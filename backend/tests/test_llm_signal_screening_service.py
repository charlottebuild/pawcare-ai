from pawcare.services.llm_signal_screening_service import (
    DeterministicLLMSignalScreeningService,
    OpenAILLMSignalScreeningService,
    should_llm_screen,
)


class _FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text

    def create(self, *, model: str, input: str):
        return type("FakeResponse", (), {"output_text": self.output_text})()


class _FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = _FakeResponses(output_text)


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
