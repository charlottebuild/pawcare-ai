from __future__ import annotations

import math
from collections import Counter
from typing import Protocol

from pawcare.services.case_models import KnowledgeMatch, KnowledgeRecord
from pawcare.skills.symptom_understanding import (
    extract_canonical_terms,
    normalize_match_text,
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


class VectorKnowledgeIndex:
    """Local deterministic vector-style index for semantic recall.

    This is not a production embedding model. It gives PawCare a stable local
    semantic layer that can later be replaced by a real embedding-backed index.
    """

    def __init__(self, *, records: list[KnowledgeRecord]) -> None:
        self.records = records
        self._record_vectors = {
            record.record_id: self._vectorize(self._record_text(record))
            for record in records
        }
        self._record_terms = {
            record.record_id: self._record_terms_for_match(record)
            for record in records
        }

    def search(
        self,
        *,
        query_text: str,
        domains: set[str] | None = None,
        kinds: set[str] | None = None,
        limit: int = 3,
    ) -> list[KnowledgeMatch]:
        query_vector = self._vectorize(query_text)
        query_terms = self._query_terms(query_text)
        if not query_vector:
            return []

        scored: list[tuple[float, KnowledgeMatch]] = []
        for record in self.records:
            if domains is not None and record.domain not in domains:
                continue
            if kinds is not None and record.kind not in kinds:
                continue
            similarity = self._cosine(
                query_vector,
                self._record_vectors[record.record_id],
            )
            matched = sorted(query_terms & self._record_terms[record.record_id])
            if similarity < 0.08 and not matched:
                continue
            score = self._score(similarity=similarity, matched=matched, record=record)
            scored.append(
                (
                    score,
                    KnowledgeMatch(
                        record=record,
                        matched_signals=matched or [record.domain],
                        relevance_score=int(round(score)),
                        relevance_level=self._relevance(score),
                        source_type=record.source_type,
                    ),
                )
            )

        scored.sort(key=lambda item: (-item[0], item[1].record.record_id))
        return [match for _, match in scored[:limit]]

    def _record_text(self, record: KnowledgeRecord) -> str:
        return " ".join(
            value
            for value in [
                record.domain,
                record.kind,
                record.source_name,
                record.title or "",
                record.summary,
                " ".join(record.signals),
                " ".join(record.record_fields),
                " ".join(record.discussion_topics),
                " ".join(record.red_flags),
            ]
            if value
        )

    def _query_terms(self, query_text: str) -> set[str]:
        terms = {normalize_identifier(term) for term in extract_canonical_terms(query_text)}
        terms.update(self._semantic_terms(query_text))
        terms.update(normalize_identifier(term) for term in normalize_match_text(query_text).split())
        return {term for term in terms if term}

    def _record_terms_for_match(self, record: KnowledgeRecord) -> set[str]:
        terms = {
            record.domain,
            *record.signals,
            *record.discussion_topics,
            *record.record_fields,
        }
        terms.update(self._semantic_terms(self._record_text(record)))
        return {normalize_identifier(term) for term in terms if term}

    def _vectorize(self, text: str) -> Counter[str]:
        normalized = normalize_match_text(text)
        tokens = [token for token in normalized.split() if token]
        terms = [normalize_identifier(term) for term in extract_canonical_terms(text)]
        terms.extend(self._semantic_terms(text))
        features: Counter[str] = Counter()
        for token in tokens:
            features[f"tok:{token}"] += 1
            for gram in self._char_ngrams(token):
                features[f"chr:{gram}"] += 1
        for left, right in zip(tokens, tokens[1:]):
            features[f"bigram:{left}_{right}"] += 2
        for term in terms:
            features[f"sem:{term}"] += 4
        return features

    def _semantic_terms(self, text: str) -> set[str]:
        normalized = normalize_match_text(text)
        terms: set[str] = set()
        semantic_groups = {
            "oral_neck": [
                "chin",
                "jaw",
                "neck",
                "mouth",
                "oral",
                "tongue",
                "swallow",
                "eating weird",
                "pulls head",
                "head back",
                "head withdraw",
                "head withdrawal",
                "drool",
                "salivary",
                "saliva",
                "mucocele",
                "sialocele",
            ],
            "head_withdrawal": [
                "pulls head",
                "pull head",
                "head back",
                "head withdraw",
                "shrink head",
                "while eating",
                "eating weird",
            ],
            "dental_or_oral_pain": [
                "chew",
                "chewing",
                "while eating",
                "eating weird",
                "mouth pain",
                "oral pain",
                "tooth",
                "teeth",
            ],
            "oral_mass": [
                "lump",
                "bump",
                "mass",
                "swelling",
                "swollen",
                "cyst",
                "under chin",
                "under jaw",
            ],
            "salivary_gland": ["salivary", "saliva", "saliva cyst", "mucocele", "sialocele"],
            "mobility": ["leg", "limp", "limping", "walk", "walking", "floor", "weight"],
            "non_weight_bearing": [
                "wont touch floor",
                "won t touch floor",
                "leg wont touch",
                "not put weight",
                "not putting weight",
                "cannot stand",
            ],
            "acl": ["acl", "ccl", "cruciate"],
            "patellar_luxation": ["patella", "kneecap", "luxating"],
            "urinary": ["pee", "urine", "urinate", "litter box"],
            "cannot_pee": ["cant pee", "cannot pee", "couldnt pee", "didnt pee", "no pee"],
            "gi": ["poop", "poo", "stool", "diarrhea", "vomit", "throw up", "tummy"],
            "bloody_stool": ["poo blood", "poop blood", "blood stool", "bloody stool"],
            "respiratory": ["cough", "breath", "breathing", "wheeze"],
            "breathing_hard": ["breathing hard", "hard breathing", "labored breathing"],
            "skin_lump": ["skin lump", "itchy bump", "itching", "skin bump"],
            "resource_guarding": ["guard", "guarding", "chew", "toy", "food bowl"],
            "cat_stress": ["tail puffed", "ears flattened", "hiding", "cat stress"],
        }
        for canonical, phrases in semantic_groups.items():
            if any(normalize_match_text(phrase) in normalized for phrase in phrases):
                terms.add(canonical)
        return terms

    def _char_ngrams(self, token: str) -> list[str]:
        if len(token) <= 3:
            return [token]
        return [token[index : index + 3] for index in range(len(token) - 2)]

    def _cosine(self, left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(value * right.get(key, 0) for key, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _score(
        self,
        *,
        similarity: float,
        matched: list[str],
        record: KnowledgeRecord,
    ) -> float:
        domain_bonus = 12 if record.domain in matched else 0
        signal_bonus = len(matched) * 4
        source_bonus = 2 if record.source_type in {"professional_reference", "seeded_clinical_profile"} else 0
        return similarity * 100 + domain_bonus + signal_bonus + source_bonus

    def _relevance(self, score: float) -> str:
        if score >= 28:
            return "high"
        if score >= 10:
            return "medium"
        return "low"


class HybridKnowledgeIndex:
    """Combine deterministic keyword matching with local semantic retrieval."""

    def __init__(self, *, records: list[KnowledgeRecord]) -> None:
        self.local_index = LocalKnowledgeIndex(records=records)
        self.vector_index = VectorKnowledgeIndex(records=records)

    def search(
        self,
        *,
        query_text: str,
        domains: set[str] | None = None,
        kinds: set[str] | None = None,
        limit: int = 3,
    ) -> list[KnowledgeMatch]:
        candidates = [
            *self.local_index.search(
                query_text=query_text,
                domains=domains,
                kinds=kinds,
                limit=max(limit * 3, 10),
            ),
            *self.vector_index.search(
                query_text=query_text,
                domains=domains,
                kinds=kinds,
                limit=max(limit * 3, 10),
            ),
        ]
        by_record: dict[str, KnowledgeMatch] = {}
        for match in candidates:
            existing = by_record.get(match.record.record_id)
            if existing is None:
                by_record[match.record.record_id] = match
                continue
            merged_signals = sorted(set(existing.matched_signals) | set(match.matched_signals))
            if match.relevance_score > existing.relevance_score:
                by_record[match.record.record_id] = KnowledgeMatch(
                    record=match.record,
                    matched_signals=merged_signals,
                    relevance_score=match.relevance_score,
                    relevance_level=match.relevance_level,
                    source_type=match.source_type,
                )
            else:
                by_record[match.record.record_id] = KnowledgeMatch(
                    record=existing.record,
                    matched_signals=merged_signals,
                    relevance_score=existing.relevance_score,
                    relevance_level=existing.relevance_level,
                    source_type=existing.source_type,
                )
        matches = list(by_record.values())
        matches.sort(key=lambda match: (-match.relevance_score, match.record.record_id))
        return matches[:limit]
