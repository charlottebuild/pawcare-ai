from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Iterable

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import (
    InMemoryPetRepository,
    PetMessageService,
    PetRecord,
    PetRecordAccessError,
    PetRepository,
    ProfessionalReferenceService,
    ResponsePolisher,
    SemanticCareContextCache,
    SQLitePetRepository,
    SimilarCaseService,
    UserAccount,
    build_knowledge_summarizer,
    build_response_polisher,
)
from pawcare.services.knowledge_summarizer import KnowledgeSummarizer


class CreateUserRequest(BaseModel):
    user_id: str | None = None
    display_name: str | None = None
    email: str | None = None

    @field_validator("user_id")
    @classmethod
    def user_id_is_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        user_id = value.strip()
        if not user_id:
            raise ValueError("user_id must not be blank")
        return user_id


class CreatePetRequest(BaseModel):
    pet_id: str | None = None
    dog_profile: DogProfile
    behavioral_baseline: BehavioralBaseline = Field(default_factory=BehavioralBaseline)
    health_baseline: HealthBaseline = Field(default_factory=HealthBaseline)

    @field_validator("pet_id")
    @classmethod
    def pet_id_is_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
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


class RelatedCasesRequest(BaseModel):
    raw_text: str
    limit: int = Field(default=3, ge=1, le=5)

    @field_validator("raw_text")
    @classmethod
    def raw_text_is_not_blank(cls, value: str) -> str:
        raw_text = value.strip()
        if not raw_text:
            raise ValueError("raw_text must not be blank")
        return raw_text


