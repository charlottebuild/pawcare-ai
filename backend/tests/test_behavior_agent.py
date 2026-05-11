from pawcare.agents import BehaviorAgent
from pawcare.schemas.state import ActiveContext
from pawcare.skills import LogExtractor


def test_behavior_agent_flags_stress_near_resource_as_proposed_update() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi froze and licked her lips when the large dog came near her chew.",
        timestamp="2026-05-08T09:15:00-07:00",
    )
    active_context = ActiveContext.model_validate(
        {
            "target_agent": "BehaviorAgent",
            "task": "Assess whether this social interaction indicates stress.",
            "current_observation_ids": ["obs_001"],
            "relevant_baseline": {
                "large_dog_reaction": "neutral",
                "resource_guarding_profile": {
                    "toy_guarding": "mild",
                    "known_guarded_resources": ["high_value_chews"],
                },
            },
            "allowed_guideline_ids": [
                "GL_SOCIAL_STRESS_001",
                "GL_RESOURCE_GUARDING_001",
            ],
        }
    )

    output = BehaviorAgent().analyze(
        active_context=active_context,
        observations=batch.observations,
    )

    assert output.agent == "BehaviorAgent"
    assert output.conclusion == "moderate social stress near resource"
    assert output.proposed_update is not None
    assert output.proposed_update.target_path == "risk_assessment.risk_factors"
    assert output.proposed_update.value == "stress signals near high-value resource"
    assert "GL_RESOURCE_GUARDING_001" in output.source_guideline_ids


def test_behavior_agent_treats_loose_play_as_protective_factor() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi did a play bow, had a loose wiggly body, and took turns chasing the other small dog.",
        timestamp="2026-05-08T09:15:00-07:00",
    )
    active_context = ActiveContext.model_validate(
        {
            "target_agent": "BehaviorAgent",
            "task": "Assess whether this social interaction indicates stress or play.",
            "current_observation_ids": ["obs_001"],
            "relevant_baseline": {
                "small_dog_reaction": "friendly",
                "play_style": "chase_and_pause",
            },
            "allowed_guideline_ids": ["GL_SOCIAL_PLAY_001"],
        }
    )

    output = BehaviorAgent().analyze(
        active_context=active_context,
        observations=batch.observations,
    )

    assert output.conclusion == "likely appropriate play"
    assert output.proposed_update is not None
    assert output.proposed_update.target_path == "risk_assessment.protective_factors"
    assert output.source_guideline_ids == ["GL_SOCIAL_PLAY_001"]


def test_behavior_agent_records_missing_information_when_no_social_observation() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi barely touched breakfast.",
        timestamp="2026-05-08T08:00:00-07:00",
    )
    active_context = ActiveContext.model_validate(
        {
            "target_agent": "BehaviorAgent",
            "task": "Assess behavior context.",
            "current_observation_ids": ["obs_001"],
            "allowed_guideline_ids": ["GL_SOCIAL_STRESS_001"],
        }
    )

    output = BehaviorAgent().analyze(
        active_context=active_context,
        observations=batch.observations,
    )

    assert output.conclusion == "no social interaction evidence"
    assert output.proposed_update is not None
    assert output.proposed_update.target_path == "current_session_state.pending_conflicts"
    assert "social_context" in output.missing_information


def test_behavior_agent_flags_resource_guarding_escalation() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="When Bear walked near Mochi's food bowl, Mochi stiffened, growled, and snapped in the air.",
        timestamp="2026-05-08T09:15:00-07:00",
    )
    active_context = ActiveContext.model_validate(
        {
            "target_agent": "BehaviorAgent",
            "task": "Assess behavior context.",
            "current_observation_ids": ["obs_001"],
            "relevant_baseline": {
                "resource_guarding_profile": {
                    "food_guarding": "unknown",
                },
            },
            "allowed_guideline_ids": [
                "GL_SOCIAL_STRESS_001",
                "GL_RESOURCE_GUARDING_001",
            ],
        }
    )

    output = BehaviorAgent().analyze(
        active_context=active_context,
        observations=batch.observations,
    )

    assert output.conclusion == "high social safety concern"
    assert output.proposed_update is not None
    assert output.proposed_update.value == "escalation signals during social interaction"
