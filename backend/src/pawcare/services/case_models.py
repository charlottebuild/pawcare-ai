from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


KnowledgeKind = Literal["professional", "behavior", "community_case"]


@dataclass(frozen=True)
class CommunityCase:
    case_id: str
    title: str
    source_platform: str
    source_url: str
    short_summary: str
    privacy_safe_snippet: str
    symptoms: list[str]
    body_areas: list[str]
    possible_discussion_topics: list[str]
    vet_outcome: str | None = None
    red_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CaseMatch:
    case_id: str
    title: str
    source_platform: str
    source_url: str
    case_summary: str
    privacy_safe_snippet: str
    matched_symptoms: list[str]
    possible_discussion_topics: list[str]
    red_flags: list[str]
    case_relevance_level: str
    condition_discussion_priority: str
    vet_outcome: str | None = None


@dataclass(frozen=True)
class ProfessionalCareReference:
    reference_id: str
    source_name: str
    source_url: str
    domain: str
    symptom_signals: list[str]
    summary: str
    red_flags: list[str]
    what_to_record: list[str]
    vet_discussion_topics: list[str]


@dataclass(frozen=True)
class ProfessionalReferenceMatch:
    reference_id: str
    source_name: str
    source_url: str
    domain: str
    summary: str
    matched_signals: list[str]
    red_flags: list[str]
    what_to_record: list[str]
    vet_discussion_topics: list[str]
    relevance_level: str


@dataclass(frozen=True)
class BehaviorCareReference:
    reference_id: str
    source_name: str
    source_url: str
    domain: str
    behavior_signals: list[str]
    summary: str
    management_notes: list[str]
    escalation_signals: list[str]


@dataclass(frozen=True)
class BehaviorReferenceMatch:
    reference_id: str
    source_name: str
    source_url: str
    domain: str
    summary: str
    matched_signals: list[str]
    management_notes: list[str]
    escalation_signals: list[str]
    relevance_level: str


@dataclass(frozen=True)
class KnowledgeRecord:
    record_id: str
    kind: KnowledgeKind
    domain: str
    source_name: str
    source_url: str
    source_type: str
    signals: list[str]
    summary: str
    red_flags: list[str] = field(default_factory=list)
    record_fields: list[str] = field(default_factory=list)
    discussion_topics: list[str] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    title: str | None = None
    privacy_safe_snippet: str | None = None
    vet_outcome: str | None = None


@dataclass(frozen=True)
class KnowledgeMatch:
    record: KnowledgeRecord
    matched_signals: list[str]
    relevance_score: int
    relevance_level: str
    source_type: str


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    source_name: str
    source_url: str
    domain: str
    species: list[str]
    allowed_use: str
    raw_or_manual_summary: str
    signals: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    chunk_text: str
    metadata_header: str
    domain: str
    signals: list[str]
    source_name: str
    source_url: str
    species: list[str] = field(default_factory=list)
