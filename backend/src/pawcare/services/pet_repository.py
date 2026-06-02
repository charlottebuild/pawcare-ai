from __future__ import annotations

from typing import Protocol

from pawcare.schemas.state import Observation
from pawcare.services.pet_models import (
    DailyPetSummary,
    DogContextSnapshot,
    MonthlyPetSummary,
    PetRecord,
    UserAccount,
    WeeklyPetSummary,
)


class PetRecordAccessError(Exception):
    """Raised when a pet record is missing or inaccessible to the user."""


class PetRepository(Protocol):
    def create_user(self, user: UserAccount) -> UserAccount: ...

    def create_pet(self, pet: PetRecord) -> PetRecord: ...

    def update_pet(self, pet: PetRecord) -> PetRecord: ...

    def list_pets(self, *, user_id: str) -> list[PetRecord]: ...

    def get_pet(self, *, user_id: str, pet_id: str) -> PetRecord: ...

    def append_observations(
        self,
        *,
        user_id: str,
        pet_id: str,
        observations: list[Observation],
    ) -> PetRecord: ...

    def save_daily_summaries(
        self, *, user_id: str, pet_id: str, summaries: list[DailyPetSummary]
    ) -> None: ...

    def save_weekly_summaries(
        self, *, user_id: str, pet_id: str, summaries: list[WeeklyPetSummary]
    ) -> None: ...

    def save_monthly_summaries(
        self, *, user_id: str, pet_id: str, summaries: list[MonthlyPetSummary]
    ) -> None: ...

    def get_daily_summaries(self, *, user_id: str, pet_id: str) -> list[DailyPetSummary]: ...

    def get_weekly_summaries(self, *, user_id: str, pet_id: str) -> list[WeeklyPetSummary]: ...

    def get_monthly_summaries(self, *, user_id: str, pet_id: str) -> list[MonthlyPetSummary]: ...

    def get_context_snapshot(
        self, *, user_id: str, pet_id: str
    ) -> DogContextSnapshot: ...