def create_app(
    repository: PetRepository | None = None,
    similar_case_service: SimilarCaseService | None = None,
    professional_reference_service: ProfessionalReferenceService | None = None,
    knowledge_summarizer: KnowledgeSummarizer | None = None,
    response_polisher: ResponsePolisher | None = None,
    care_context_cache: SemanticCareContextCache | None = None,
) -> FastAPI:
    pet_repository = repository or InMemoryPetRepository()
    message_service = PetMessageService(repository=pet_repository)
    case_service = similar_case_service or SimilarCaseService()
    reference_service = professional_reference_service or ProfessionalReferenceService()
    summarizer = knowledge_summarizer or build_knowledge_summarizer()
    polisher = response_polisher or build_response_polisher()
    semantic_cache = (
        care_context_cache if care_context_cache is not None else SemanticCareContextCache()
    )
    app = FastAPI(title="PawCare AI API", version="0.1.0")
    _mount_web_app(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/app")

    @app.get("/app", include_in_schema=False)
    def local_app() -> FileResponse:
        return FileResponse(_web_dir() / "index.html")

    @app.post("/v1/users")
    def create_user(request: CreateUserRequest) -> dict[str, Any]:
        user_id = _resolve_user_id(request)
        user = pet_repository.create_user(
            UserAccount(
                user_id=user_id,
                display_name=request.display_name,
                email=request.email,
            )
        )
        return jsonable_encoder(user)

    @app.post("/v1/users/{user_id}/pets")
    def create_pet(user_id: str, request: CreatePetRequest) -> dict[str, Any]:
        pet_id = _resolve_pet_id(request)
        pet = pet_repository.create_pet(
            PetRecord(
                pet_id=pet_id,
                user_id=user_id,
                dog_profile=request.dog_profile.model_copy(update={"id": pet_id}),
                behavioral_baseline=request.behavioral_baseline,
                health_baseline=request.health_baseline,
            )
        )
        return _pet_detail(pet)

    @app.patch("/v1/users/{user_id}/pets/{pet_id}")
    def update_pet(user_id: str, pet_id: str, request: CreatePetRequest) -> dict[str, Any]:
        normalized_pet_id = _validate_pet_id(pet_id)
        try:
            pet = pet_repository.update_pet(
                PetRecord(
                    pet_id=normalized_pet_id,
                    user_id=user_id,
                    dog_profile=request.dog_profile.model_copy(
                        update={"id": normalized_pet_id}
                    ),
                    behavioral_baseline=request.behavioral_baseline,
                    health_baseline=request.health_baseline,
                )
            )
        except PetRecordAccessError as exc:
            raise _pet_not_found() from exc
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

    @app.post("/v1/users/{user_id}/pets/{pet_id}/related-cases")
    def find_related_cases(
        user_id: str,
        pet_id: str,
        request: RelatedCasesRequest,
    ) -> dict[str, Any]:
        pet = _get_accessible_pet(
            repository=pet_repository,
            user_id=user_id,
            pet_id=_validate_pet_id(pet_id),
        )
        matches = case_service.find_matches(
            raw_text=request.raw_text,
            pet=pet,
            recent_observations=pet.observations,
            limit=request.limit,
        )
        return {
            "disclaimer": (
                "Similar cases are supporting context, not a diagnosis. Discuss concerning "
                "signs with a veterinarian."
            ),
            "related_cases": case_service.as_payload(matches),
        }

    @app.post("/v1/users/{user_id}/pets/{pet_id}/care-context")
    def find_care_context(
        user_id: str,
        pet_id: str,
        request: RelatedCasesRequest,
    ) -> dict[str, Any]:
        pet = _get_accessible_pet(
            repository=pet_repository,
            user_id=user_id,
            pet_id=_validate_pet_id(pet_id),
        )
        return _build_care_context(
            raw_text=request.raw_text,
            pet=pet,
            limit=request.limit,
            reference_service=reference_service,
            case_service=case_service,
            summarizer=summarizer,
            cache=semantic_cache,
        )

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
        response = polisher.polish(response=response, care_context=None)
        return jsonable_encoder(response)

    @app.post("/v1/users/{user_id}/pets/{pet_id}/messages/stream")
    def create_message_stream(
        user_id: str,
        pet_id: str,
        request: CreateMessageRequest,
    ) -> StreamingResponse:
        normalized_pet_id = _validate_pet_id(pet_id)
        _get_accessible_pet(
            repository=pet_repository,
            user_id=user_id,
            pet_id=normalized_pet_id,
        )

        def event_stream() -> Iterable[str]:
            yield _sse(
                "status",
                {"stage": "received", "message": "Received your update."},
            )
            yield _sse(
                "status",
                {"stage": "loading_pet", "message": "Loading pet workspace."},
            )
            yield _sse(
                "status",
                {
                    "stage": "processing_message",
                    "message": "Checking health and behavior signals.",
                },
            )
            response = message_service.process_message(
                user_id=user_id,
                pet_id=normalized_pet_id,
                raw_text=request.raw_text,
                timestamp=request.timestamp,
                workflow_id=request.workflow_id,
            )
            yield _sse(
                "status",
                {
                    "stage": "retrieving_care_context",
                    "message": "Retrieving care context.",
                },
            )
            pet = pet_repository.get_pet(user_id=user_id, pet_id=normalized_pet_id)
            care_context = _build_care_context(
                raw_text=request.raw_text,
                pet=pet,
                limit=3,
                reference_service=reference_service,
                case_service=case_service,
                summarizer=summarizer,
                cache=semantic_cache,
            )
            yield _sse(
                "status",
                {"stage": "safety_review", "message": "Final safety review complete."},
            )
            polished_response = polisher.polish(
                response=response,
                care_context=care_context,
            )
            yield _sse(
                "final",
                {
                    "response": jsonable_encoder(polished_response),
                    "care_context": care_context,
                },
            )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app


def create_local_app(db_path: str | Path = "pawcare.local.sqlite3") -> FastAPI:
    return create_app(repository=SQLitePetRepository(db_path))


def _validate_pet_id(pet_id: str) -> str:
    normalized = pet_id.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="pet_id must not be blank")
    return normalized


