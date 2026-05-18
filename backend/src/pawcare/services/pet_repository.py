from __future__ import annotations

from typing import Protocol

from pawcare.schemas.state import Observation
from pawcare.services.pet_models import PetRecord, UserAccount


class PetRecordAccessError(Exception):
    """Raised when a pet record is missing or inaccessible to the user."""


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
