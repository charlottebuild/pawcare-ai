import pytest

from pawcare.schemas.state import (
    BehavioralBaseline,
    DogProfile,
    HealthBaseline,
    ObservationCategory,
)
from pawcare.services import (
    InMemoryPetRepository,
    PetMessageService,
    PetRecord,
    PetRecordAccessError,
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


def _service_with_two_pets() -> tuple[PetMessageService, InMemoryPetRepository]:
    repository = InMemoryPetRepository()
    repository.create_user(UserAccount(user_id="user_123", display_name="Charlotte"))
    repository.create_pet(
        _pet_record(user_id="user_123", pet_id="dog_mochi", name="Mochi")
    )
    repository.create_pet(
        _pet_record(user_id="user_123", pet_id="dog_bear", name="Bear")
    )
    return PetMessageService(repository=repository), repository


def test_pet_message_service_appends_observations_only_to_target_pet() -> None:
    service, repository = _service_with_two_pets()

    response = service.process_message(
        user_id="user_123",
        pet_id="dog_mochi",
        raw_text="Mochi barely touched breakfast.",
        timestamp="2026-05-08T08:00:00-07:00",
        workflow_id="wf_product_001",
    )

    mochi = repository.get_pet(user_id="user_123", pet_id="dog_mochi")
    bear = repository.get_pet(user_id="user_123", pet_id="dog_bear")
    assert response.status == "attention_needed"
    assert response.dog_id == "dog_mochi"
    assert "GL_APPETITE_002" in response.source_guideline_ids
    assert [observation.category for observation in mochi.observations] == [
        ObservationCategory.food_intake
    ]
    assert bear.observations == []
    assert "proposed_update" not in response.model_dump()
    assert "agent_outputs" not in response.model_dump()


def test_pet_message_service_records_safe_update_without_internal_fields() -> None:
    service, repository = _service_with_two_pets()

    response = service.process_message(
        user_id="user_123",
        pet_id="dog_mochi",
        raw_text="Mochi had a quiet afternoon.",
        timestamp="2026-05-08T15:00:00-07:00",
        workflow_id="wf_product_002",
    )

    mochi = repository.get_pet(user_id="user_123", pet_id="dog_mochi")
    assert response.status == "updated"
    assert response.risk_band == "low"
    assert "updated" in response.message.lower()
    assert response.escalation_conditions == []
    assert len(mochi.observations) == 1
    assert mochi.observations[0].category == ObservationCategory.other
    assert mochi.observations[0].raw_text == "Mochi had a quiet afternoon."
    assert "proposed_update" not in response.model_dump()
    assert "agent_outputs" not in response.model_dump()


def test_pet_message_service_returns_escalate_for_high_risk_health_update() -> None:
    service, repository = _service_with_two_pets()

    response = service.process_message(
        user_id="user_123",
        pet_id="dog_mochi",
        raw_text="After taking Rimadyl pain medication, Mochi had bloody stool.",
        timestamp="2026-05-08T09:15:00-07:00",
        workflow_id="wf_product_003",
    )

    mochi = repository.get_pet(user_id="user_123", pet_id="dog_mochi")
    categories = [observation.category for observation in mochi.observations]
    assert response.status == "escalate"
    assert response.risk_band == "high"
    assert response.escalation_conditions
    assert "GL_NSAID_SIDE_EFFECT_001" in response.source_guideline_ids
    assert "dose" not in response.message.lower()
    assert "dosage" not in response.message.lower()
    assert ObservationCategory.stool in categories
    assert ObservationCategory.medication_note in categories


def test_pet_message_service_raises_unified_access_error_without_appending() -> None:
    service, repository = _service_with_two_pets()
    repository.create_user(UserAccount(user_id="user_456", display_name="Other Owner"))
    repository.create_pet(
        _pet_record(user_id="user_456", pet_id="dog_luna", name="Luna")
    )
    before = {
        pet.pet_id: len(pet.observations)
        for pet in repository.list_pets(user_id="user_123")
    }
    other_before = len(
        repository.get_pet(user_id="user_456", pet_id="dog_luna").observations
    )

    with pytest.raises(PetRecordAccessError):
        service.process_message(
            user_id="user_123",
            pet_id="dog_not_owned_by_user",
            raw_text="Barely ate breakfast.",
            timestamp="2026-05-08T08:00:00-07:00",
            workflow_id="wf_product_004",
        )

    with pytest.raises(PetRecordAccessError):
        service.process_message(
            user_id="user_123",
            pet_id="dog_luna",
            raw_text="Luna barely ate breakfast.",
            timestamp="2026-05-08T08:00:00-07:00",
            workflow_id="wf_product_005",
        )

    after = {
        pet.pet_id: len(pet.observations)
        for pet in repository.list_pets(user_id="user_123")
    }
    other_after = len(
        repository.get_pet(user_id="user_456", pet_id="dog_luna").observations
    )
    assert after == before
    assert other_after == other_before
