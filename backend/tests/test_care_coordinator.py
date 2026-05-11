from pawcare.coordinator import CareCoordinator
from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline


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
    assert state.agent_outputs[0].agent == "BehaviorAgent"
    assert state.agent_outputs[0].proposed_update is not None
    assert result.accepted_updates == [state.agent_outputs[0].proposed_update]
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


def test_coordinator_records_missing_social_context_conflict_for_food_only_log() -> None:
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
    assert state.risk_assessment is None
    assert state.safety_review is None
    assert state.final_recommendation is None
    assert len(state.current_session_state.pending_conflicts) == 1
    conflict = state.current_session_state.pending_conflicts[0]
    assert conflict.type == "missing_information"
    assert conflict.involved_agents == ["BehaviorAgent"]
