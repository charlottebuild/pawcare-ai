import asyncio
import time

from pawcare.coordinator import CareCoordinator
from pawcare.agents import BehaviorAgent, HealthAgent
from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services.llm_signal_screening_service import LLMSignalScreeningResult


def _dog_profile() -> DogProfile:
    return DogProfile(id="dog_123", name="Mochi", species="dog")


def _behavioral_baseline() -> BehavioralBaseline:
    return BehavioralBaseline.model_validate(
        {
            "general_temperament": "food_motivated",
            "social_profile": {
                "large_dog_reaction": "neutral",
                "small_dog_reaction": "friendly",
                "prey_drive_level": 4,
                "known_triggers": ["direct_staring"],
                "stress_signals_typical": ["lip_licking"],
            },
            "resource_guarding_profile": {
                "food_guarding": "none_known",
                "toy_guarding": "mild",
                "known_guarded_resources": ["high_value_chews"],
            },
        }
    )


def _health_baseline() -> HealthBaseline:
    return HealthBaseline(
        normal_appetite="high",
        normal_stool_quality="firm",
        normal_activity_level="medium",
    )


def test_coordinator_builds_active_context_and_merges_behavior_risk_update() -> None:
    result = CareCoordinator().handle_log(
        workflow_id="wf_001",
        dog_id="dog_123",
        raw_text="Mochi froze and licked her lips when the large dog came near her chew.",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    state = result.state
    assert state.active_context is not None
    assert state.active_context.target_agent == "BehaviorAgent"
    assert [output.agent for output in state.agent_outputs] == ["BehaviorAgent"]
    behavior_output = next(output for output in state.agent_outputs if output.agent == "BehaviorAgent")
    assert behavior_output.proposed_update is not None
    assert behavior_output.proposed_update in result.accepted_updates
    assert state.risk_assessment is not None
    assert state.risk_assessment.risk_band == "moderate"
    assert state.risk_assessment.primary_risk_domain == "social"
    assert state.risk_assessment.risk_factors == [
        "stress signals near high-value resource"
    ]
    assert "GL_RESOURCE_GUARDING_001" in state.risk_assessment.source_guideline_ids
    assert state.safety_review is not None
    assert state.safety_review.final_status == "approved"
    assert state.final_recommendation is not None
    assert state.final_recommendation.safety_checked is True
    assert "stress signals near high-value resource" in state.final_recommendation.owner_message
    assert state.active_context.relevant_baseline["behavior_references"]
    assert "Behavior context:" in behavior_output.reasoning_trace


def test_coordinator_merges_play_case_as_protective_factor() -> None:
    result = CareCoordinator().handle_log(
        workflow_id="wf_002",
        dog_id="dog_123",
        raw_text="Mochi did a play bow, had a loose wiggly body, and took turns chasing the other small dog.",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    state = result.state
    assert state.risk_assessment is not None
    assert state.risk_assessment.risk_band == "low"
    assert state.risk_assessment.protective_factors == [
        "loose body and play bow suggest appropriate play context"
    ]
    assert state.risk_assessment.risk_factors == []
    assert state.safety_review is not None
    assert state.final_recommendation is not None
    assert state.final_recommendation.risk_band == "low"
    assert "Don't worry" not in state.final_recommendation.owner_message


def test_coordinator_routes_food_only_log_to_health_agent_without_behavior_conflict() -> None:
    result = CareCoordinator().handle_log(
        workflow_id="wf_003",
        dog_id="dog_123",
        raw_text="Mochi barely touched breakfast.",
        timestamp="2026-05-08T08:00:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    state = result.state
    assert state.risk_assessment is not None
    assert state.risk_assessment.primary_risk_domain == "health"
    assert state.risk_assessment.risk_band == "moderate"
    assert state.safety_review is not None
    assert state.final_recommendation is not None
    assert [output.agent for output in state.agent_outputs] == ["HealthAgent"]
    assert state.current_session_state.pending_conflicts == []
    assert state.risk_assessment.escalation_conditions == [
        "vomiting repeats or worsens",
        "bloody or black/tarry stool appears",
        "energy drops below baseline",
        "the pet refuses food or water",
        "post-op mobility worsens or non-weight-bearing continues",
    ]


def test_coordinator_merges_mixed_health_and_social_outputs() -> None:
    result = CareCoordinator().handle_log(
        workflow_id="wf_004",
        dog_id="dog_123",
        raw_text=(
            "Mochi skipped dinner after a stressful intro with a larger dog. "
            "She froze and licked her lips."
        ),
        timestamp="2026-05-08T19:00:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    state = result.state
    assert [output.agent for output in state.agent_outputs] == [
        "HealthAgent",
        "BehaviorAgent",
    ]
    assert state.risk_assessment is not None
    assert state.risk_assessment.primary_risk_domain == "mixed"
    assert state.risk_assessment.risk_band == "moderate"
    assert "GL_APPETITE_002" in state.risk_assessment.source_guideline_ids
    assert "GL_SOCIAL_STRESS_001" in state.risk_assessment.source_guideline_ids
    assert len(state.current_session_state.pending_conflicts) == 1
    conflict = state.current_session_state.pending_conflicts[0]
    assert conflict.type == "behavior_vs_health"
    assert conflict.involved_agents == ["HealthAgent", "BehaviorAgent"]
    assert state.safety_review is not None
    assert state.final_recommendation is not None


def test_coordinator_passes_professional_references_to_health_agent() -> None:
    result = CareCoordinator().handle_log(
        workflow_id="wf_005",
        dog_id="dog_123",
        raw_text="Mochi is vomiting and has diarrhea. Could it be gastroenteritis?",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    state = result.state
    health_output = next(output for output in state.agent_outputs if output.agent == "HealthAgent")
    assert state.active_context is not None
    assert state.active_context.target_agent == "HealthAgent"
    assert state.active_context.relevant_baseline["professional_references"]
    assert "Professional context:" in health_output.reasoning_trace
    assert "Merck Veterinary Manual" in health_output.reasoning_trace


class _FakeScreeningService:
    def __init__(self, result_by_target: dict[str, LLMSignalScreeningResult]) -> None:
        self.result_by_target = result_by_target
        self.calls: list[str] = []

    def screen(self, *, raw_text: str, pet_context: dict[str, object], target: str):
        self.calls.append(target)
        return self.result_by_target.get(
            target,
            LLMSignalScreeningResult(
                possible_domains=[],
                matched_phrases=[],
                suggested_canonical_terms=[],
                suggested_guideline_ids=[],
                confidence=0.0,
                reasoning_summary="",
            ),
        )


def test_llm_screening_can_route_health_agent_when_rules_have_no_health_signal() -> None:
    screening = _FakeScreeningService(
        {
            "health": LLMSignalScreeningResult(
                possible_domains=["health", "mobility"],
                matched_phrases=["moving strangely"],
                suggested_canonical_terms=["mobility_change"],
                suggested_guideline_ids=["GL_LAMENESS_001"],
                confidence=0.72,
                reasoning_summary="Movement concern should be reviewed.",
            )
        }
    )

    result = CareCoordinator(llm_signal_screening_service=screening).handle_log(
        workflow_id="wf_llm_001",
        dog_id="dog_123",
        raw_text="Mochi is moving strangely, is this normal?",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    state = result.state
    assert "health" in screening.calls
    assert [output.agent for output in state.agent_outputs] == ["HealthAgent"]
    health_output = state.agent_outputs[0]
    assert "LLM health screening concern" in health_output.conclusion
    assert "Movement concern should be reviewed" in health_output.reasoning_trace
    assert state.risk_assessment is not None
    assert state.risk_assessment.risk_band == "moderate"
    assert "GL_LAMENESS_001" in state.risk_assessment.source_guideline_ids


def test_llm_screening_can_route_behavior_agent_when_rules_have_no_social_signal() -> None:
    screening = _FakeScreeningService(
        {
            "behavior": LLMSignalScreeningResult(
                possible_domains=["behavior", "anxiety"],
                matched_phrases=["seems scared"],
                suggested_canonical_terms=["anxiety"],
                suggested_guideline_ids=["GL_SOCIAL_STRESS_001"],
                confidence=0.7,
                reasoning_summary="Anxiety-like behavior should be reviewed.",
            )
        }
    )

    result = CareCoordinator(llm_signal_screening_service=screening).handle_log(
        workflow_id="wf_llm_002",
        dog_id="dog_123",
        raw_text="Mochi seems scared and anxious, what should I do?",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    state = result.state
    assert "behavior" in screening.calls
    assert [output.agent for output in state.agent_outputs] == ["BehaviorAgent"]
    behavior_output = state.agent_outputs[0]
    assert "LLM behavior screening concern" in behavior_output.conclusion
    assert "Anxiety-like behavior should be reviewed" in behavior_output.reasoning_trace
    assert state.risk_assessment is not None
    assert state.risk_assessment.risk_band == "moderate"


def test_deterministic_red_flag_skips_llm_screening() -> None:
    screening = _FakeScreeningService(
        {
            "health": LLMSignalScreeningResult(
                possible_domains=["health"],
                matched_phrases=["blood"],
                suggested_canonical_terms=["low_risk"],
                suggested_guideline_ids=["GL_APPETITE_002"],
                confidence=0.1,
                reasoning_summary="This should not run.",
            )
        }
    )

    result = CareCoordinator(llm_signal_screening_service=screening).handle_log(
        workflow_id="wf_llm_003",
        dog_id="dog_123",
        raw_text="Mochi has bloody stool.",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    assert screening.calls == []
    assert result.state.risk_assessment is not None
    assert result.state.risk_assessment.risk_band == "high"
    assert "GL_STOOL_001" in result.state.risk_assessment.source_guideline_ids


class _SlowHealthAgent(HealthAgent):
    def analyze(self, *, active_context, observations):
        time.sleep(0.2)
        return super().analyze(active_context=active_context, observations=observations)


class _SlowBehaviorAgent(BehaviorAgent):
    def analyze(self, *, active_context, observations):
        time.sleep(0.2)
        return super().analyze(active_context=active_context, observations=observations)


def test_async_coordinator_runs_health_and_behavior_workers_concurrently() -> None:
    coordinator = CareCoordinator(
        health_agent=_SlowHealthAgent(),
        behavior_agent=_SlowBehaviorAgent(),
    )
    start = time.perf_counter()
    result = asyncio.run(
        coordinator.handle_log_async(
            workflow_id="wf_async_001",
            dog_id="dog_123",
            raw_text=(
                "Mochi skipped dinner after a stressful intro with a larger dog. "
                "She froze and licked her lips."
            ),
            timestamp="2026-05-08T19:00:00-07:00",
            dog_profile=_dog_profile(),
            behavioral_baseline=_behavioral_baseline(),
            health_baseline=_health_baseline(),
        )
    )
    elapsed = time.perf_counter() - start

    assert [output.agent for output in result.state.agent_outputs] == [
        "HealthAgent",
        "BehaviorAgent",
    ]
    assert elapsed < 0.35
    assert result.state.risk_assessment is not None
    assert result.state.risk_assessment.primary_risk_domain == "mixed"
