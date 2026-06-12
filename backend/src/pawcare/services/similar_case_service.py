from __future__ import annotations

from dataclasses import asdict

from pawcare.schemas.state import Observation
from pawcare.services.case_models import CaseMatch, CommunityCase
from pawcare.services.knowledge_adapters import community_case_to_record
from pawcare.services.knowledge_index import HybridKnowledgeIndex, KnowledgeIndex
from pawcare.services.pet_models import PetRecord
from pawcare.skills.symptom_understanding import (
    extract_canonical_terms,
    has_care_context_trigger,
)


class SimilarCaseService:
    """Deterministic related-case retrieval for non-diagnostic triage support."""

    def __init__(
        self,
        *,
        cases: list[CommunityCase] | None = None,
        knowledge_index: KnowledgeIndex | None = None,
    ) -> None:
        self.cases = cases or seed_community_cases()
        self.knowledge_index = knowledge_index or HybridKnowledgeIndex(
            records=[community_case_to_record(case) for case in self.cases]
        )

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
        query_text = " ".join(
            item
            for item in [
                raw_text,
                pet.dog_profile.breed or "",
                " ".join(pet.health_baseline.known_medical_notes),
            ]
            if item
        )
        matches = self.knowledge_index.search(
            query_text=query_text,
            kinds={"community_case"},
            limit=max(limit * 3, 10),
        )
        filtered = [
            self._to_match(match)
            for match in matches
            if not trigger_terms
            or set(match.matched_signals) & trigger_terms
        ]
        return filtered[:limit]

    def as_payload(self, matches: list[CaseMatch]) -> list[dict[str, object]]:
        return [asdict(match) for match in matches]

    def _trigger_terms(
        self,
        *,
        raw_text: str,
    ) -> set[str]:
        return self._terms_from_text(raw_text)

    def _has_triage_intent(self, raw_text: str) -> bool:
        return has_care_context_trigger(raw_text)

    def _to_match(self, match) -> CaseMatch:
        record = match.record
        return CaseMatch(
            case_id=record.record_id,
            title=record.title or record.source_name,
            source_platform=record.source_type,
            source_url=record.source_url,
            case_summary=record.summary,
            privacy_safe_snippet=record.privacy_safe_snippet or "",
            matched_symptoms=list(match.matched_signals),
            possible_discussion_topics=list(record.discussion_topics),
            red_flags=list(record.red_flags),
            case_relevance_level=match.relevance_level,
            condition_discussion_priority=self._priority(match.relevance_score),
            vet_outcome=record.vet_outcome,
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

def seed_community_cases() -> list[CommunityCase]:
    return [
        CommunityCase(
            case_id="case_acl_postop_001",
            title="Post-op dog avoided weight-bearing during recovery",
            source_platform="seeded_clinical_profile",
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
            source_platform="seeded_clinical_profile",
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
            source_platform="seeded_clinical_profile",
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
            symptoms=["vomiting", "diarrhea", "bloody_stool", "gi"],
            body_areas=["gi"],
            possible_discussion_topics=["gi", "dietary_irritation", "infection_discussion"],
            vet_outcome="Vet triaged hydration and stool/vomit history.",
            red_flags=["repeated vomiting", "bloody or black stool", "lethargy", "dehydration"],
        ),
        CommunityCase(
            case_id="case_urinary_001",
            title="Straining to pee with blood was treated as urgent",
            source_platform="seeded_clinical_profile",
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
        CommunityCase(
            case_id="case_seizure_001",
            title="Pet had a seizure-like episode and owner tracked duration",
            source_platform="seeded_clinical_profile",
            source_url="https://example.com/pawcare-cases/seizure-like-episode-duration",
            short_summary=(
                "Owner described collapse with shaking; similar cases focused on timing the episode, "
                "recording recovery, and contacting a vet for neurologic triage."
            ),
            privacy_safe_snippet="Shaking episode with recovery period; owner recorded duration.",
            symptoms=["seizure", "convulsion", "neurologic"],
            body_areas=["neurologic"],
            possible_discussion_topics=["seizure_like_episode", "syncope_discussion", "toxin_exposure"],
            vet_outcome="Vet discussion focused on duration, repeat events, and possible exposures.",
            red_flags=["repeated seizures", "does not recover", "possible toxin exposure"],
        ),
        CommunityCase(
            case_id="case_bloat_001",
            title="Dog had a hard swollen belly and tried to vomit",
            source_platform="seeded_clinical_profile",
            source_url="https://example.com/pawcare-cases/hard-belly-unproductive-retching",
            short_summary=(
                "Owner noticed a hard, swollen abdomen and repeated retching; similar cases "
                "treated this as an emergency discussion topic for bloat/GDV."
            ),
            privacy_safe_snippet="Hard swollen abdomen with unproductive retching.",
            symptoms=["abdominal_distension", "bloat", "unproductive_vomiting"],
            body_areas=["abdomen"],
            possible_discussion_topics=["bloat_gdv", "abdominal_emergency", "urgent_triage"],
            vet_outcome="Urgent veterinary evaluation was recommended in the summarized case.",
            red_flags=["hard or swollen abdomen", "unproductive retching", "collapse"],
        ),
        CommunityCase(
            case_id="case_eye_injury_001",
            title="Eye injury with squinting needed urgent eye exam",
            source_platform="seeded_clinical_profile",
            source_url="https://example.com/pawcare-cases/eye-injury-squinting",
            short_summary=(
                "Owner saw eye trauma with squinting and possible vision change; similar cases "
                "focused on urgent veterinary eye evaluation rather than home treatment."
            ),
            privacy_safe_snippet="Eye trauma with squinting and visible discomfort.",
            symptoms=["eye_injury", "vision_loss", "eye_pain"],
            body_areas=["eye"],
            possible_discussion_topics=["eye_trauma", "corneal_injury", "vision_change"],
            vet_outcome="Vet evaluation was recommended because vision can be at risk.",
            red_flags=["eye bulging", "sudden blindness", "keeps eye closed", "severe pain"],
        ),
    ]
