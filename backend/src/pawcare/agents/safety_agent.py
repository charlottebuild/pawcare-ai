from __future__ import annotations

from datetime import UTC, datetime

from pawcare.schemas.state import (
    FinalRecommendation,
    SafetyFinalStatus,
    SafetyReview,
    SafetyRewrite,
)


class SafetyAgent:
    """Constitutional safety worker for recommendation candidates."""

    diagnosis_terms = [
        "has parvo",
        "is parvo",
        "has cancer",
        "has gastroenteritis",
        "is gastroenteritis",
        "has salivary mucocele",
        "is salivary mucocele",
        "has uti",
        "is uti",
        "has acl tear",
        "has ccl tear",
        "is acl tear",
        "is ccl tear",
        "is patellar luxation",
        "has patellar luxation",
        "confirm this is patellar luxation",
        "has urinary blockage",
        "is urinary blockage",
        "has an infection",
        "is a stomach infection",
        "得了细小",
        "就是细小",
        "感染了",
    ]
    medication_terms = [
        "give 2 mg",
        "mg per",
        "dose",
        "dosage",
        "human anti-diarrhea medicine",
        "imodium",
        "pepto",
        "给它吃药",
        "剂量",
    ]
    reassurance_terms = [
        "don't worry",
        "it will be fine",
        "definitely normal",
        "nothing to worry about",
        "肯定没事",
        "不用担心",
        "一定正常",
    ]

    def review_recommendation(
        self, recommendation: FinalRecommendation
    ) -> SafetyReview:
        text = self._combined_text(recommendation).lower()
        blocked_content: list[str] = []
        rewrites: list[SafetyRewrite] = []

        diagnosis_present = self._contains_any(text, self.diagnosis_terms)
        medication_advice_present = self._contains_any(text, self.medication_terms)
        over_reassurance_present = self._contains_any(text, self.reassurance_terms)
        source_guideline_ids_present = bool(recommendation.source_guideline_ids)

        if diagnosis_present:
            blocked_content.append("diagnosis")
        if medication_advice_present:
            blocked_content.append("medication_advice")
        if not source_guideline_ids_present:
            blocked_content.append("missing_source_guideline_ids")

        if over_reassurance_present:
            rewrites.append(
                SafetyRewrite(
                    original="over-reassuring language",
                    replacement=(
                        "Use conservative monitoring language with clear escalation conditions."
                    ),
                )
            )

        if blocked_content:
            final_status = SafetyFinalStatus.blocked_needs_human_review
        elif rewrites:
            final_status = SafetyFinalStatus.approved_with_rewrites
        else:
            final_status = SafetyFinalStatus.approved

        return SafetyReview(
            safety_checked=True,
            checked_at=datetime.now(UTC).isoformat(),
            blocked_content=blocked_content,
            rewrites_applied=rewrites,
            diagnosis_present=diagnosis_present,
            medication_advice_present=medication_advice_present,
            over_reassurance_present=over_reassurance_present,
            source_guideline_ids_present=source_guideline_ids_present,
            final_status=final_status,
        )

    def _combined_text(self, recommendation: FinalRecommendation) -> str:
        return " ".join(
            item
            for item in [
                recommendation.summary,
                recommendation.recommendation or "",
                recommendation.owner_message or "",
                " ".join(recommendation.escalation_conditions),
            ]
            if item
        )

    def _contains_any(self, text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)
