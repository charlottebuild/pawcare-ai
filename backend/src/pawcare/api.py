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
    domain = _care_context_domain(
        professional_payload=professional_payload,
        raw_text=raw_text,
    )
    professional_payload = _prioritize_professional_payload(
        professional_payload,
        domain=domain,
    )
    case_payload = _prioritize_case_payload(
        case_payload,
        domain=domain,
    )
    summary_matches = professional_payload[:1] + case_payload[:1]
    context_summary = summarizer.summarize(
        matches=summary_matches,
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
        "screening_checklist": _screening_checklist_payload(
            professional_payload=professional_payload,
            case_payload=case_payload,
            raw_text=raw_text,
            domain=domain,
        ),
        "professional_references": professional_payload,
        "related_cases": case_payload,
    }


def _screening_checklist_payload(
    *,
    professional_payload: list[dict[str, object]],
    case_payload: list[dict[str, object]],
    raw_text: str,
    domain: str | None = None,
) -> dict[str, object] | None:
    if not professional_payload and not case_payload:
        return None
    domain = domain or _care_context_domain(professional_payload=professional_payload, raw_text=raw_text)
    if domain is None:
        return None
    checklists = {
        "oral_neck": {
            "possible_domain": "oral_neck",
            "symptom_checklist": [
                "swelling under the jaw, chin, neck, mouth, or tongue",
                "drooling or wet fur around the mouth",
                "trouble eating, chewing, or swallowing",
                "pain when the mouth or neck area is touched",
                "rapid growth, bleeding, breathing changes, or low energy",
            ],
            "questions_to_ask_user": [
                "Where exactly is the swelling or lump?",
                "Is it soft, firm, movable, painful, or growing quickly?",
                "Any drooling, head withdrawal while eating, swallowing changes, or breathing changes?",
            ],
            "safe_next_steps": [
                "Record location, size, firmness, growth speed, photos, eating changes, and drooling.",
                "Discuss these signs with a veterinarian; seek prompt care if breathing, swallowing, pain, bleeding, or rapid growth appears.",
            ],
        },
        "gi": {
            "possible_domain": "gi",
            "symptom_checklist": [
                "vomiting frequency",
                "diarrhea, blood, or black/tarry stool",
                "low appetite, low energy, dehydration signs, or medication exposure",
            ],
            "questions_to_ask_user": [
                "How many times did vomiting or diarrhea happen?",
                "Any blood, black/tarry stool, refusal to drink, or low energy?",
            ],
            "safe_next_steps": [
                "Record stool quality, vomiting frequency, appetite, water intake, energy, medications, and possible exposures.",
                "Contact a veterinarian promptly if blood, black stool, repeated vomiting, dehydration, or low energy appears.",
            ],
        },
        "urinary": {
            "possible_domain": "urinary",
            "symptom_checklist": [
                "straining with little or no urine",
                "blood in urine",
                "frequent litter box or potty trips",
                "pain, vomiting, low energy, or not eating",
            ],
            "questions_to_ask_user": [
                "Is urine actually passing, and how much?",
                "Any blood, straining, pain, vomiting, or low energy?",
            ],
            "safe_next_steps": [
                "Record frequency, amount, straining, blood, accidents, water intake, and whether urine passes.",
                "Seek urgent veterinary care if the pet cannot urinate or repeatedly strains with little or no urine.",
            ],
        },
        "mobility": {
            "possible_domain": "mobility",
            "symptom_checklist": [
                "limping or not bearing weight",
                "pain, swelling, sudden worsening, or post-op changes",
                "reluctance during prescribed rehab exercises",
            ],
            "questions_to_ask_user": [
                "Which limb is affected, and can the pet bear weight?",
                "Any recent surgery, injury, swelling, pain, or sudden worsening?",
            ],
            "safe_next_steps": [
                "Record affected limb, weight-bearing ability, pain signs, swelling, recent activity, and surgery context.",
                "Follow the veterinarian's rehab plan and contact the surgical vet if mobility worsens or pain appears.",
            ],
        },
        "skin_lump": {
            "possible_domain": "skin_lump",
            "symptom_checklist": [
                "new lump, bump, swelling, redness, discharge, bleeding, or itching",
                "rapid growth, pain, warmth, or behavior change",
            ],
            "questions_to_ask_user": [
                "Where is the lump and how large is it?",
                "Is it changing quickly, painful, bleeding, discharging, or itchy?",
            ],
            "safe_next_steps": [
                "Record size, location, color, texture, photos, itchiness, pain, discharge, and growth speed.",
                "Discuss changes with a veterinarian, especially if rapid growth, bleeding, discharge, or pain appears.",
            ],
        },
        "respiratory": {
            "possible_domain": "respiratory",
            "symptom_checklist": [
                "breathing effort, coughing, wheezing, rapid breathing, or gum color changes",
                "collapse, low energy, or worsening distress",
            ],
            "questions_to_ask_user": [
                "Is breathing hard, noisy, fast, or labored?",
                "Any blue or pale gums, collapse, low energy, or worsening signs?",
            ],
            "safe_next_steps": [
                "Record cough timing, frequency, triggers, resting breathing rate, gum color, energy, and appetite.",
                "Seek urgent veterinary care for labored breathing, blue/pale gums, collapse, or severe distress.",
            ],
        },
    }
    return {
        "source": "deterministic_screening_fallback",
        "non_diagnostic_notice": "This checklist supports triage discussion only; it is not a diagnosis.",
        **checklists[domain],
    }


