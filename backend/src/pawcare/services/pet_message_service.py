from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pawcare.schemas.state import (
    BehavioralBaseline,
    DogProfile,
    HealthBaseline,
    Observation,
    UserResponse,
)
from pawcare.services.log_processing_service import LogProcessingService


class PetRecordAccessError(Exception):
    """Raised when a pet record is missing or inaccessible to the user."""


@dataclass(frozen=True)
class UserAccount:
    user_id: str
    display_name: str | None = None
    email: str | None = None


@dataclass
class PetRecord:
    pet_id: str
    user_id: str
    dog_profile: DogProfile
    behavioral_baseline: BehavioralBaseline
    health_baseline: HealthBaseline
    observations: list[Observation] = field(default_factory=list)


class PetRepository(Protocol):
    def create_user(self, user: UserAccount) -> UserAccount: ...

    def create_pet(self, pet: PetRecord) -> PetRecord: ...

    def list_pets(self, *, user_id: str) -> list[PetRecord]: ...

    def get_pet(self, *, user_id: str, pet_id: str) -> PetRecord: ...

    def append_observations(
        self,
        *,
        user_id: str,
        pet_id: str,
        observations: list[Observation],
    ) -> PetRecord: ...


class InMemoryPetRepository:
    """In-memory product workspace store for users and their pet records."""

    def __init__(self) -> None:
        self._users: dict[str, UserAccount] = {}
        self._pets: dict[tuple[str, str], PetRecord] = {}

    def create_user(self, user: UserAccount) -> UserAccount:
        self._users[user.user_id] = user
        return user

    def create_pet(self, pet: PetRecord) -> PetRecord:
        if pet.user_id not in self._users:
            self.create_user(UserAccount(user_id=pet.user_id))
        self._pets[(pet.user_id, pet.pet_id)] = pet
        return pet

    def list_pets(self, *, user_id: str) -> list[PetRecord]:
        return [
            pet
            for (owner_id, _), pet in self._pets.items()
            if owner_id == user_id
        ]

    def get_pet(self, *, user_id: str, pet_id: str) -> PetRecord:
        try:
            return self._pets[(user_id, pet_id)]
        except KeyError as exc:
            raise PetRecordAccessError("Pet record is not available.") from exc

    def append_observations(
        self,
        *,
        user_id: str,
        pet_id: str,
        observations: list[Observation],
    ) -> PetRecord:
        pet = self.get_pet(user_id=user_id, pet_id=pet_id)
        pet.observations.extend(observations)
        return pet


class PetMessageService:
    """App-facing entry point for user messages about a specific pet."""

    def __init__(
        self,
        *,
        repository: PetRepository | None = None,
        log_processing_service: LogProcessingService | None = None,
    ) -> None:
        self.repository = repository or InMemoryPetRepository()
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
