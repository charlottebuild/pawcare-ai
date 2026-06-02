from __future__ import annotations

from dataclasses import asdict

from pawcare.schemas.state import (
    BodyLanguageSignal,
    Observation,
    ObservationCategory,
    ResourceType,
    VocalizationSignal,
)
from pawcare.services.case_models import BehaviorCareReference, BehaviorReferenceMatch
from pawcare.services.knowledge_adapters import behavior_reference_to_record
from pawcare.services.knowledge_fts_index import (
    SQLiteKnowledgeFTSIndex,
    seed_professional_knowledge_documents,
)
from pawcare.services.knowledge_index import KnowledgeIndex, LocalKnowledgeIndex
from pawcare.skills.symptom_understanding import normalize_identifier


class BehaviorReferenceService:
    """Curated behavior references used as worker-agent context."""

    def __init__(
        self,
        *,
        references: list[BehaviorCareReference] | None = None,
        knowledge_index: KnowledgeIndex | None = None,
        fts_index: SQLiteKnowledgeFTSIndex | None = None,
    ) -> None:
        self.references = references or seed_behavior_references()
        self.knowledge_index = knowledge_index or LocalKnowledgeIndex(
            records=[behavior_reference_to_record(reference) for reference in self.references]
        )
        self.fts_index = fts_index or SQLiteKnowledgeFTSIndex()
        if fts_index is None:
            self.fts_index.ingest_documents(seed_professional_knowledge_documents())

    def find_matches(
        self,
        *,
        observations: list[Observation],
        limit: int = 3,
    ) -> list[BehaviorReferenceMatch]:
        query_terms = self._terms_from_observations(observations)
        if not query_terms:
            return []
        matches = self.knowledge_index.search(
            query_text=" ".join(sorted(query_terms)),
            kinds={"behavior"},
            limit=limit,
        )
        fts_matches = self.fts_index.search(
            query_text=" ".join(sorted(query_terms)),
            domains={"resource_guarding"},
            limit=limit,
        )
        return [
            self._to_match(match)
            for match in [*matches, *fts_matches]
            if set(match.matched_signals) & query_terms
        ][:limit]

    def as_payload(
        self,
        matches: list[BehaviorReferenceMatch],
    ) -> list[dict[str, object]]:
        return [asdict(match) for match in matches]

    def _terms_from_observations(self, observations: list[Observation]) -> set[str]:
        terms: set[str] = set()
        for observation in observations:
            if observation.category != ObservationCategory.social_interaction:
                continue
            context = observation.social_context
            if context is None:
                continue
            terms.add("social_interaction")
            body_language = set(context.signals.body_language)
            vocalization = set(context.signals.vocalization)
            for signal in body_language:
                terms.add(str(signal))
            for signal in vocalization:
                terms.add(str(signal))
            if context.resource_involved.present and context.resource_involved.type != ResourceType.none:
                terms.add("resource_context")
                terms.add("resource_guarding")
            if {
                BodyLanguageSignal.play_bow.value,
                BodyLanguageSignal.loose_body.value,
            }.issubset(body_language):
                terms.add("appropriate_play")
            if body_language & {
                BodyLanguageSignal.lip_licking.value,
                BodyLanguageSignal.yawning.value,
                BodyLanguageSignal.whale_eye.value,
                BodyLanguageSignal.frozen.value,
                BodyLanguageSignal.avoidance.value,
                BodyLanguageSignal.ears_back.value,
                BodyLanguageSignal.tail_tucked.value,
                BodyLanguageSignal.puffed_tail.value,
                BodyLanguageSignal.flattened_ears.value,
                BodyLanguageSignal.hiding.value,
            }:
                terms.add("stress_signals")
            if body_language & {
                BodyLanguageSignal.air_snap.value,
                BodyLanguageSignal.muzzle_punch.value,
            } or vocalization & {
                VocalizationSignal.growl.value,
                VocalizationSignal.snarl.value,
                VocalizationSignal.yelp.value,
            }:
                terms.add("escalation_signal")
        return {normalize_identifier(term) for term in terms}

    def _to_match(self, match) -> BehaviorReferenceMatch:
        record = match.record
        return BehaviorReferenceMatch(
            reference_id=record.record_id,
            source_name=record.source_name,
            source_url=record.source_url,
            domain=record.domain,
            summary=record.summary,
            matched_signals=list(match.matched_signals),
            management_notes=list(record.record_fields),
            escalation_signals=list(record.red_flags),
            relevance_level=match.relevance_level,
        )