def _prioritize_professional_payload(
    payload: list[dict[str, object]],
    *,
    domain: str | None,
) -> list[dict[str, object]]:
    if domain is None:
        return payload
    return sorted(
        payload,
        key=lambda item: (
            0 if str(item.get("domain") or "") == domain else 1,
            str(item.get("source_name") or ""),
        ),
    )


def _prioritize_case_payload(
    payload: list[dict[str, object]],
    *,
    domain: str | None,
) -> list[dict[str, object]]:
    if domain is None:
        return payload
    return sorted(
        payload,
        key=lambda item: (
            0 if _case_matches_domain(item, domain=domain) else 1,
            str(item.get("title") or ""),
        ),
    )


def _case_matches_domain(item: dict[str, object], *, domain: str) -> bool:
    domain_terms = {
        "oral_neck": {"oral_mass", "salivary_gland", "dental_pain", "tongue_lump", "head_withdrawal"},
        "gi": {"gi", "dietary_irritation", "infection_discussion", "vomiting", "diarrhea", "bloody_stool", "black_tarry"},
        "urinary": {"urinary", "urinary_blockage", "uti_discussion", "cannot_pee", "blood_in_urine", "straining"},
        "mobility": {"mobility", "acl", "ccl", "post_op", "orthopedic_follow_up", "non_weight_bearing", "patellar_luxation"},
        "skin_lump": {"skin_lump", "allergy_or_mass_discussion"},
        "respiratory": {"respiratory", "respiratory_distress", "airway_or_lung_issue", "coughing", "breathing_difficulty"},
        "abdominal": {"bloat_gdv", "abdominal_emergency"},
        "neurologic": {"seizure_like_episode", "syncope_discussion", "toxin_exposure"},
        "eye": {"eye_trauma", "corneal_injury", "vision_change"},
    }.get(domain, {domain})
    values: list[str] = []
    raw_value = item.get("possible_discussion_topics")
    if isinstance(raw_value, list):
        values.extend(str(value) for value in raw_value)
    return bool(set(values) & domain_terms)


def _care_context_domain(
    *, professional_payload: list[dict[str, object]], raw_text: str
) -> str | None:
    lowered = raw_text.lower()
    if any(term in lowered for term in ["salivary", "mouth", "oral", "jaw", "chin", "neck"]):
        return "oral_neck"
    if any(term in lowered for term in ["pee", "urine", "urinary", "litter box"]):
        return "urinary"
    if any(term in lowered for term in ["vomit", "diarrhea", "poop", "stool", "gi"]):
        return "gi"
    if any(term in lowered for term in ["limp", "leg", "acl", "ccl", "walk"]):
        return "mobility"
    if any(term in lowered for term in ["skin", "lump", "bump", "itch"]):
        return "skin_lump"
    if any(term in lowered for term in ["cough", "breath", "wheez"]):
        return "respiratory"
    for reference in professional_payload:
        domain = str(reference.get("domain") or "")
        if domain in {"oral_neck", "gi", "urinary", "mobility", "skin_lump", "respiratory"}:
            return domain
    return None


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _pet_summary(pet: PetRecord) -> dict[str, Any]:
    return {
        "pet_id": pet.pet_id,
        "name": pet.dog_profile.name,
        "species": pet.dog_profile.species,
        "avatar": _pet_avatar(pet),
        "avatar_image": _pet_avatar_image(pet),
        "avatar_zoom": _pet_avatar_number(pet, "avatar_zoom", 1.0),
        "avatar_x": _pet_avatar_number(pet, "avatar_x", 50.0),
        "avatar_y": _pet_avatar_number(pet, "avatar_y", 50.0),
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


def _pet_avatar_number(pet: PetRecord, key: str, default: float) -> float:
    prefix = f"{key}:"
    for note in pet.dog_profile.care_notes:
        if note.startswith(prefix):
            try:
                return float(note.removeprefix(prefix))
            except ValueError:
                return default
    return default


def _mount_web_app(app: FastAPI) -> None:
    app.mount(
        "/app/static",
        StaticFiles(directory=_web_dir()),
        name="pawcare_app_static",
    )


def _web_dir() -> Path:
    return Path(__file__).parent / "web"
