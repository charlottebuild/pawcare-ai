from pawcare.agents import HealthAgent
from pawcare.schemas.state import ActiveContext
from pawcare.skills import LogExtractor


def _active_context() -> ActiveContext:
    return ActiveContext(
        target_agent="HealthAgent",
        task="Assess health risk.",
        current_observation_ids=["obs_001", "obs_002", "obs_003"],
        allowed_guideline_ids=[
            "GL_STOOL_001",
            "GL_NSAID_SIDE_EFFECT_001",
            "GL_ACL_POSTOP_001",
            "GL_LAMENESS_001",
        ],
    )


def test_health_agent_flags_nsaid_bloody_stool_as_high_medication_safety_concern() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="After taking Rimadyl pain medication, Mochi had bloody stool.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    output = HealthAgent().analyze(
        active_context=_active_context(),
        observations=batch.observations,
    )

    assert output.conclusion == "high medication safety concern"
    assert output.proposed_update is not None
    assert output.proposed_update.value == "possible medication side-effect warning signs"
    assert "GL_NSAID_SIDE_EFFECT_001" in output.source_guideline_ids
    assert "GL_STOOL_001" in output.source_guideline_ids


def test_health_agent_flags_acl_postop_non_weight_bearing() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi is post-op from ACL surgery and won't put her back leg on the ground.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    output = HealthAgent().analyze(
        active_context=_active_context(),
        observations=batch.observations,
    )

    assert output.conclusion == "high post-op mobility concern"
    assert output.proposed_update is not None
    assert output.proposed_update.value == "post-op non-weight-bearing or severe mobility change"
    assert "GL_ACL_POSTOP_001" in output.source_guideline_ids
    assert "GL_LAMENESS_001" in output.source_guideline_ids


def test_health_agent_flags_low_appetite_as_moderate_concern() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi barely touched breakfast.",
        timestamp="2026-05-08T08:00:00-07:00",
    )

    output = HealthAgent().analyze(
        active_context=_active_context(),
        observations=batch.observations,
    )

    assert output.conclusion == "moderate appetite concern"
    assert output.proposed_update is not None
    assert output.proposed_update.value == "appetite below baseline or expected intake"
    assert "GL_APPETITE_002" in output.source_guideline_ids
