from __future__ import annotations

from pawcare.schemas.state import Observation
from pawcare.services.pet_models import (
    CareRoutine,
    DailyPetSummary,
    DogContextSnapshot,
    MonthlyPetSummary,
    PetRecord,
    UserAccount,
    WeeklyPetSummary,
)
from pawcare.services.pet_repository import PetRecordAccessError


class InMemoryPetRepository:
    """In-memory product workspace store for users and their pet records."""

    def __init__(self) -> None:
        self._users: dict[str, UserAccount] = {}
        self._pets: dict[tuple[str, str], PetRecord] = {}
        self._daily_summaries: dict[tuple[str, str], list[DailyPetSummary]] = {}
        self._weekly_summaries: dict[tuple[str, str], list[WeeklyPetSummary]] = {}
        self._monthly_summaries: dict[tuple[str, str], list[MonthlyPetSummary]] = {}
        self._care_routines: dict[tuple[str, str], list[CareRoutine]] = {}

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

    def save_care_routines(
        self, *, user_id: str, pet_id: str, routines: list[CareRoutine]
    ) -> None:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        self._care_routines[(user_id, pet_id)] = list(routines)

    def list_care_routines(self, *, user_id: str, pet_id: str) -> list[CareRoutine]:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        return list(self._care_routines.get((user_id, pet_id), []))

    def save_daily_summaries(
        self, *, user_id: str, pet_id: str, summaries: list[DailyPetSummary]
    ) -> None:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        self._daily_summaries[(user_id, pet_id)] = list(summaries)

    def save_weekly_summaries(
        self, *, user_id: str, pet_id: str, summaries: list[WeeklyPetSummary]
    ) -> None:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        self._weekly_summaries[(user_id, pet_id)] = list(summaries)

    def save_monthly_summaries(
        self, *, user_id: str, pet_id: str, summaries: list[MonthlyPetSummary]
    ) -> None:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        self._monthly_summaries[(user_id, pet_id)] = list(summaries)

    def get_daily_summaries(self, *, user_id: str, pet_id: str) -> list[DailyPetSummary]:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        return list(self._daily_summaries.get((user_id, pet_id), []))

    def get_weekly_summaries(self, *, user_id: str, pet_id: str) -> list[WeeklyPetSummary]:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        return list(self._weekly_summaries.get((user_id, pet_id), []))

    def get_monthly_summaries(self, *, user_id: str, pet_id: str) -> list[MonthlyPetSummary]:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        return list(self._monthly_summaries.get((user_id, pet_id), []))

    def get_context_snapshot(self, *, user_id: str, pet_id: str) -> DogContextSnapshot:
        pet = self.get_pet(user_id=user_id, pet_id=pet_id)
        daily = self.get_daily_summaries(user_id=user_id, pet_id=pet_id)
        weekly = self.get_weekly_summaries(user_id=user_id, pet_id=pet_id)
        monthly = self.get_monthly_summaries(user_id=user_id, pet_id=pet_id)
        active_issues = [issue for summary in daily[-3:] for issue in summary.active_issues]
        recent_trends = [summary.summary for summary in weekly[-2:] or daily[-3:]]
        flags = [
            flag
            for summary in [*monthly[-3:], *weekly[-4:], *daily[-7:]]
            for flag in summary.important_flags
        ]
        return DogContextSnapshot(
            user_id=user_id,
            pet_id=pet_id,
            pet_profile=pet.dog_profile.model_dump(),
            health_baseline=pet.health_baseline.model_dump(),
            behavioral_baseline=pet.behavioral_baseline.model_dump(),
            active_issues=sorted(set(active_issues)),
            recent_trends=recent_trends,
            important_historical_flags=sorted(set(flags)),
            recent_summary=" ".join(recent_trends[:3]),
        )
