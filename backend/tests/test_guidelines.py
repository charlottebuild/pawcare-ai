from pawcare.knowledge import (
    GUIDELINES,
    GUIDELINES_BY_ID,
    GuidelineType,
    find_guidelines_by_signals,
    find_guidelines_by_type,
    get_guideline,
)


def test_guideline_ids_are_unique() -> None:
    guideline_ids = [guideline.id for guideline in GUIDELINES]

    assert len(guideline_ids) == len(set(guideline_ids))
    assert len(GUIDELINES_BY_ID) == len(GUIDELINES)


def test_guideline_taxonomy_has_all_core_types() -> None:
    guideline_types = {guideline.type for guideline in GUIDELINES}

    assert guideline_types == {
        GuidelineType.health_observation,
        GuidelineType.medication_safety,
        GuidelineType.post_op_recovery,
        GuidelineType.behavior_social_safety,
        GuidelineType.owner_communication,
    }


def test_get_guideline_by_id() -> None:
    guideline = get_guideline("GL_NSAID_SIDE_EFFECT_001")

    assert guideline.type == GuidelineType.medication_safety
    assert "bloody_stool" in guideline.signals
    assert guideline.sources


def test_find_guidelines_by_signals_returns_relevant_sources() -> None:
    guidelines = find_guidelines_by_signals({"bloody_stool", "vomiting"})
    guideline_ids = {guideline.id for guideline in guidelines}

    assert "GL_STOOL_001" in guideline_ids
    assert "GL_VOMITING_001" in guideline_ids
    assert "GL_NSAID_SIDE_EFFECT_001" in guideline_ids


def test_find_post_op_recovery_guidelines() -> None:
    guidelines = find_guidelines_by_type(GuidelineType.post_op_recovery)
    guideline_ids = {guideline.id for guideline in guidelines}

    assert "GL_ACL_POSTOP_001" in guideline_ids
    assert "GL_ACTIVITY_RESTRICTION_001" in guideline_ids
