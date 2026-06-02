from __future__ import annotations

from typing import Protocol

from pawcare.services.case_models import KnowledgeMatch, KnowledgeRecord
from pawcare.skills.symptom_understanding import (
    extract_canonical_terms,
    normalize_identifier,
)


class KnowledgeIndex(Protocol):
    def search(
        self,
        *,
        query_text: str,
        domains: set[str] | None = None,
        kinds: set[str] | None = None,
        limit: int = 3,
    ) -> list[KnowledgeMatch]:
        """Return ranked knowledge matches for the current query."""


class LocalKnowledgeIndex:
    """Small deterministic index that can later be replaced by vector search."""

    def __init__(self, *, records: list[KnowledgeRecord]) -> None:
        self.records = records

    def search(
        self,
        *,
        query_text: str,
        domains: set[str] | None = None,
        kinds: set[str] | None = None,
        limit: int = 3,
    ) -> list[KnowledgeMatch]:
        query_terms = {normalize_identifier(term) for term in extract_canonical_terms(query_text)}
        query_terms.update(normalize_identifier(term) for term in query_text.split())
        scored: list[KnowledgeMatch] = []
        for record in self.records:
            if domains is not None and record.domain not in domains:
                continue
            if kinds is not None and record.kind not in kinds:
                continue
            record_terms = self._record_terms(record)
            matched = sorted(query_terms & record_terms)
            if not matched:
                continue
            score = self._score(record=record, matched=matched)
            scored.append(
                KnowledgeMatch(
                    record=record,
                    matched_signals=matched,
                    relevance_score=score,
                    relevance_level=self._relevance(score),
                    source_type=record.source_type,
                )
            )
        scored.sort(key=lambda match: (-match.relevance_score, match.record.record_id))
        return scored[:limit]

    def _record_terms(self, record: KnowledgeRecord) -> set[str]:
        terms = set(record.signals)
        terms.add(record.domain)
        terms.update(record.discussion_topics)
        terms.update(record.record_fields)
        return {normalize_identifier(term) for term in terms if term}

    def _score(self, *, record: KnowledgeRecord, matched: list[str]) -> int:
        high_signal_terms = {
            "acl",
            "patellar_luxation",
            "post_op",
            "non_weight_bearing",
            "salivary_gland",
            "tongue_lump",
            "bloody_urine",
            "cannot_pee",
            "abdominal_distension",
            "bloat",
            "unproductive_vomiting",
            "seizure",
            "convulsion",
            "eye_injury",
            "vision_loss",
            "eye_pain",
            "breathing_hard",
            "resource_guarding",
            "escalation_signal",
            "stress_signals",
            "pain",
        }
        specificity_bonus = 0 if record.domain in {"behavior_history"} else 1
        domain_bonus = 3 if normalize_identifier(record.domain) in matched else 0
        history_bonus = (
            1
            if record.domain == "behavior_history" and "social_interaction" in matched
            else 0
        )
        domain_priority_bonus = {
            "resource_guarding": 3,
            "abdominal": 3,
            "neurologic": 3,
            "eye": 3,
            "urinary": 2,
            "respiratory": 2,
            "oral_neck": 1,
            "mobility": 1,
        }.get(record.domain, 0)
        return (
            len(matched)
            + sum(2 for term in matched if term in high_signal_terms)
            + specificity_bonus
            + domain_bonus
            + history_bonus
            + domain_priority_bonus
        )

    def _relevance(self, score: int) -> str:
        if score >= 5:
            return "high"
        if score >= 2:
            return "medium"
        return "low"
