import pytest

from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import (
    PetMessageService,
    PetRecord,
    PetRecordAccessError,
    SQLitePetRepository,
    SummaryWorker,
    UserAccount,
)


def _dog_profile(pet_id: str, name: str) -> DogProfile:
    return DogProfile(id=pet_id, name=name, species="dog")


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


def _pet_record(*, user_id: str, pet_id: str, name: str) -> PetRecord:
    return PetRecord(
        pet_id=pet_id,
        user_id=user_id,
        dog_profile=_dog_profile(pet_id=pet_id, name=name),
        behavioral_baseline=_behavioral_baseline(),
        health_baseline=_health_baseline(),
    )


def test_sqlite_repository_persists_user_and_pet_records(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    repository.create_user(UserAccount(user_id="user_123", display_name="Charlotte"))
    repository.create_pet(
        _pet_record(user_id="user_123", pet_id="dog_mochi", name="Mochi")
    )
    repository.create_pet(
        _pet_record(user_id="user_123", pet_id="dog_bear", name="Bear")
    )

    reopened = SQLitePetRepository(db_path)
    pets = reopened.list_pets(user_id="user_123")

    assert [pet.pet_id for pet in pets] == ["dog_mochi", "dog_bear"]
    assert [pet.dog_profile.name for pet in pets] == ["Mochi", "Bear"]
    assert [len(pet.observations) for pet in pets] == [0, 0]


def test_sqlite_repository_restores_pet_baselines_and_observations(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    repository.create_pet(
        _pet_record(user_id="user_123", pet_id="dog_mochi", name="Mochi")
    )
    PetMessageService(repository=repository).process_message(
        user_id="user_123",
        pet_id="dog_mochi",
        raw_text="Mochi barely touched breakfast.",
        timestamp="2026-05-08T08:00:00-07:00",
        workflow_id="wf_sqlite_001",
    )

    reopened = SQLitePetRepository(db_path)
    pet = reopened.get_pet(user_id="user_123", pet_id="dog_mochi")

    assert pet.dog_profile.name == "Mochi"
    assert pet.behavioral_baseline.general_temperament == "food_motivated"
    assert pet.health_baseline.normal_appetite == "high"
    assert len(pet.observations) == 1
    assert pet.observations[0].category == "food_intake"
    assert pet.observations[0].raw_text == "Mochi barely touched breakfast."


def test_sqlite_repository_persists_high_risk_message_observations(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    repository.create_pet(
        _pet_record(user_id="user_123", pet_id="dog_mochi", name="Mochi")
    )

    response = PetMessageService(repository=repository).process_message(
        user_id="user_123",
        pet_id="dog_mochi",
        raw_text="After taking Rimadyl pain medication, Mochi had bloody stool.",
        timestamp="2026-05-08T09:15:00-07:00",
        workflow_id="wf_sqlite_002",
    )

    reopened = SQLitePetRepository(db_path)
    pet = reopened.get_pet(user_id="user_123", pet_id="dog_mochi")
    categories = [observation.category for observation in pet.observations]
    assert response.status == "escalate"
    assert categories == ["stool", "medication_note"]


def test_sqlite_repository_raises_unified_access_error_without_appending(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    repository.create_pet(
        _pet_record(user_id="user_456", pet_id="dog_luna", name="Luna")
    )
    before = len(repository.get_pet(user_id="user_456", pet_id="dog_luna").observations)

    with pytest.raises(PetRecordAccessError):
        repository.get_pet(user_id="user_123", pet_id="dog_luna")

    with pytest.raises(PetRecordAccessError):
        repository.append_observations(
            user_id="user_123",
            pet_id="dog_luna",
            observations=[],
        )

    after = len(repository.get_pet(user_id="user_456", pet_id="dog_luna").observations)
    assert after == before


def test_sqlite_repository_persists_pet_memory_summaries(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    repository.create_pet(
        _pet_record(user_id="user_123", pet_id="dog_mochi", name="Mochi")
    )
    PetMessageService(repository=repository).process_message(
        user_id="user_123",
        pet_id="dog_mochi",
        raw_text="Mochi had bloody stool after breakfast.",
        timestamp="2026-05-08T09:15:00-07:00",
        workflow_id="wf_sqlite_memory_001",
    )
    SummaryWorker().rebuild_for_pet(
        repository=repository,
        user_id="user_123",
        pet_id="dog_mochi",
    )

    reopened = SQLitePetRepository(db_path)
    daily = reopened.get_daily_summaries(user_id="user_123", pet_id="dog_mochi")
    snapshot = reopened.get_context_snapshot(user_id="user_123", pet_id="dog_mochi")

    assert len(daily) == 1
    assert daily[0].date == "2026-05-08"
    assert "bloody stool" in daily[0].active_issues
    assert "bloody stool" in snapshot.active_issues
    assert snapshot.pet_profile["name"] == "Mochi"
