from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, field_validator

from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import (
    InMemoryPetRepository,
    PetMessageService,
    PetRecord,
    PetRecordAccessError,
    UserAccount,
)


class CreateUserRequest(BaseModel):
    user_id: str
    display_name: str | None = None
    email: str | None = None


class CreatePetRequest(BaseModel):
    pet_id: str
    dog_profile: DogProfile
    behavioral_baseline: BehavioralBaseline = Field(default_factory=BehavioralBaseline)
    health_baseline: HealthBaseline = Field(default_factory=HealthBaseline)

    @field_validator("pet_id")
    @classmethod
    def pet_id_is_not_blank(cls, value: str) -> str:
        pet_id = value.strip()
        if not pet_id:
            raise ValueError("pet_id must not be blank")
        return pet_id


class CreateMessageRequest(BaseModel):
    raw_text: str
    timestamp: str
    workflow_id: str | None = None

    @field_validator("raw_text")
    @classmethod
    def raw_text_is_not_blank(cls, value: str) -> str:
        raw_text = value.strip()
        if not raw_text:
            raise ValueError("raw_text must not be blank")
        return raw_text

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_iso_like(cls, value: str) -> str:
        timestamp = value.strip()
        if not timestamp:
            raise ValueError("timestamp must not be blank")
        normalized_timestamp = (
            timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
        )
        try:
            datetime.fromisoformat(normalized_timestamp)
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-like") from exc
        return timestamp


def create_app(repository: InMemoryPetRepository | None = None) -> FastAPI:
    pet_repository = repository or InMemoryPetRepository()
    message_service = PetMessageService(repository=pet_repository)
    app = FastAPI(title="PawCare AI API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/users")
    def create_user(request: CreateUserRequest) -> dict[str, Any]:
        user = pet_repository.create_user(
            UserAccount(
                user_id=request.user_id,
                display_name=request.display_name,
                email=request.email,
            )
        )
        return jsonable_encoder(user)

    @app.post("/v1/users/{user_id}/pets")
    def create_pet(user_id: str, request: CreatePetRequest) -> dict[str, Any]:
        pet = pet_repository.create_pet(
            PetRecord(
                pet_id=request.pet_id,
                user_id=user_id,
                dog_profile=request.dog_profile,
                behavioral_baseline=request.behavioral_baseline,
                health_baseline=request.health_baseline,
            )
        )
        return _pet_detail(pet)

    @app.get("/v1/users/{user_id}/pets")
    def list_pets(user_id: str) -> dict[str, list[dict[str, Any]]]:
        pets = pet_repository.list_pets(user_id=user_id)
        return {"pets": [_pet_summary(pet) for pet in pets]}

    @app.get("/v1/users/{user_id}/pets/{pet_id}")
    def get_pet(user_id: str, pet_id: str) -> dict[str, Any]:
        pet = _get_accessible_pet(
            repository=pet_repository,
            user_id=user_id,
            pet_id=_validate_pet_id(pet_id),
        )
        return _pet_detail(pet)

    @app.get("/v1/users/{user_id}/pets/{pet_id}/observations")
    def list_observations(user_id: str, pet_id: str) -> dict[str, list[dict[str, Any]]]:
        pet = _get_accessible_pet(
            repository=pet_repository,
            user_id=user_id,
            pet_id=_validate_pet_id(pet_id),
        )
        return {
            "observations": [
                jsonable_encoder(observation) for observation in pet.observations
            ]
        }

    @app.post("/v1/users/{user_id}/pets/{pet_id}/messages")
    def create_message(
        user_id: str,
        pet_id: str,
        request: CreateMessageRequest,
    ) -> dict[str, Any]:
        try:
            response = message_service.process_message(
                user_id=user_id,
                pet_id=_validate_pet_id(pet_id),
                raw_text=request.raw_text,
                timestamp=request.timestamp,
                workflow_id=request.workflow_id,
            )
        except PetRecordAccessError as exc:
            raise _pet_not_found() from exc
        return jsonable_encoder(response)

    return app


def _validate_pet_id(pet_id: str) -> str:
    normalized = pet_id.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="pet_id must not be blank")
    return normalized


def _get_accessible_pet(
    *,
    repository: InMemoryPetRepository,
    user_id: str,
    pet_id: str,
) -> PetRecord:
    try:
        return repository.get_pet(user_id=user_id, pet_id=pet_id)
    except PetRecordAccessError as exc:
        raise _pet_not_found() from exc


def _pet_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Pet record is not available.")


def _pet_summary(pet: PetRecord) -> dict[str, Any]:
    return {
        "pet_id": pet.pet_id,
        "name": pet.dog_profile.name,
        "observation_count": len(pet.observations),
    }


def _pet_detail(pet: PetRecord) -> dict[str, Any]:
    return {
        "pet_id": pet.pet_id,
        "user_id": pet.user_id,
        "dog_profile": jsonable_encoder(pet.dog_profile),
        "behavioral_baseline": jsonable_encoder(pet.behavioral_baseline),
        "health_baseline": jsonable_encoder(pet.health_baseline),
        "observation_count": len(pet.observations),
    }
