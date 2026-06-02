from pawcare.schemas.state import Species
from pawcare.services import BehaviorReferenceService
from pawcare.skills import LogExtractor


def test_matches_resource_stress_behavior_reference() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi froze and licked her lips when the large dog came near her chew.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    matches = BehaviorReferenceService().find_matches(
        observations=batch.observations,
    )

    assert matches
    assert matches[0].domain == "resource_guarding"
    assert "resource_guarding" in matches[0].matched_signals
    assert "Merck Veterinary Manual" in matches[0].source_name
    assert matches[0].management_notes


def test_matches_cat_stress_behavior_reference() -> None:
    batch = LogExtractor().extract(
        dog_id="cat_123",
        raw_text="Miso's tail puffed up and her ears flattened when the dog approached.",
        timestamp="2026-05-08T09:15:00-07:00",
        species=Species.cat,
    )

    matches = BehaviorReferenceService().find_matches(
        observations=batch.observations,
    )

    assert matches
    assert any(match.domain == "cat_stress" for match in matches)


def test_behavior_references_include_history_context() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi froze, turned away, and licked her lips when the larger dog approached.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    matches = BehaviorReferenceService().find_matches(
        observations=batch.observations,
    )

    assert any("Diagnosing Behavior Problems" in match.source_name for match in matches)


def test_no_social_observation_returns_no_behavior_references() -> None:
    batch = LogExtractor().extract(
        dog_id="dog_123",
        raw_text="Mochi ate breakfast normally.",
        timestamp="2026-05-08T09:15:00-07:00",
    )

    assert BehaviorReferenceService().find_matches(observations=batch.observations) == []
