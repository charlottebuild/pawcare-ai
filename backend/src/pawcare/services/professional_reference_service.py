from __future__ import annotations

from dataclasses import asdict

from pawcare.schemas.state import Observation
from pawcare.services.case_models import (
    KnowledgeMatch,
    ProfessionalCareReference,
    ProfessionalReferenceMatch,
)
from pawcare.services.knowledge_adapters import professional_reference_to_record
from pawcare.services.knowledge_fts_index import (
    SQLiteKnowledgeFTSIndex,
    seed_professional_knowledge_documents,
)
from pawcare.services.knowledge_index import HybridKnowledgeIndex, KnowledgeIndex
from pawcare.services.pet_models import PetRecord
from pawcare.skills.symptom_understanding import (
    extract_canonical_terms,
    has_care_context_trigger,
)


class ProfessionalReferenceService:
    """Curated professional references used as non-diagnostic care context."""

    def __init__(
        self,
        *,
        references: list[ProfessionalCareReference] | None = None,
        knowledge_index: KnowledgeIndex | None = None,
        fts_index: SQLiteKnowledgeFTSIndex | None = None,
    ) -> None:
        self.references = references or seed_professional_references()
        self.knowledge_index = knowledge_index or HybridKnowledgeIndex(
            records=[
                professional_reference_to_record(reference)
                for reference in self.references
            ]
        )
        self.fts_index = fts_index or SQLiteKnowledgeFTSIndex()
        if fts_index is None:
            self.fts_index.ingest_documents(seed_professional_knowledge_documents())

    def find_matches(
        self,
        *,
        raw_text: str,
        pet: PetRecord,
        recent_observations: list[Observation] | None = None,
        limit: int = 3,
    ) -> list[ProfessionalReferenceMatch]:
        if not has_care_context_trigger(raw_text):
            return []

        query_text = " ".join(
            item
            for item in [
                raw_text,
                pet.dog_profile.species,
                pet.dog_profile.breed or "",
                " ".join(pet.health_baseline.known_medical_notes),
            ]
            if item
        )
        matches = self.knowledge_index.search(
            query_text=query_text,
            kinds={"professional"},
            limit=max(limit * 3, 10),
        )
        fts_matches = self.fts_index.search(
            query_text=query_text,
            domains=None,
            limit=max(limit * 2, 6),
        )
        filtered = [
            self._to_match(match)
            for match in [*matches, *fts_matches]
            if self._trigger_matches(raw_text=raw_text, match=match)
        ]
        return self._dedupe(filtered)[:limit]

    def as_payload(
        self,
        matches: list[ProfessionalReferenceMatch],
    ) -> list[dict[str, object]]:
        return [asdict(match) for match in matches]

    def _profile_terms(self, pet: PetRecord) -> set[str]:
        profile_text = " ".join(
            item
            for item in [
                pet.dog_profile.species,
                pet.dog_profile.breed or "",
                " ".join(pet.health_baseline.known_medical_notes),
            ]
            if item
        )
        return extract_canonical_terms(profile_text)

    def _trigger_matches(self, *, raw_text: str, match: KnowledgeMatch) -> bool:
        trigger_terms = extract_canonical_terms(raw_text)
        if not trigger_terms:
            return match.relevance_score >= 10
        return bool(set(match.matched_signals) & trigger_terms)

    def _to_match(self, match: KnowledgeMatch) -> ProfessionalReferenceMatch:
        record = match.record
        return ProfessionalReferenceMatch(
            reference_id=record.record_id,
            source_name=record.source_name,
            source_url=record.source_url,
            domain=record.domain,
            summary=record.summary,
            matched_signals=list(match.matched_signals),
            red_flags=list(record.red_flags),
            what_to_record=list(record.record_fields),
            vet_discussion_topics=list(record.discussion_topics),
            relevance_level=match.relevance_level,
        )

    def _dedupe(
        self, matches: list[ProfessionalReferenceMatch]
    ) -> list[ProfessionalReferenceMatch]:
        seen: set[str] = set()
        deduped: list[ProfessionalReferenceMatch] = []
        for match in matches:
            if match.reference_id in seen:
                continue
            seen.add(match.reference_id)
            deduped.append(match)
        return deduped