def seed_behavior_references() -> list[BehaviorCareReference]:
    return [
        BehaviorCareReference(
            reference_id="beh_ref_stress_001",
            source_name="AAHA - Canine and Feline Behavior Management Guidelines",
            source_url="https://www.aaha.org/resources/2015-aaha-canine-and-feline-behavior-management-guidelines/behavior-management-home-2/",
            domain="stress_signals",
            behavior_signals=[
                "stress_signals",
                "lip_licking",
                "yawning",
                "whale_eye",
                "frozen",
                "avoidance",
                "ears_back",
                "tail_tucked",
            ],
            summary=(
                "Subtle stress signals should be treated as meaningful context even when there "
                "is no growling or snapping."
            ),
            management_notes=[
                "increase distance",
                "reduce social pressure",
                "watch whether the pet can relax",
            ],
            escalation_signals=["freezing persists", "growling", "snapping", "cannot settle"],
        ),
        BehaviorCareReference(
            reference_id="beh_ref_resource_001",
            source_name="Merck Veterinary Manual - Behavior Problems in Dogs",
            source_url="https://www.merckvetmanual.com/dog-owners/behavior-of-dogs/behavior-problems-in-dogs",
            domain="resource_guarding",
            behavior_signals=["resource_context", "resource_guarding", "frozen", "growl", "stiff_body"],
            summary=(
                "Food, chews, toys, resting spots, and owner attention can increase social tension; "
                "management should prevent pressure around valued resources."
            ),
            management_notes=[
                "separate pets around high-value resources",
                "remove shared pressure points",
                "avoid testing or taking items by force",
            ],
            escalation_signals=["growling", "air snap", "bite attempt", "repeated guarding"],
        ),
        BehaviorCareReference(
            reference_id="beh_ref_play_001",
            source_name="AAHA - Canine and Feline Behavior Management Guidelines",
            source_url="https://www.aaha.org/resources/2015-aaha-canine-and-feline-behavior-management-guidelines/behavior-management-home-2/",
            domain="appropriate_play",
            behavior_signals=["appropriate_play", "play_bow", "loose_body"],
            summary=(
                "Loose bodies, play bows, pauses, and role switching are more reassuring than "
                "stiff, one-sided pursuit."
            ),
            management_notes=[
                "keep play supervised",
                "pause if arousal rises",
                "watch for role switching and relaxed recovery",
            ],
            escalation_signals=["stiff chasing", "one pet cannot disengage", "yelping", "snapping"],
        ),
        BehaviorCareReference(
            reference_id="beh_ref_cat_stress_001",
            source_name="Cat Friendly Homes - Understanding Feline Behavior",
            source_url="https://catfriendly.com/cat-friendly-homes/understanding-feline-behavior/",
            domain="cat_stress",
            behavior_signals=["puffed_tail", "flattened_ears", "hiding", "hissing", "stress_signals"],
            summary=(
                "Cats often show stress through hiding, flattened ears, puffed tail, freezing, or hissing; "
                "distance and escape routes matter."
            ),
            management_notes=[
                "provide hiding and vertical space",
                "reduce approach pressure",
                "separate from stressful animals if signals persist",
            ],
            escalation_signals=["hissing escalates", "swatting", "refuses food", "cannot leave hiding"],
        ),
        BehaviorCareReference(
            reference_id="beh_ref_history_001",
            source_name="Merck Veterinary Manual - Diagnosing Behavior Problems in Dogs",
            source_url="https://www.merckvetmanual.com/dog-owners/behavior-of-dogs/diagnosing-behavior-problems-in-dogs",
            domain="behavior_history",
            behavior_signals=["social_interaction", "stress_signals", "escalation_signal"],
            summary=(
                "Behavior interpretation should be grounded in a history: onset, duration, frequency, "
                "triggers, intensity, pattern changes, and what stopped the episode."
            ),
            management_notes=[
                "record episode frequency and duration",
                "capture triggers and distance",
                "note what helped the pet recover",
            ],
            escalation_signals=["pattern worsens", "episode duration increases", "injury risk appears"],
        ),
        BehaviorCareReference(
            reference_id="beh_ref_anxiety_cornell_001",
            source_name="Cornell Riney Canine Health Center - Anxious Behavior",
            source_url=(
                "https://www.vet.cornell.edu/departments-centers-and-institutes/"
                "riney-canine-health-center/canine-health-topics/anxious-behavior-how-help-your-dog-cope-unsettling-situations"
            ),
            domain="anxiety_context",
            behavior_signals=["stress_signals", "avoidance", "pacing", "whining", "hiding"],
            summary=(
                "Anxiety-like behavior can show up as distress, avoidance, vocalizing, pacing, "
                "destructive behavior, or changes when the environment shifts."
            ),
            management_notes=[
                "reduce triggers when possible",
                "give predictable routines",
                "track whether signs improve after distance/rest",
            ],
            escalation_signals=["panic persists", "self-injury", "cannot eat or rest", "aggression appears"],
        ),
    ]
