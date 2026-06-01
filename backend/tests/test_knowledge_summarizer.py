from types import SimpleNamespace

from pawcare.services import (
    DeterministicKnowledgeSummarizer,
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