def _resolve_pet_id(request: CreatePetRequest) -> str:
    candidate = request.pet_id if request.pet_id is not None else request.dog_profile.id
    return _validate_pet_id(candidate)


def _resolve_user_id(request: CreateUserRequest) -> str:
    if request.user_id is not None:
        return request.user_id
    seed = request.email or request.display_name
    if not seed:
        raise HTTPException(
            status_code=422,
            detail="email or display_name is required",
        )
    return f"user_{_slugify(seed)}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:48] or "workspace"


def _get_accessible_pet(
    *,
    repository: PetRepository,
    user_id: str,
    pet_id: str,
) -> PetRecord:
    try:
        return repository.get_pet(user_id=user_id, pet_id=pet_id)
    except PetRecordAccessError as exc:
        raise _pet_not_found() from exc


def _pet_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Pet record is not available.")


def _build_care_context(
    *,
    raw_text: str,
    pet: PetRecord,
    limit: int,
    reference_service: ProfessionalReferenceService,
    case_service: SimilarCaseService,
    summarizer: KnowledgeSummarizer,
    cache: SemanticCareContextCache | None = None,
) -> dict[str, Any]:
    lookup = (
        cache.get(raw_text=raw_text, pet=pet, limit=limit)
        if cache is not None
        else None
    )
    if lookup is not None and lookup.hit:
        return lookup.payload or {}
    professional_matches = reference_service.find_matches(
        raw_text=raw_text,
        pet=pet,
        recent_observations=pet.observations,
        limit=limit,
    )
    case_matches = case_service.find_matches(
        raw_text=raw_text,
        pet=pet,
        recent_observations=pet.observations,
        limit=limit,
    )
    payload = _care_context_payload(
        professional_payload=reference_service.as_payload(professional_matches),
        case_payload=case_service.as_payload(case_matches),
        raw_text=raw_text,
        pet=pet,
        summarizer=summarizer,
    )
    payload["cache_status"] = "miss"
    if cache is not None:
        cache.set(
            key=lookup.key if lookup is not None else None,
            payload=payload,
        )
    return payload


def _care_context_payload(
    *,
    professional_payload: list[dict[str, object]],
    case_payload: list[dict[str, object]],
    raw_text: str,
    pet: PetRecord,
    summarizer: KnowledgeSummarizer,
) -> dict[str, Any]:
    context_summary = summarizer.summarize(
        matches=professional_payload + case_payload,
        raw_text=raw_text,
        pet_context={
            "pet_id": pet.pet_id,
            "name": pet.dog_profile.name,
            "species": pet.dog_profile.species,
            "breed": pet.dog_profile.breed,
        },
    )
    return {
        "non_diagnostic_notice": (
            "Professional references and similar cases are supporting context, not a "
            "diagnosis. Discuss concerning signs with a veterinarian."
        ),
        "context_summary": context_summary,
        "professional_references": professional_payload,
        "related_cases": case_payload,
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _pet_summary(pet: PetRecord) -> dict[str, Any]:
    return {
        "pet_id": pet.pet_id,
        "name": pet.dog_profile.name,
        "species": pet.dog_profile.species,
        "avatar": _pet_avatar(pet),
        "avatar_image": _pet_avatar_image(pet),
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


def _pet_avatar(pet: PetRecord) -> str | None:
    for note in pet.dog_profile.care_notes:
        if note.startswith("avatar:"):
            return note.removeprefix("avatar:")
    return None


def _pet_avatar_image(pet: PetRecord) -> str | None:
    for note in pet.dog_profile.care_notes:
        if note.startswith("avatar_image:"):
            return note.removeprefix("avatar_image:")
    return None


def _mount_web_app(app: FastAPI) -> None:
    app.mount(
        "/app/static",
        StaticFiles(directory=_web_dir()),
        name="pawcare_app_static",
    )


def _web_dir() -> Path:
    return Path(__file__).parent / "web"
