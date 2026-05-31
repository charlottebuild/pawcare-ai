from __future__ import annotations

from dataclasses import asdict

from pawcare.schemas.state import Observation
from pawcare.services.case_models import CaseMatch, CommunityCase
from pawcare.services.pet_models import PetRecord
from pawcare.skills.symptom_understanding import (
    TRIAGE_INTENT_TERMS,
    contains_any,
    extract_canonical_terms,
    normalize_identifier,
)


class SimilarCaseService:
    """Deterministic related-case retrieval for non-diagnostic triage support."""

    def __init__(self, *, cases: list[CommunityCase] | None = None) -> None:
        self.cases = cases or seed_community_cases()

    def find_matches(
        self,
        *,
        raw_text: str,
        pet: PetRecord,
        recent_observations: list[Observation] | None = None,
        limit: int = 3,
    ) -> list[CaseMatch]:
        if not self._has_triage_intent(raw_text):
            return []
        trigger_terms = self._trigger_terms(
            raw_text=raw_text,
        )
        query_terms = set(trigger_terms)
        query_terms.update(self._profile_terms(pet))
        scored: list[tuple[int, CommunityCase, list[str]]] = []
        for case in self.cases:
            matched = self._matched_terms(case=case, query_terms=query_terms)
            trigger_matched = self._matched_terms(case=case, query_terms=trigger_terms)
            if trigger_matched:
                scored.append((self._score(case=case, matched=matched), case, matched))

        scored.sort(key=lambda item: (-item[0], item[1].case_id))
        return [
            self._to_match(case=case, matched=matched, score=score)
            for score, case, matched in scored[:limit]
        ]

    def as_payload(self, matches: list[CaseMatch]) -> list[dict[str, object]]:
        return [asdict(match) for match in matches]

    def _trigger_terms(
        self,
        *,
        raw_text: str,
    ) -> set[str]:
        return self._terms_from_text(raw_text)

    def _has_triage_intent(self, raw_text: str) -> bool:
        return contains_any(raw_text, TRIAGE_INTENT_TERMS)

    def _profile_terms(self, pet: PetRecord) -> set[str]:
        profile_text = " ".join(
            item
            for item in [
                pet.dog_profile.breed or "",
                " ".join(pet.health_baseline.known_medical_notes),
            ]
            if item
        )
        return self._terms_from_text(profile_text)

    def _matched_terms(self, *, case: CommunityCase, query_terms: set[str]) -> list[str]:
        case_terms = set(case.symptoms) | set(case.body_areas) | set(
            case.possible_discussion_topics
        )
        normalized_case_terms = {self._normalize_token(term) for term in case_terms}
        normalized_query_terms = {self._normalize_token(term) for term in query_terms}
        matches = normalized_case_terms & normalized_query_terms
        return sorted(term for term in matches if term)

    def _score(self, *, case: CommunityCase, matched: list[str]) -> int:
        high_signal_terms = {
            "acl",
            "ccl",
            "patellar_luxation",
            "post_op",
            "non_weight_bearing",
            "oral_mass",
            "salivary_gland",
            "tongue_lump",
            "bloody_urine",
            "cannot_pee",
            "breathing_hard",
        }
        return len(matched) + sum(2 for term in matched if term in high_signal_terms)

    def _to_match(
        self, *, case: CommunityCase, matched: list[str], score: int
    ) -> CaseMatch:
        return CaseMatch(
            case_id=case.case_id,
            title=case.title,
            source_platform=case.source_platform,
            source_url=case.source_url,
            case_summary=case.short_summary,
            privacy_safe_snippet=case.privacy_safe_snippet,
            matched_symptoms=matched,
            possible_discussion_topics=case.possible_discussion_topics,
            red_flags=case.red_flags,
            case_relevance_level=self._relevance(score),
            condition_discussion_priority=self._priority(score),
            vet_outcome=case.vet_outcome,
        )

    def _relevance(self, score: int) -> str:
        if score >= 5:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def _priority(self, score: int) -> str:
        if score >= 5:
            return "discuss_soon"
        if score >= 2:
            return "discuss_if_persistent"
        return "background_context"

    def _terms_from_text(self, value: str) -> set[str]:
        return extract_canonical_terms(value)

    def _normalize_token(self, value: str) -> str:
        return normalize_identifier(value)


