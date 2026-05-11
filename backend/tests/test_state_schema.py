import pytest
from pydantic import ValidationError

from pawcare.schemas.state import (
    ActiveContext,
    AgentOutput,
    Observation,
    ObservationCategory,
    PawCareState,
    ProposedUpdate,
)


def test_social_observation_accepts_known_body_language_signals() -> None:
    observation = Observation.model_validate(
        {
            "observation_id": "obs_001",
            "timestamp": "2026-05-08T09:15:00-07:00",
            "source": "user_log",
            "category": "social_interaction",
            "raw_text": "Mochi froze and licked her lips when the large dog came near her chew.",
            "confidence": 0.91,
            "entity_involved": {
                "type": "large_dog",
                "id": "dog_456",
                "relative_size": "larger",
            },
            "social_context": {
                "interaction_type": "resource_proximity",
                "initiator": "other_dog",
                "distance": "near",
                "resource_involved": {
                    "present": True,
                    "type": "chew",
                    "ownership": "primary_dog",
                },
                "signals": {
                    "body_language": ["lip_licking", "frozen", "stiff_body"],
                    "vocalization": ["silent"],
                    "posture": "frozen",
                    "movement": "avoidant",
                },
                "handler_intervention": {
                    "occurred": True,
                    "type": "increased_distance",
                    "result": "deescalated",
                },
            },
            "severity_score": 6,
            "source_guideline_ids": [
                "GL_SOCIAL_STRESS_001",
                "GL_RESOURCE_GUARDING_001",
            ],
        }
    )

    assert observation.category == ObservationCategory.social_interaction
    assert observation.social_context is not None
    assert observation.social_context.signals.body_language == [
        "lip_licking",
        "frozen",
        "stiff_body",
    ]


def test_social_observation_rejects_unknown_body_language_signal() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Observation.model_validate(
            {
                "observation_id": "obs_001",
                "timestamp": "2026-05-08T09:15:00-07:00",
                "category": "social_interaction",
                "raw_text": "Mochi looked kind of sad near the large dog.",
                "confidence": 0.8,
                "social_context": {
                    "interaction_type": "greeting",
                    "signals": {
                        "body_language": ["kind_of_sad", "lip_licking"],
                    },
                },
            }
        )

    assert "kind_of_sad" in str(exc_info.value)


def test_dog_observation_accepts_expanded_dog_body_language_signals() -> None:
    observation = Observation.model_validate(
        {
            "observation_id": "obs_tail_001",
            "timestamp": "2026-05-08T09:15:00-07:00",
            "species": "dog",
            "category": "social_interaction",
            "raw_text": "Mochi lowered her tail and put her ears back when the larger dog approached.",
            "confidence": 0.88,
            "social_context": {
                "interaction_type": "greeting",
                "signals": {
                    "body_language": ["lowered_tail", "ears_back"],
                },
            },
        }
    )

    assert observation.social_context is not None
    assert observation.social_context.signals.body_language == [
        "lowered_tail",
        "ears_back",
    ]


def test_cat_observation_accepts_cat_specific_body_language_signals() -> None:
    observation = Observation.model_validate(
        {
            "observation_id": "obs_cat_001",
            "timestamp": "2026-05-08T09:15:00-07:00",
            "species": "cat",
            "category": "social_interaction",
            "raw_text": "Miso's tail puffed up and her ears flattened when the dog approached.",
            "confidence": 0.9,
            "social_context": {
                "interaction_type": "greeting",
                "signals": {
                    "body_language": ["puffed_tail", "flattened_ears"],
                },
            },
        }
    )

    assert observation.species == "cat"
    assert observation.social_context is not None
    assert observation.social_context.signals.body_language == [
        "puffed_tail",
        "flattened_ears",
    ]


def test_dog_observation_rejects_cat_only_body_language_signals() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Observation.model_validate(
            {
                "observation_id": "obs_cat_signal_on_dog_001",
                "timestamp": "2026-05-08T09:15:00-07:00",
                "species": "dog",
                "category": "social_interaction",
                "raw_text": "Mochi had a puffed tail when the dog approached.",
                "confidence": 0.9,
                "social_context": {
                    "interaction_type": "greeting",
                    "signals": {
                        "body_language": ["puffed_tail"],
                    },
                },
            }
        )

    assert "cat-only body_language values" in str(exc_info.value)


def test_social_interaction_requires_social_context() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Observation.model_validate(
            {
                "observation_id": "obs_002",
                "timestamp": "2026-05-08T09:15:00-07:00",
                "category": "social_interaction",
                "raw_text": "Mochi froze when Bear approached.",
                "confidence": 0.8,
            }
        )

    assert "social_context is required" in str(exc_info.value)


def test_worker_output_uses_proposed_update_instead_of_direct_state_mutation() -> None:
    output = AgentOutput.model_validate(
        {
            "agent": "BehaviorAgent",
            "input_active_context_id": "ctx_001",
            "conclusion": "moderate social stress",
            "confidence": 0.84,
            "missing_information": [
                "whether this dog has guarded chews before",
            ],
            "proposed_update": {
                "target_path": "risk_assessment.risk_factors",
                "operation": "append",
                "value": "stress signals near high-value resource",
            },
            "reasoning_trace": "Lip licking and freezing appeared near a chew.",
            "source_guideline_ids": [
                "GL_SOCIAL_STRESS_001",
                "GL_RESOURCE_GUARDING_001",
            ],
        }
    )

    assert isinstance(output.proposed_update, ProposedUpdate)
    assert output.proposed_update.target_path == "risk_assessment.risk_factors"


def test_worker_output_rejects_direct_global_state_mutation_shape() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AgentOutput.model_validate(
            {
                "agent": "BehaviorAgent",
                "conclusion": "high risk",
                "confidence": 0.9,
                "reasoning_trace": "Direct mutation should not be accepted.",
                "source_guideline_ids": ["GL_SOCIAL_STRESS_001"],
                "risk_assessment": {
                    "risk_level": 8,
                },
            }
        )

    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_minimal_pawcare_state_can_hold_active_context() -> None:
    state = PawCareState.model_validate(
        {
            "workflow_id": "wf_001",
            "dog_id": "dog_123",
            "dog_profile": {
                "id": "dog_123",
                "name": "Mochi",
            },
            "behavioral_baseline": {
                "general_temperament": "food_motivated",
                "social_profile": {
                    "large_dog_reaction": "neutral",
                    "prey_drive_level": 4,
                    "stress_signals_typical": ["lip_licking"],
                },
                "resource_guarding_profile": {
                    "toy_guarding": "mild",
                    "known_guarded_resources": ["high_value_chews"],
                },
            },
            "health_baseline": {
                "normal_appetite": "high",
                "normal_stool_quality": "firm",
            },
            "current_session_state": {
                "is_active": True,
                "pending_conflicts": [],
            },
            "active_context": {
                "target_agent": "BehaviorAgent",
                "task": "Assess whether the social observation indicates stress.",
                "current_observation_ids": ["obs_001"],
                "allowed_guideline_ids": [
                    "GL_SOCIAL_STRESS_001",
                    "GL_RESOURCE_GUARDING_001",
                ],
                "required_output_path": "agent_outputs",
            },
        }
    )

    assert isinstance(state.active_context, ActiveContext)
    assert state.active_context.target_agent == "BehaviorAgent"
