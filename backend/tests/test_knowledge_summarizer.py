from types import SimpleNamespace

from pawcare.services import (
    DeterministicKnowledgeSummarizer,
    LLMUsageCollector,
    OpenAIKnowledgeSummarizer,
)


MATCHES = [
    {
        "domain": "urinary",
        "summary": "Cats that cannot pee need urgent triage.",
        "vet_discussion_topics": ["urinary obstruction", "FLUTD"],
        "red_flags": ["cannot pee", "blood in urine"],
    }
]


def test_deterministic_summarizer_needs_no_api_key_or_network() -> None:
    summary = DeterministicKnowledgeSummarizer().summarize(
        matches=MATCHES,
        raw_text="cat cannot pee, should I worry?",
        pet_context={"name": "NiaoNiao"},
    )

    assert "not a diagnosis" in summary.lower()
    assert "urinary obstruction" in summary
    assert "cannot pee" in summary
    assert "dose" not in summary.lower()


def test_openai_summarizer_uses_fake_client_without_network() -> None:
    class FakeResponses:
        def create(self, *, model: str, input: str) -> SimpleNamespace:
            assert model == "test-model"
            assert "Do not diagnose" in input
            return SimpleNamespace(output_text="A safe fake summary.")

    class FakeClient:
        responses = FakeResponses()

    summary = OpenAIKnowledgeSummarizer(
        client=FakeClient(),
        model="test-model",
    ).summarize(
        matches=MATCHES,
        raw_text="cat cannot pee, should I worry?",
        pet_context={"name": "NiaoNiao"},
    )

    assert summary == "A safe fake summary."


def test_openai_summarizer_records_usage_when_response_includes_usage() -> None:
    class FakeResponses:
        def create(self, *, model: str, input: str) -> SimpleNamespace:
            return SimpleNamespace(
                output_text="A safe fake summary.",
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=25,
                    total_tokens=125,
                ),
            )

    class FakeClient:
        responses = FakeResponses()

    usage_collector = LLMUsageCollector()
    summary = OpenAIKnowledgeSummarizer(
        client=FakeClient(),
        model="test-model",
        usage_collector=usage_collector,
    ).summarize(
        matches=MATCHES,
        raw_text="cat cannot pee, should I worry?",
        pet_context={"name": "NiaoNiao"},
    )

    usage = usage_collector.summary()

    assert summary == "A safe fake summary."
    assert usage["available"] is True
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 25
    assert usage["total_tokens"] == 125
    assert usage["estimated_cost_usd"] is not None


def test_openai_summarizer_falls_back_on_failure() -> None:
    class BrokenResponses:
        def create(self, *, model: str, input: str) -> SimpleNamespace:
            raise RuntimeError("network unavailable")

    class BrokenClient:
        responses = BrokenResponses()

    summary = OpenAIKnowledgeSummarizer(client=BrokenClient()).summarize(
        matches=MATCHES,
        raw_text="cat cannot pee, should I worry?",
        pet_context={"name": "NiaoNiao"},
    )

    assert "not a diagnosis" in summary.lower()
    assert "urinary obstruction" in summary