def seed_community_cases() -> list[CommunityCase]:
    return [
        CommunityCase(
            case_id="case_acl_postop_001",
            title="Post-op dog avoided weight-bearing during recovery",
            source_platform="seeded_public_summary",
            source_url="https://example.com/pawcare-cases/acl-postop-weight-bearing",
            short_summary=(
                "Owner noticed a dog still avoided putting weight on the operated leg during "
                "recovery and discussed ACL/CCL follow-up with an orthopedic vet."
            ),
            privacy_safe_snippet="Avoided weight-bearing after surgery; owner tracked pain and rehab tolerance.",
            symptoms=["acl", "post_op", "non_weight_bearing", "rehab_reluctance"],
            body_areas=["mobility"],
            possible_discussion_topics=["acl", "ccl", "post_op", "orthopedic_follow_up"],
            vet_outcome="Vet discussed rehab adjustment and pain/lameness monitoring.",
            red_flags=[
                "sudden worsening lameness",
                "persistent non-weight-bearing",
                "swelling or obvious pain",
            ],
        ),
        CommunityCase(
            case_id="case_patella_001",
            title="Small dog skipped steps and lifted a back leg",
            source_platform="seeded_public_summary",
            source_url="https://example.com/pawcare-cases/patellar-luxation-skipping",
            short_summary=(
                "Owner described intermittent hopping and back-leg lifting; vet discussion "
                "included patellar luxation and orthopedic evaluation."
            ),
            privacy_safe_snippet="Intermittent skipping gait and leg lift during walks.",
            symptoms=["patellar_luxation", "non_weight_bearing"],
            body_areas=["mobility", "knee"],
            possible_discussion_topics=["patellar_luxation", "orthopedic_follow_up"],
            vet_outcome="Vet recommended orthopedic exam and monitoring gait videos.",
            red_flags=["cannot use the leg", "pain increases", "lameness persists"],
        ),
        CommunityCase(
            case_id="case_oral_neck_001",
            title="Dog pulled head back while eating; oral exam found a benign lump",
            source_platform="seeded_public_summary",
            source_url="https://example.com/pawcare-cases/oral-lump-eating-discomfort",
            short_summary=(
                "Owner noticed head withdrawal and head tilting while eating; veterinary exam "
                "checked mouth, tongue, teeth, and salivary-area concerns."
            ),
            privacy_safe_snippet="Head pulled back while eating; mouth discomfort was evaluated by a vet.",
            symptoms=["head_withdrawal", "oral_mass", "tongue_lump", "salivary_gland"],
            body_areas=["oral", "neck"],
            possible_discussion_topics=["oral_mass", "salivary_gland", "dental_pain"],
            vet_outcome="Vet evaluated an oral lump; outcome was benign in the summarized case.",
            red_flags=["refuses food", "rapid swelling", "bleeding", "trouble swallowing"],
        ),
        CommunityCase(
            case_id="case_gi_001",
            title="Vomiting and diarrhea prompted GI triage",
            source_platform="seeded_public_summary",
            source_url="https://example.com/pawcare-cases/vomiting-diarrhea-gi",
            short_summary=(
                "Owner reported vomiting with diarrhea and discussed GI irritation, dietary "
                "indiscretion, infection, and dehydration risk with a vet."
            ),
            privacy_safe_snippet="Vomiting plus diarrhea; owner tracked frequency, stool color, and energy.",
            symptoms=["vomiting", "diarrhea", "gi"],
            body_areas=["gi"],
            possible_discussion_topics=["gi", "dietary_irritation", "infection_discussion"],
            vet_outcome="Vet triaged hydration and stool/vomit history.",
            red_flags=["repeated vomiting", "bloody or black stool", "lethargy", "dehydration"],
        ),
        CommunityCase(
            case_id="case_urinary_001",
            title="Straining to pee with blood was treated as urgent",
            source_platform="seeded_public_summary",
            source_url="https://example.com/pawcare-cases/urinary-straining-blood",
            short_summary=(
                "Owner saw straining and blood in urine; community responses emphasized urgent "
                "vet evaluation for urinary blockage or urinary tract problems."
            ),
            privacy_safe_snippet="Straining to urinate and blood visible in urine.",
            symptoms=["urinary", "bloody_urine", "cannot_pee"],
            body_areas=["urinary"],
            possible_discussion_topics=["urinary_blockage", "uti_discussion"],
            vet_outcome="Urgent veterinary triage was recommended.",
            red_flags=["cannot pee", "blood in urine", "painful straining"],
        ),
        CommunityCase(
            case_id="case_respiratory_001",
            title="Coughing with hard breathing needed urgent triage",
            source_platform="seeded_public_summary",
            source_url="https://example.com/pawcare-cases/coughing-hard-breathing",
            short_summary=(
                "Owner described coughing and increased breathing effort; similar cases discussed "
                "respiratory distress signs and urgent vet contact."
            ),
            privacy_safe_snippet="Coughing and breathing effort increased.",
            symptoms=["respiratory", "breathing_hard"],
            body_areas=["respiratory"],
            possible_discussion_topics=["respiratory_distress", "airway_or_lung_issue"],
            vet_outcome="Urgent evaluation was recommended because breathing effort changed.",
            red_flags=["labored breathing", "blue gums", "collapse", "rapid worsening"],
        ),
        CommunityCase(
            case_id="case_skin_lump_001",
            title="New skin lump and itching were documented before vet visit",
            source_platform="seeded_public_summary",
            source_url="https://example.com/pawcare-cases/skin-lump-itching",
            short_summary=(
                "Owner noticed a new lump with itching and recorded size, location, growth speed, "
                "and photos before the vet appointment."
            ),
            privacy_safe_snippet="New skin bump with itching; owner tracked size and change over time.",
            symptoms=["skin_lump"],
            body_areas=["skin"],
            possible_discussion_topics=["skin_lump", "allergy_or_mass_discussion"],
            vet_outcome="Vet visit focused on documenting growth and irritation.",
            red_flags=["rapid growth", "bleeding", "pain", "open wound"],
        ),
    ]
