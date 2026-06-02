from types import SimpleNamespace

from pawcare.schemas.state import RiskBand, UserResponse, UserResponseStatus
from pawcare.services import (
    DeterministicResponsePolisher,
    LLMUsageCollector,
    OpenAIResponsePolisher,
)


def _response() -> UserResponse:
    return UserResponse(
        status=UserResponseStatus.attention_needed,
        workflow_id="wf_polish_001",
        dog_id="dog_mochi",
        risk_band=RiskBand.moderate,
        message="Quick update: Observed concern. I am monitoring this closely.",
        escalation_conditions=["contact a vet if symptoms worsen"],
        source_guideline_ids=["GL_APPETITE_002"],
    )


def test_deterministic_response_polisher_is_noop() -> None:
    response = _response()

    polished = DeterministicResponsePolisher().polish(response=response)

    assert polished == response


def test_openai_response_polisher_changes_only_message_and_records_usage() -> None:
    class FakeResponses:
        def create(self, *, model: str, input: str) -> SimpleNamespace:
            assert "Do not change status" in input
            return SimpleNamespace(
                output_text="A warmer but still safe message.",
                usage=SimpleNamespace(input_tokens=120, output_tokens=30, total_tokens=150),
            )

    class FakeClient:
        responses = FakeResponses()

    usage_collector = LLMUsageCollector()
    response = _response()
    polished = OpenAIResponsePolisher(
        client=FakeClient(),
        model="test-model",
        usage_collector=usage_collector,
    ).polish(response=response)
    usage = usage_collector.summary()

    assert polished.message == "A warmer but still safe message."
    assert polished.status == response.status
    assert polished.risk_band == response.risk_band
    assert polished.escalation_conditions == response.escalation_conditions
    assert polished.source_guideline_ids == response.source_guideline_ids
    assert usage["total_tokens"] == 150


def test_openai_response_polisher_falls_back_for_unsafe_output() -> None:
    class FakeResponses:
        def create(self, *, model: str, input: str) -> SimpleNamespace:
            return SimpleNamespace(output_text="Your dog has gastroenteritis. Give a dose.")

    class FakeClient:
        responses = FakeResponses()

    response = _response()

    polished = OpenAIResponsePolisher(client=FakeClient()).polish(response=response)

    assert polished == response


def test_openai_response_polisher_falls_back_on_client_failure() -> None:
    class BrokenResponses:
        def create(self, *, model: str, input: str) -> SimpleNamespace:
            raise RuntimeError("network unavailable")

    class BrokenClient:
        responses = BrokenResponses()

    response = _response()

    polished = OpenAIResponsePolisher(client=BrokenClient()).polish(response=response)

    assert polished == response
