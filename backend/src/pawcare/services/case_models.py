from __future__ import annotations

from dataclasses import dataclass, field


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
