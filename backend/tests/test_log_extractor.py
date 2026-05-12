from pawcare.schemas.state import ObservationCategory, Species
from pawcare.skills import LogExtractor


def test_extracts_social_context_for_large_dog_chew_stress_case() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi froze and licked her lips when the large dog came near her chew.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    assert len(batch.observations) == 1
    observation = batch.observations[0]
    assert observation.category == ObservationCategory.social_interaction
    assert observation.social_context is not None
    assert observation.entity_involved is not None
    assert observation.entity_involved.type == "large_dog"
    assert observation.social_context.interaction_type == "resource_proximity"
    assert observation.social_context.resource_involved.type == "chew"
    assert observation.social_context.signals.body_language == [
        "lip_licking",
        "frozen",
    ]
    assert "GL_RESOURCE_GUARDING_001" in observation.source_guideline_ids


def test_extracts_food_intake_and_missing_information() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi barely touched breakfast, which is weird because she usually eats everything immediately.",
        timestamp="2026-05-08T08:00:00-07:00",
    )

    assert len(batch.observations) == 1
    observation = batch.observations[0]
    assert observation.category == ObservationCategory.food_intake
    assert observation.health_context == {"food_intake": "low"}
    assert observation.source_guideline_ids == ["GL_APPETITE_002"]
    assert batch.missing_information == ["energy_level", "water_intake"]


def test_extracts_multiple_observations_from_mixed_health_and_behavior_text() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text=(
            "Mochi skipped dinner after a stressful intro with a larger dog. "
            "She is otherwise walking normally and has not vomited."
        ),
        timestamp="2026-05-08T19:00:00-07:00",
    )

    categories = [observation.category for observation in batch.observations]
    assert ObservationCategory.social_interaction in categories
    assert ObservationCategory.food_intake in categories


def test_extracts_medication_and_bloody_stool_observations() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="After taking Rimadyl pain medication, Mochi had bloody stool.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    observations_by_category = {
        observation.category: observation for observation in batch.observations
    }

    stool = observations_by_category[ObservationCategory.stool]
    medication = observations_by_category[ObservationCategory.medication_note]
    assert stool.health_context == {"stool_quality": "bloody"}
    assert stool.severity_score == 8
    assert medication.health_context == {"nsaid_or_pain_med_context": True}
    assert "GL_NSAID_SIDE_EFFECT_001" in medication.source_guideline_ids


def test_extracts_acl_postop_non_weight_bearing_mobility_observation() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi is post-op from ACL surgery and won't put her back leg on the ground.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    assert len(batch.observations) == 1
    observation = batch.observations[0]
    assert observation.category == ObservationCategory.mobility
    assert observation.health_context == {
        "mobility": "limping",
        "weight_bearing": "non_weight_bearing",
        "post_op_context": True,
    }
    assert observation.severity_score == 8
    assert observation.source_guideline_ids == [
        "GL_LAMENESS_001",
        "GL_ACL_POSTOP_001",
    ]


def test_extracts_black_tarry_stool_as_high_severity() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi had black tarry stool this morning.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    observation = batch.observations[0]
    assert observation.category == ObservationCategory.stool
    assert observation.health_context == {"stool_quality": "black_tarry"}
    assert observation.severity_score == 8


def test_extracts_cat_specific_social_signal_when_species_is_cat() -> None:
    batch = LogExtractor().extract(
        dog_id="cat_123",
        raw_text="Miso's tail puffed up and her ears flattened when the dog approached.",
        timestamp="2026-05-08T09:15:00-07:00",
        species=Species.cat,
    )

    observation = batch.observations[0]
    assert observation.species == "cat"
    assert observation.social_context is not None
    assert observation.social_context.signals.body_language == [
        "puffed_tail",
        "flattened_ears",
    ]


def test_unparsed_text_falls_back_to_other_observation() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi had a quiet afternoon.",
        timestamp="2026-05-08T15:00:00-07:00",
    )

    assert len(batch.observations) == 1
    assert batch.observations[0].category == ObservationCategory.other
    assert batch.observations[0].health_context == {"unparsed": True}
