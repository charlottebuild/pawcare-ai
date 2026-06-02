from __future__ import annotations

from pawcare.schemas.state import Observation
from pawcare.services.pet_models import PetRecord, UserAccount
from pawcare.services.pet_repository import PetRecordAccessError


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

    def update_pet(self, pet: PetRecord) -> PetRecord:
        current = self.get_pet(user_id=pet.user_id, pet_id=pet.pet_id)
        pet.observations = list(current.observations)
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
