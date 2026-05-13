from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import (
    InMemoryPetRepository,
    PetMessageService,
    PetRecord,
    UserAccount,
)


@dataclass(frozen=True)
class DemoWorkspace:
    user: UserAccount
    repository: InMemoryPetRepository
    message_service: PetMessageService


def build_demo_workspace() -> DemoWorkspace:
    repository = InMemoryPetRepository()
    user = repository.create_user(
        UserAccount(
            user_id="user_demo",
            display_name="Demo User",
            email="demo@example.com",
        )
    )
    repository.create_pet(
        _demo_pet_record(user_id=user.user_id, pet_id="dog_mochi", name="Mochi")
    )
    repository.create_pet(
        _demo_pet_record(user_id=user.user_id, pet_id="dog_bear", name="Bear")
    )
    return DemoWorkspace(
        user=user,
        repository=repository,
        message_service=PetMessageService(repository=repository),
    )


def process_demo_message(
    *,
    raw_text: str,
    pet_id: str = "dog_mochi",
    timestamp: str = "2026-05-08T09:15:00-07:00",
) -> dict[str, object]:
    workspace = build_demo_workspace()
    response = workspace.message_service.process_message(
        user_id=workspace.user.user_id,
        pet_id=pet_id,
        raw_text=raw_text,
        timestamp=timestamp,
        workflow_id="wf_demo_001",
    )
    pet = workspace.repository.get_pet(user_id=workspace.user.user_id, pet_id=pet_id)
    return {
        "response": response.model_dump(),
        "stored_observation_count": len(pet.observations),
        "stored_observation_categories": [
            observation.category for observation in pet.observations
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    raw_text = " ".join(args) if args else "Mochi barely touched breakfast."
    result = process_demo_message(raw_text=raw_text)
    print(json.dumps(result, indent=2))
    return 0


def _demo_pet_record(*, user_id: str, pet_id: str, name: str) -> PetRecord:
    return PetRecord(
        pet_id=pet_id,
        user_id=user_id,
        dog_profile=DogProfile(id=pet_id, name=name, species="dog"),
        behavioral_baseline=_demo_behavioral_baseline(),
        health_baseline=_demo_health_baseline(),
    )


def _demo_behavioral_baseline() -> BehavioralBaseline:
    return BehavioralBaseline.model_validate(
        {
            "general_temperament": "food_motivated",
            "social_profile": {
                "large_dog_reaction": "neutral",
                "small_dog_reaction": "friendly",
                "prey_drive_level": 4,
                "known_triggers": ["direct_staring"],
                "stress_signals_typical": ["lip_licking"],
            },
            "resource_guarding_profile": {
                "toy_guarding": "mild",
                "known_guarded_resources": ["high_value_chews"],
            },
        }
    )


def _demo_health_baseline() -> HealthBaseline:
    return HealthBaseline(
        normal_appetite="high",
        normal_stool_quality="firm",
        normal_activity_level="medium",
    )


if __name__ == "__main__":
    raise SystemExit(main())
