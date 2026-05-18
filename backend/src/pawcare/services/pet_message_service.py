from __future__ import annotations

from pawcare.schemas.state import UserResponse
from pawcare.services.log_processing_service import LogProcessingService
from pawcare.services.pet_models import PetRecord
from pawcare.services.pet_repository import PetRepository


class PetMessageService:
    """App-facing entry point for user messages about a specific pet."""

    def __init__(
        self,
        *,
        repository: PetRepository,
        log_processing_service: LogProcessingService | None = None,
    ) -> None:
        self.repository = repository
        self.log_processing_service = log_processing_service or LogProcessingService()

    def process_message(
        self,
        *,
        user_id: str,
        pet_id: str,
        raw_text: str,
        timestamp: str,
        workflow_id: str | None = None,
    ) -> UserResponse:
        pet = self.repository.get_pet(user_id=user_id, pet_id=pet_id)
        log_result = self.log_processing_service.process_log(
            workflow_id=workflow_id
            or self._workflow_id(user_id=user_id, pet_id=pet_id, pet=pet),
            dog_id=pet.pet_id,
            raw_text=raw_text,
            timestamp=timestamp,
            dog_profile=pet.dog_profile,
            behavioral_baseline=pet.behavioral_baseline,
            health_baseline=pet.health_baseline,
            species=pet.dog_profile.species,
        )
        self.repository.append_observations(
            user_id=user_id,
            pet_id=pet_id,
            observations=list(log_result.coordinator_result.state.observations),
        )
        return log_result.response

    def _workflow_id(self, *, user_id: str, pet_id: str, pet: PetRecord) -> str:
        return f"wf_{user_id}_{pet_id}_{len(pet.observations) + 1:03d}"
