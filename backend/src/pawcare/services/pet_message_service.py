from __future__ import annotations

from pawcare.schemas.state import Observation, ObservationCategory, UserResponse
from pawcare.services.log_processing_service import LogProcessingService
from pawcare.services.pet_models import PetRecord
from pawcare.services.pet_repository import PetRepository
from pawcare.services.pet_summary_worker import SummaryWorker


class PetMessageService:
    """App-facing entry point for user messages about a specific pet."""

    def __init__(
        self,
        *,
        repository: PetRepository,
        log_processing_service: LogProcessingService | None = None,
        summary_worker: SummaryWorker | None = None,
    ) -> None:
        self.repository = repository
        self.log_processing_service = log_processing_service or LogProcessingService()
        self.summary_worker = summary_worker or SummaryWorker()

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
        snapshot = self.repository.get_context_snapshot(user_id=user_id, pet_id=pet_id)
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
            dog_context_snapshot=snapshot,
        )
        observations_to_append = self._dedupe_meal_observations(
            existing_observations=pet.observations,
            new_observations=list(log_result.coordinator_result.state.observations),
        )
        self.repository.append_observations(
            user_id=user_id,
            pet_id=pet_id,
            observations=observations_to_append,
        )
        self.summary_worker.rebuild_for_pet(
            repository=self.repository,
            user_id=user_id,
            pet_id=pet_id,
        )
        return log_result.response

    def _workflow_id(self, *, user_id: str, pet_id: str, pet: PetRecord) -> str:
        return f"wf_{user_id}_{pet_id}_{len(pet.observations) + 1:03d}"

    def _dedupe_meal_observations(
        self,
        *,
        existing_observations: list[Observation],
        new_observations: list[Observation],
    ) -> list[Observation]:
        existing_meals = {
            (self._date_key(observation.timestamp), meal)
            for observation in existing_observations
            if observation.category == ObservationCategory.food_intake
            for meal in [self._meal_keyword(observation.raw_text)]
            if meal
        }
        kept: list[Observation] = []
        for observation in new_observations:
            if observation.category != ObservationCategory.food_intake:
                kept.append(observation)
                continue
            meal = self._meal_keyword(observation.raw_text)
            key = (self._date_key(observation.timestamp), meal)
            if meal and key in existing_meals:
                continue
            if meal:
                existing_meals.add(key)
            kept.append(observation)
        return kept

    def _date_key(self, timestamp: str | None) -> str:
        return str(timestamp or "")[:10]

    def _meal_keyword(self, value: str) -> str:
        normalized = value.lower()
        if "breakfast" in normalized:
            return "breakfast"
        if "lunch" in normalized:
            return "lunch"
        if "dinner" in normalized:
            return "dinner"
        return ""
