from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import LogProcessingService


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
            },
            "resource_guarding_profile": {
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


def test_service_returns_attention_needed_for_low_appetite_health_concern() -> None:
    result = LogProcessingService().process_log(
        workflow_id="wf_001",
        dog_id="dog_123",
        raw_text="Mochi barely touched breakfast.",
        timestamp="2026-05-08T08:00:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    assert result.response.status == "attention_needed"
    assert result.response.risk_band == "moderate"
    assert "appetite below baseline or expected intake" in result.response.message
    assert result.coordinator_result.state.agent_outputs[0].proposed_update is not None
    assert "proposed_update" not in result.response.model_dump()


def test_service_returns_attention_needed_for_moderate_social_risk() -> None:
    result = LogProcessingService().process_log(
        workflow_id="wf_002",
        dog_id="dog_123",
        raw_text="Mochi froze and licked her lips when the large dog came near her chew.",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    assert result.response.status == "attention_needed"
    assert result.response.risk_band == "moderate"
    assert "stress signals near high-value resource" in result.response.message
    assert "GL_RESOURCE_GUARDING_001" in result.response.source_guideline_ids
    assert result.response.escalation_conditions


def test_service_returns_escalate_for_high_social_risk() -> None:
    result = LogProcessingService().process_log(
        workflow_id="wf_003",
        dog_id="dog_123",
        raw_text="When Bear walked near Mochi's food bowl, Mochi stiffened, growled, and snapped in the air.",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    assert result.response.status == "escalate"
    assert result.response.risk_band == "high"
    assert "escalation signals during social interaction" in result.response.message


def test_service_returns_escalate_for_nsaid_bloody_stool() -> None:
    result = LogProcessingService().process_log(
        workflow_id="wf_004",
        dog_id="dog_123",
        raw_text="After taking Rimadyl pain medication, Mochi had bloody stool.",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    assert result.response.status == "escalate"
    assert result.response.risk_band == "high"
    assert "possible medication side-effect warning signs" in result.response.message
    assert "GL_NSAID_SIDE_EFFECT_001" in result.response.source_guideline_ids
    assert result.coordinator_result.state.safety_review is not None
    assert result.coordinator_result.state.safety_review.medication_advice_present is False
    assert "dosage" not in result.response.message.lower()
    assert "dose" not in result.response.message.lower()


def test_service_returns_escalate_for_acl_postop_non_weight_bearing() -> None:
    result = LogProcessingService().process_log(
        workflow_id="wf_005",
        dog_id="dog_123",
        raw_text="Mochi is post-op from ACL surgery and won't put her back leg on the ground.",
        timestamp="2026-05-08T09:15:00-07:00",
        dog_profile=_dog_profile(),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )

    assert result.response.status == "escalate"
    assert result.response.risk_band == "high"
    assert "post-op non-weight-bearing" in result.response.message
    assert "GL_ACL_POSTOP_001" in result.response.source_guideline_ids
