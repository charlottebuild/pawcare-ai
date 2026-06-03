from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from pawcare.services.pet_models import PetRecord
from pawcare.skills.symptom_understanding import extract_canonical_terms


FORBIDDEN_CACHE_FIELDS = {
    "message",
    "response",
    "status",
    "risk_band",
    "source_guideline_ids",
    "guideline_ids",
    "escalation_conditions",
    "agent_outputs",
    "proposed_update",
    "safety_review",
}


@dataclass(frozen=True)
class SemanticCareContextCacheKey:
    species: str
    signals: tuple[str, ...]
    breed: str
    known_medical_notes: tuple[str, ...]
    limit: int


@dataclass(frozen=True)
class SemanticCareContextCacheLookup:
    key: SemanticCareContextCacheKey | None
    payload: dict[str, object] | None

    @property
    def hit(self) -> bool:
        return self.payload is not None


class SemanticCareContextCache:
    """In-memory semantic cache for non-diagnostic care context payloads."""

    def __init__(self, *, max_entries: int = 256) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.max_entries = max_entries
        self._entries: OrderedDict[
            SemanticCareContextCacheKey,
            dict[str, object],
        ] = OrderedDict()

    def make_key(
        self,
        *,
        raw_text: str,
        pet: PetRecord,
        limit: int,
    ) -> SemanticCareContextCacheKey | None:
        signals = tuple(sorted(extract_canonical_terms(raw_text)))
        if not signals:
            return None
        return SemanticCareContextCacheKey(
            species=str(pet.dog_profile.species),
            signals=signals,
            breed=(pet.dog_profile.breed or "").strip().lower(),
            known_medical_notes=tuple(
                sorted(
                    note.strip().lower()
                    for note in pet.health_baseline.known_medical_notes
                    if note.strip()
                )
            ),
            limit=limit,
        )

    def get(
        self,
        *,
        raw_text: str,
        pet: PetRecord,
        limit: int,
    ) -> SemanticCareContextCacheLookup:
        key = self.make_key(raw_text=raw_text, pet=pet, limit=limit)
        if key is None or key not in self._entries:
            return SemanticCareContextCacheLookup(key=key, payload=None)
        payload = self._entries.pop(key)
        self._entries[key] = payload
        cached_payload = dict(payload)
        cached_payload["cache_status"] = "hit"
        return SemanticCareContextCacheLookup(key=key, payload=cached_payload)

    def set(self, *, key: SemanticCareContextCacheKey | None, payload: dict[str, object]) -> None:
        if key is None or not self._cacheable(payload):
            return
        stored_payload = {
            name: value
            for name, value in payload.items()
            if name not in FORBIDDEN_CACHE_FIELDS and name != "cache_status"
        }
        self._entries[key] = stored_payload
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def __len__(self) -> int:
        return len(self._entries)

    def _cacheable(self, payload: dict[str, object]) -> bool:
        if set(payload) & FORBIDDEN_CACHE_FIELDS:
            return False
        professional_references = payload.get("professional_references")
        related_cases = payload.get("related_cases")
        return bool(professional_references or related_cases)
