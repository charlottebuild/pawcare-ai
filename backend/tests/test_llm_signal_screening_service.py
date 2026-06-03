from pawcare.services.llm_signal_screening_service import (
    DeterministicLLMSignalScreeningService,
    OpenAILLMSignalScreeningService,
    should_llm_screen,
)
from pawcare.services.llm_usage import LLMUsageCollector


class _FakeResponses:
    def __init__(self, output_text: str, usage=None) -> None:
        self.output_text = output_text
        self.usage = usage

    def create(self, *, model: str, input: str):
        return type(
            "FakeResponse",
            (),
            {"output_text": self.output_text, "usage": self.usage},
        )()


class _FakeClient:
    def __init__(self, output_text: str, usage=None) -> None:
        self.responses = _FakeResponses(output_text, usage=usage)


def test_deterministic_llm_signal_screening_is_noop() -> None:
    result = DeterministicLLMSignalScreeningService().screen(
        raw_text="Is this normal?",
        pet_context={"name": "Mochi"},
        target="health",
    )

    assert result.is_empty()


def test_openai_llm_signal_screening_parses_structured_json() -> None:
    service = OpenAILLMSignalScreeningService(
        client=_FakeClient(
            """
            {
              "possible_domains": ["health", "mobility"],
              "matched_phrases": ["moving strangely"],
              "suggested_canonical_terms": ["mobility_change"],
              "suggested_guideline_ids": ["GL_LAMENESS_001"],
              "confidence": 0.72,
              "reasoning_summary": "Movement concern should be reviewed."
            }
            """
        )
    )

    result = service.screen(
        raw_text="Mochi is moving strangely, is this normal?",
        pet_context={"name": "Mochi"},
        target="health",
    )

    assert result.possible_domains == ["health", "mobility"]
    assert result.suggested_guideline_ids == ["GL_LAMENESS_001"]
    assert result.confidence == 0.72
    assert "Movement concern" in result.reasoning_summary


def test_openai_llm_signal_screening_records_usage_when_response_includes_usage() -> None:
    usage_collector = LLMUsageCollector()
    service = OpenAILLMSignalScreeningService(
        client=_FakeClient(
            """
            {
              "possible_domains": ["health"],
              "matched_phrases": ["moving strangely"],
              "suggested_canonical_terms": ["mobility_change"],
              "suggested_guideline_ids": ["GL_LAMENESS_001"],
              "confidence": 0.7,
              "reasoning_summary": "Movement concern should be reviewed."
            }
            """,
            usage={"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
        ),
        model="test-model",
        usage_collector=usage_collector,
    )

    result = service.screen(
        raw_text="Mochi is moving strangely, is this normal?",
        pet_context={"name": "Mochi"},
        target="health",
    )
    usage = usage_collector.summary()

    assert not result.is_empty()
    assert usage["available"] is True
    assert usage["prompt_tokens"] == 80
    assert usage["completion_tokens"] == 20
    assert usage["total_tokens"] == 100


def test_openai_llm_signal_screening_blocks_unsafe_diagnosis_or_medication_text() -> None:
    service = OpenAILLMSignalScreeningService(
        client=_FakeClient(
            """
            {
              "possible_domains": ["health"],
              "matched_phrases": ["diarrhea"],
              "suggested_canonical_terms": ["diarrhea"],
              "suggested_guideline_ids": ["GL_CONDITION_GI_001"],
              "confidence": 0.8,
              "reasoning_summary": "The pet has gastroenteritis and needs a dosage."
            }
            """
        )
    )

    result = service.screen(
        raw_text="Mochi has diarrhea, is this normal?",
        pet_context={"name": "Mochi"},
        target="health",
    )

    assert result.is_empty()


def test_openai_llm_signal_screening_falls_back_on_client_failure() -> None:
    class FailingResponses:
        def create(self, *, model: str, input: str):
            raise RuntimeError("network unavailable")

    class FailingClient:
        responses = FailingResponses()

    result = OpenAILLMSignalScreeningService(client=FailingClient()).screen(
        raw_text="I am worried about this behavior.",
        pet_context={"name": "Mochi"},
        target="behavior",
    )

    assert result.is_empty()


def test_should_llm_screen_for_care_questions_but_not_plain_updates() -> None:
    assert should_llm_screen("Mochi is acting weird, is this normal?")
    assert should_llm_screen("Mochi seems anxious, what should I do?")
    assert not should_llm_screen("Mochi ate breakfast.")
