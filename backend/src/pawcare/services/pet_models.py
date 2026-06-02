from __future__ import annotations

from dataclasses import dataclass, field

from pawcare.schemas.state import (
    BehavioralBaseline,
    DogProfile,
    HealthBaseline,
    Observation,
)


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


@dataclass(frozen=True)
class DailyPetSummary:
    user_id: str
    pet_id: str
    date: str
    summary: str
    domains: list[str] = field(default_factory=list)
    active_issues: list[str] = field(default_factory=list)
    important_flags: list[str] = field(default_factory=list)
    observation_count: int = 0


@dataclass(frozen=True)
class WeeklyPetSummary:
    user_id: str
    pet_id: str
    week_start: str
    summary: str
    domains: list[str] = field(default_factory=list)
    active_issues: list[str] = field(default_factory=list)
    important_flags: list[str] = field(default_factory=list)
    observation_count: int = 0


@dataclass(frozen=True)
class MonthlyPetSummary:
    user_id: str
    pet_id: str
    month: str
    summary: str
    domains: list[str] = field(default_factory=list)
    active_issues: list[str] = field(default_factory=list)
    important_flags: list[str] = field(default_factory=list)
    observation_count: int = 0


@dataclass(frozen=True)
class DogContextSnapshot:
    user_id: str
    pet_id: str
    pet_profile: dict[str, object]
    health_baseline: dict[str, object]
    behavioral_baseline: dict[str, object]
    active_issues: list[str] = field(default_factory=list)
    recent_trends: list[str] = field(default_factory=list)
    important_historical_flags: list[str] = field(default_factory=list)
    recent_summary: str = ""
