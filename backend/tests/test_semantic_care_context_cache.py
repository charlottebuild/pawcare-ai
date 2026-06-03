from __future__ import annotations

from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import PetRecord
from pawcare.services.semantic_care_context_cache import SemanticCareContextCache


def _pet(*, species: str = "dog", breed: str | None = "Poodle") -> PetRecord:
    return PetRecord(
        pet_id=f"{species}_pet",
        user_id="user_123",
        dog_profile=DogProfile(id=f"{species}_pet", species=species, breed=breed),
        behavioral_baseline=BehavioralBaseline(),
        health_baseline=HealthBaseline(
            known_medical_notes=["prior oral lump"] if species == "dog" else []
        ),
    )


def test_semantic_cache_key_normalizes_similar_symptom_phrases() -> None:
    cache = SemanticCareContextCache()
    pet = _pet()

    first = cache.make_key(raw_text="Mochi poo blood.", pet=pet, limit=3)
    second = cache.make_key(raw_text="Mochi had bloody stool.", pet=pet, limit=3)

    assert first == second
    assert first is not None
    assert set(first.signals) == {"bloody_stool", "gi"}


def test_semantic_cache_key_separates_species_context() -> None:
    cache = SemanticCareContextCache()
    dog_key = cache.make_key(raw_text="couldnt pee", pet=_pet(species="dog"), limit=3)
    cat_key = cache.make_key(raw_text="couldnt pee", pet=_pet(species="cat"), limit=3)

    assert dog_key != cat_key
    assert dog_key is not None
    assert cat_key is not None
    assert dog_key.species == "dog"
    assert cat_key.species == "cat"


def test_semantic_cache_does_not_store_final_response_or_risk_fields() -> None:
    cache = SemanticCareContextCache()
    pet = _pet()
    key = cache.make_key(raw_text="Mochi poo blood.", pet=pet, limit=3)

    cache.set(
        key=key,
        payload={
            "professional_references": [{"domain": "gi"}],
            "related_cases": [],
            "context_summary": "GI context.",
            "non_diagnostic_notice": "Not a diagnosis.",
            "status": "escalate",
            "risk_band": "high",
            "source_guideline_ids": ["GL_CONDITION_GI_001"],
            "escalation_conditions": ["blood worsens"],
        },
    )

    assert len(cache) == 0


def test_semantic_cache_hits_and_evicts_oldest_entry() -> None:
    cache = SemanticCareContextCache(max_entries=1)
    pet = _pet()
    gi_key = cache.make_key(raw_text="Mochi poo blood.", pet=pet, limit=3)
    urinary_key = cache.make_key(raw_text="Mochi cannot pee.", pet=pet, limit=3)

    cache.set(
        key=gi_key,
        payload={
            "professional_references": [{"domain": "gi"}],
            "related_cases": [],
            "context_summary": "GI context.",
            "non_diagnostic_notice": "Not a diagnosis.",
        },
    )
    assert cache.get(raw_text="Mochi had bloody stool.", pet=pet, limit=3).hit

    cache.set(
        key=urinary_key,
        payload={
            "professional_references": [{"domain": "urinary"}],
            "related_cases": [],
            "context_summary": "Urinary context.",
            "non_diagnostic_notice": "Not a diagnosis.",
        },
    )

    assert len(cache) == 1
    assert not cache.get(raw_text="Mochi poo blood.", pet=pet, limit=3).hit
    assert cache.get(raw_text="Mochi cannot pee.", pet=pet, limit=3).hit
