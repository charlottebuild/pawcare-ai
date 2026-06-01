from __future__ import annotations

from pawcare.services.case_models import (
    BehaviorCareReference,
    CommunityCase,
    KnowledgeRecord,
    ProfessionalCareReference,
)


def professional_reference_to_record(
    reference: ProfessionalCareReference,
) -> KnowledgeRecord:
    return KnowledgeRecord(
        record_id=reference.reference_id,
        kind="professional",
        domain=reference.domain,
        source_name=reference.source_name,
        source_url=reference.source_url,
        source_type="professional_reference",
        signals=list(reference.symptom_signals),
        summary=reference.summary,
        red_flags=list(reference.red_flags),
        record_fields=list(reference.what_to_record),
        discussion_topics=list(reference.vet_discussion_topics),
        safety_notes=["non_diagnostic", "discuss_with_veterinarian"],
    )


def behavior_reference_to_record(reference: BehaviorCareReference) -> KnowledgeRecord:
    return KnowledgeRecord(
        record_id=reference.reference_id,
        kind="behavior",
        domain=reference.domain,
        source_name=reference.source_name,
        source_url=reference.source_url,
        source_type="behavior_reference",
        signals=list(reference.behavior_signals),
        summary=reference.summary,
        red_flags=list(reference.escalation_signals),
        record_fields=list(reference.management_notes),
        discussion_topics=[reference.domain],
        safety_notes=["non_diagnostic", "manage_environment", "avoid_punishment"],
    )


def community_case_to_record(case: CommunityCase) -> KnowledgeRecord:
    return KnowledgeRecord(
        record_id=case.case_id,
        kind="community_case",
        domain=case.body_areas[0] if case.body_areas else "general",
        source_name=case.title,
        source_url=case.source_url,
        source_type=case.source_platform,
        signals=list(case.symptoms) + list(case.body_areas),
        summary=case.short_summary,
        red_flags=list(case.red_flags),
        record_fields=[],
        discussion_topics=list(case.possible_discussion_topics),
        safety_notes=["similar_case_not_diagnosis", "privacy_safe_summary_only"],
        title=case.title,
        privacy_safe_snippet=case.privacy_safe_snippet,
        vet_outcome=case.vet_outcome,
    )
