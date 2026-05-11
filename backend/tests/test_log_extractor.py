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
