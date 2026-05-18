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