def seed_professional_references() -> list[ProfessionalCareReference]:
    return [
        ProfessionalCareReference(
            reference_id="ref_gi_merck_001",
            source_name="Merck Veterinary Manual - Digestive Disorders of Dogs",
            source_url=(
                "https://www.merckvetmanual.com/dog-owners/digestive-disorders-of-dogs/"
                "introduction-to-digestive-disorders-of-dogs"
            ),
            domain="gi",
            symptom_signals=["gi", "vomiting", "diarrhea", "bloody_stool"],
            summary=(
                "Vomiting, diarrhea, appetite change, and stool changes can come from many GI "
                "or body-wide causes, so the useful next step is careful history and veterinary exam."
            ),
            red_flags=["repeated vomiting", "bloody or black stool", "lethargy", "dehydration"],
            what_to_record=["vomit frequency", "stool color/texture", "appetite", "water intake", "energy", "possible exposures"],
            vet_discussion_topics=["dietary upset", "gastroenteritis", "parasites", "foreign material", "infectious disease"],
        ),
        ProfessionalCareReference(
            reference_id="ref_oral_acvs_001",
            source_name="ACVS - Salivary Mucocele",
            source_url="https://www.acvs.org/small-animal/sialocele/",
            domain="oral_neck",
            symptom_signals=["head_withdrawal", "drooling", "oral_mass", "tongue_lump", "salivary_gland"],
            summary=(
                "Soft swelling around the jaw, mouth, or under the tongue can be one reason to discuss "
                "salivary or oral causes with a veterinarian, especially when eating or swallowing changes."
            ),
            red_flags=["trouble breathing", "trouble swallowing", "rapid swelling", "bleeding", "refuses food"],
            what_to_record=["location", "size", "firmness", "growth speed", "drooling", "eating or swallowing changes", "photos"],
            vet_discussion_topics=["salivary mucocele", "oral mass", "dental pain", "abscess", "lymph node swelling"],
        ),
        ProfessionalCareReference(
            reference_id="ref_oral_merck_001",
            source_name="Merck Veterinary Manual - Disorders of the Mouth in Dogs",
            source_url=(
                "https://www.merckvetmanual.com/dog-owners/digestive-disorders-of-dogs/"
                "disorders-of-the-mouth-in-dogs"
            ),
            domain="oral_neck",
            symptom_signals=["oral_mass", "dental_or_oral_pain", "drooling", "head_withdrawal"],
            summary=(
                "Mouth discomfort, drooling, trouble eating, or head withdrawal while eating "
                "can point to oral, dental, salivary, or throat-area issues to discuss with a vet."
            ),
            red_flags=["trouble breathing", "trouble swallowing", "bleeding", "refuses food", "severe pain"],
            what_to_record=["eating changes", "drooling", "mouth odor", "visible swelling", "bleeding", "photos if safe"],
            vet_discussion_topics=["dental disease", "oral pain", "salivary issue", "foreign material", "oral mass"],
        ),
        ProfessionalCareReference(
            reference_id="ref_mobility_acvs_001",
            source_name="ACVS - Cranial Cruciate Ligament Disease",
            source_url="https://www.acvs.org/es/small-animal/partial-acl-injury/",
            domain="mobility",
            symptom_signals=["acl", "post_op", "non_weight_bearing", "patellar_luxation", "rehab_reluctance"],
            summary=(
                "Hind-limb lameness, difficulty rising, reduced weight bearing, or post-op worsening "
                "are orthopedic discussion points, not something the app should diagnose."
            ),
            red_flags=["sudden non-weight-bearing", "worsening pain", "swelling", "post-op decline"],
            what_to_record=["affected limb", "weight-bearing level", "pain signs", "swelling", "exercise tolerance", "videos"],
            vet_discussion_topics=["ACL/CCL injury", "patellar luxation", "meniscal pain", "post-op rehab adjustment"],
        ),
        ProfessionalCareReference(
            reference_id="ref_mobility_patella_cornell_001",
            source_name="Cornell Riney Canine Health Center - Patellar Luxation",
            source_url=(
                "https://www.vet.cornell.edu/departments-centers-and-institutes/"
                "riney-canine-health-center/canine-health-information/patellar-luxation"
            ),
            domain="mobility",
            symptom_signals=["patellar_luxation", "non_weight_bearing", "pain"],
            summary=(
                "Intermittent skipping, sudden hind-leg lifting, or recurrent knee-related lameness "
                "are useful signs to document and discuss with an orthopedic veterinarian."
            ),
            red_flags=["persistent lameness", "pain", "cannot use the limb", "worsening frequency"],
            what_to_record=["which leg", "video of gait", "frequency", "pain signs", "activity before onset"],
            vet_discussion_topics=["patellar luxation", "orthopedic exam", "knee pain", "gait video review"],
        ),
        ProfessionalCareReference(
            reference_id="ref_pain_aaha_001",
            source_name="AAHA - 2022 Pain Management Guidelines for Dogs and Cats",
            source_url=(
                "https://www.aaha.org/resources/2022-aaha-pain-management-guidelines-for-dogs-and-cats/"
                "home-3/"
            ),
            domain="mobility",
            symptom_signals=["pain", "post_op", "non_weight_bearing", "rehab_reluctance"],
            summary=(
                "Pain signs can be subtle after surgery or injury. Changes in normal behavior, "
                "activity, comfort, and willingness to move should be documented for the vet."
            ),
            red_flags=["worsening pain", "refuses to move", "cannot rest", "post-op decline"],
            what_to_record=["activity change", "sleep/rest", "appetite", "mobility", "reaction to handling", "exercise tolerance"],
            vet_discussion_topics=["post-op pain control", "rehab tolerance", "environment modification", "comfort assessment"],
        ),
        ProfessionalCareReference(
            reference_id="ref_skin_merck_001",
            source_name="Merck Veterinary Manual - Tumors of the Skin in Dogs",
            source_url="https://www.merckvetmanual.com/dog-owners/skin-disorders-of-dogs/tumors-of-the-skin-in-dogs",
            domain="skin_lump",
            symptom_signals=["skin_lump"],
            summary=(
                "Skin lumps and irritated bumps vary widely, so tracking change over time and veterinary "
                "assessment are more useful than guessing the type from appearance alone."
            ),
            red_flags=["rapid growth", "bleeding", "open wound", "pain", "pet seems unwell"],
            what_to_record=["size", "location", "color", "texture", "itchiness", "pain", "photos over time"],
            vet_discussion_topics=["skin mass", "cyst", "infection", "allergy", "trauma"],
        ),
        ProfessionalCareReference(
            reference_id="ref_urinary_cornell_001",
            source_name="Cornell Feline Health Center - Feline Lower Urinary Tract Disease",
            source_url=(
                "https://www.vet.cornell.edu/departments-centers-and-institutes/"
                "cornell-feline-health-center/health-information/feline-health-topics/"
                "feline-lower-urinary-tract-disease"
            ),
            domain="urinary",
            symptom_signals=["urinary", "cannot_pee", "bloody_urine"],
            summary=(
                "Cats that strain, make frequent attempts, or pass little/no urine need conservative "
                "triage because urethral obstruction can become urgent."
            ),
            red_flags=["cannot pee", "little or no urine", "blood in urine", "painful straining", "vomiting or collapse"],
            what_to_record=["last urination", "amount", "straining", "blood", "litter box attempts", "pain signs"],
            vet_discussion_topics=["urinary obstruction", "FLUTD", "UTI discussion", "bladder stones"],
        ),
        ProfessionalCareReference(
            reference_id="ref_respiratory_merck_001",
            source_name="Merck Veterinary Manual - Clinical Signs of Respiratory Disease",
            source_url=(
                "https://www.merckvetmanual.com/respiratory-system/respiratory-system-introduction/"
                "clinical-signs-of-respiratory-disease-in-animals"
            ),
            domain="respiratory",
            symptom_signals=["respiratory", "breathing_hard"],
            summary=(
                "Coughing and breathing changes can come from many respiratory or systemic causes; "
                "increased breathing effort is a reason for urgent veterinary triage."
            ),
            red_flags=["labored breathing", "blue or pale gums", "collapse", "severe distress", "rapid worsening"],
            what_to_record=["resting breathing rate", "cough frequency", "gum color", "energy", "appetite", "triggers"],
            vet_discussion_topics=["respiratory infection", "airway irritation", "heart/lung concern", "allergy"],
        ),
        ProfessionalCareReference(
            reference_id="ref_neurologic_merck_001",
            source_name="Merck Veterinary Manual - Emergency Triage and Seizures",
            source_url=(
                "https://www.merckvetmanual.com/emergency-medicine-and-critical-care/"
                "evaluation-and-initial-treatment-of-small-animal-emergency-patients/"
                "initial-triage-and-resuscitation-of-small-animal-emergency-patients"
            ),
            domain="neurologic",
            symptom_signals=["seizure", "convulsion", "neurologic"],
            summary=(
                "Seizure-like events need careful history because collapse, fainting, toxin exposure, "
                "or neurologic disease can look similar and may need urgent veterinary triage."
            ),
            red_flags=["seizure lasts several minutes", "repeated seizures", "does not recover", "collapse", "possible toxin exposure"],
            what_to_record=["start time", "duration", "video if safe", "recovery time", "possible exposure", "previous episodes"],
            vet_discussion_topics=["seizure-like episode", "syncope discussion", "toxin exposure", "neurologic evaluation"],
        ),
        ProfessionalCareReference(
            reference_id="ref_abdominal_bloat_vca_001",
            source_name="VCA Animal Hospitals - Gastric Dilatation and Volvulus in Dogs",
            source_url="https://vcahospitals.com/know-your-pet/gastric-dilatation-and-volvulus-in-dogs",
            domain="abdominal",
            symptom_signals=["abdominal_distension", "bloat", "unproductive_vomiting"],
            summary=(
                "A swollen abdomen, distress, and repeated retching without producing vomit are "
                "patterns owners should treat as urgent veterinary discussion points."
            ),
            red_flags=["hard or swollen abdomen", "unproductive retching", "restlessness", "weakness", "collapse"],
            what_to_record=["onset time", "belly appearance", "retching attempts", "meal/exercise timing", "restlessness", "gum color"],
            vet_discussion_topics=["bloat/GDV", "abdominal pain", "emergency triage", "deep-chested breed risk"],
        ),
        ProfessionalCareReference(
            reference_id="ref_abdominal_bloat_cornell_001",
            source_name="Cornell Riney Canine Health Center - GDV or Bloat",
            source_url=(
                "https://www.vet.cornell.edu/departments-centers-and-institutes/"
                "riney-canine-health-center/canine-health-information/"
                "gastric-dilatation-volvulus-gdv-or-bloat"
            ),
            domain="abdominal",
            symptom_signals=["abdominal_distension", "bloat", "unproductive_vomiting"],
            summary=(
                "GDV/bloat is a possible emergency discussion topic when a dog has abdominal "
                "distension and signs of distress or unproductive vomiting."
            ),
            red_flags=["distended abdomen", "retching", "pain", "restlessness", "shock signs"],
            what_to_record=["breed/size", "time since meal", "exercise timing", "retching", "belly size change", "energy"],
            vet_discussion_topics=["GDV", "bloat", "abdominal emergency", "surgical emergency discussion"],
        ),
        ProfessionalCareReference(
            reference_id="ref_eye_emergency_vca_001",
            source_name="VCA Animal Hospitals - Common Emergencies in Dogs",
            source_url="https://vcahospitals.com/premier/know-your-pet/common-emergencies-in-dogs",
            domain="eye",
            symptom_signals=["eye_injury", "vision_loss", "eye_pain"],
            summary=(
                "Eye trauma, sudden vision changes, bulging eyes, or severe eye pain should be "
                "handled as urgent veterinary discussion points because vision can be at risk."
            ),
            red_flags=["eye bulging", "sudden blindness", "severe pain", "blood or puncture", "keeps eye closed"],
            what_to_record=["which eye", "injury timing", "visible wound", "squinting", "vision change", "photos if safe"],
            vet_discussion_topics=["eye trauma", "corneal injury", "glaucoma discussion", "vision loss", "urgent eye exam"],
        ),
    ]
