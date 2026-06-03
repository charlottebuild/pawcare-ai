from __future__ import annotations

from datetime import UTC, datetime

from pawcare.evaluation.golden_runner import run_golden_cases
from pawcare.knowledge.abnormal_signals import AbnormalSignalRecord, seed_abnormal_signal_records
from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline, Species
from pawcare.services.knowledge_summarizer import DeterministicKnowledgeSummarizer
from pawcare.services.log_processing_service import LogProcessingService
from pawcare.services.pet_models import PetRecord
from pawcare.services.professional_reference_service import ProfessionalReferenceService
from pawcare.services.semantic_care_context_cache import SemanticCareContextCache
from pawcare.services.similar_case_service import SimilarCaseService
from pawcare.skills.symptom_understanding import contains_any


NON_DIAGNOSTIC_NOTICE = (
    "These results are structured support context, not a diagnosis. Discuss concerning "
    "signals with a veterinarian, especially if red flags are present."
)
_CARE_CONTEXT_CACHE = SemanticCareContextCache()


def screen_abnormal_signals(raw_text: str, species: str = "dog") -> dict[str, object]:
    """Screen messy user wording for known abnormal pet care signals."""

    normalized_species = _normalize_species(species).value
    matched_records = [
        _abnormal_signal_payload(record, raw_text=raw_text)
        for record in seed_abnormal_signal_records()
        if _species_matches(record, normalized_species)
        and _record_matches_text(record, raw_text)
    ]
    canonical_terms = sorted(
        {
            term
            for record in matched_records
            for term in record.get("canonical_terms", [])
            if isinstance(term, str)
        }
    )
    return {
        "matched": bool(matched_records),
        "species": normalized_species,
        "matched_signals": matched_records,
        "canonical_terms": canonical_terms,
        "non_diagnostic_notice": NON_DIAGNOSTIC_NOTICE,
    }


def search_care_context(
    raw_text: str,
    pet_profile: dict[str, object] | None = None,
    limit: int = 3,
) -> dict[str, object]:
    """Return professional references and similar cases for a care concern."""

    pet = _pet_from_profile(pet_profile or {})
    lookup = _CARE_CONTEXT_CACHE.get(raw_text=raw_text, pet=pet, limit=limit)
    if lookup.hit:
        return lookup.payload or {}
    professional_service = ProfessionalReferenceService()
    similar_case_service = SimilarCaseService()
    professional_matches = professional_service.find_matches(
        raw_text=raw_text,
        pet=pet,
        limit=limit,
    )
    similar_matches = similar_case_service.find_matches(
        raw_text=raw_text,
        pet=pet,
        limit=limit,
    )
    professional_payload = professional_service.as_payload(professional_matches)
    similar_payload = similar_case_service.as_payload(similar_matches)
    context_summary = DeterministicKnowledgeSummarizer().summarize(
        matches=[*professional_payload, *similar_payload],
        raw_text=raw_text,
        pet_context=pet.dog_profile.model_dump(mode="json"),
    )
    payload = {
        "professional_references": professional_payload,
        "related_cases": similar_payload,
        "context_summary": context_summary,
        "non_diagnostic_notice": NON_DIAGNOSTIC_NOTICE,
        "cache_status": "miss",
    }
    _CARE_CONTEXT_CACHE.set(key=lookup.key, payload=payload)
    return payload


def preview_pet_response(
    raw_text: str,
    pet_profile: dict[str, object] | None = None,
    timestamp: str | None = None,
) -> dict[str, object]:
    """Run the existing safety chain for a preview without writing pet data."""

    pet = _pet_from_profile(pet_profile or {})
    result = LogProcessingService().process_log(
        workflow_id=f"mcp_preview_{pet.pet_id}",
        dog_id=pet.pet_id,
        raw_text=raw_text,
        timestamp=timestamp or datetime.now(UTC).isoformat(),
        dog_profile=pet.dog_profile,
        behavioral_baseline=pet.behavioral_baseline,
        health_baseline=pet.health_baseline,
        species=pet.dog_profile.species,
    )
    payload = result.response.model_dump(mode="json")
    _strip_internal_fields(payload)
    return payload


def run_golden_eval(layer: str = "all") -> dict[str, object]:
    """Run the local Golden Dataset and return a lightweight summary."""

    selected_layer = layer if layer in {"all", "service", "api"} else "all"
    summary = run_golden_cases(layer=selected_layer).as_dict()
    return {
        "summary": summary["summary"],
        "category_scores": summary["category_scores"],
        "metric_scores": summary["metric_scores"],
        "latency_summary": summary["latency_summary"],
        "quality_summary": summary["quality_summary"],
        "cost_summary": summary["cost_summary"],
    }


def _record_matches_text(record: AbnormalSignalRecord, raw_text: str) -> bool:
    return contains_any(raw_text, [*record.user_phrases, *record.canonical_terms])


def _species_matches(record: AbnormalSignalRecord, species: str) -> bool:
    return species in record.species or "unknown" in record.species


def _abnormal_signal_payload(
    record: AbnormalSignalRecord,
    *,
    raw_text: str,
) -> dict[str, object]:
    matched_terms = [
        term
        for term in [*record.user_phrases, *record.canonical_terms]
        if contains_any(raw_text, [term])
    ]
    return {
        "signal_id": record.signal_id,
        "domain": record.domain,
        "canonical_terms": list(record.canonical_terms),
        "matched_terms": matched_terms,
        "risk_hint": record.risk_hint,
        "safe_language": record.safe_language,
        "reference_ids": list(record.reference_ids),
        "case_ids": list(record.case_ids),
    }


def _pet_from_profile(profile: dict[str, object]) -> PetRecord:
    pet_id = _string_or_default(profile.get("id") or profile.get("pet_id"), "pet_preview")
    species = _normalize_species(_string_or_default(profile.get("species"), "dog"))
    known_medical_notes = _string_list(profile.get("known_medical_notes"))
    care_notes = _string_list(profile.get("care_notes"))
    if known_medical_notes and not care_notes:
        care_notes = known_medical_notes
    dog_profile = DogProfile.model_validate(
        {
            "id": pet_id,
            "name": _optional_string(profile.get("name")) or "Preview Pet",
            "species": species.value,
            "breed": _optional_string(profile.get("breed")),
            "age_years": profile.get("age_years"),
            "weight_kg": profile.get("weight_kg"),
            "care_notes": care_notes,
        }
    )
    behavioral_baseline = BehavioralBaseline.model_validate(
        profile.get("behavioral_baseline")
        if isinstance(profile.get("behavioral_baseline"), dict)
        else {"general_temperament": "unknown"}
    )
    health_baseline = HealthBaseline.model_validate(
        profile.get("health_baseline")
        if isinstance(profile.get("health_baseline"), dict)
        else {
            "normal_appetite": "unknown",
            "normal_stool_quality": "unknown",
            "normal_activity_level": "unknown",
            "known_medical_notes": known_medical_notes,
        }
    )
    return PetRecord(
        pet_id=pet_id,
        user_id=_string_or_default(profile.get("user_id"), "mcp_preview_user"),
        dog_profile=dog_profile,
        behavioral_baseline=behavioral_baseline,
        health_baseline=health_baseline,
    )


def _normalize_species(value: str) -> Species:
    try:
        return Species(value.lower())
    except ValueError:
        return Species.dog


def _string_or_default(value: object, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _strip_internal_fields(payload: dict[str, object]) -> None:
    for key in ("agent_outputs", "proposed_update", "safety_review"):
        payload.pop(key, None)
