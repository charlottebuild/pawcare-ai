from __future__ import annotations

from pawcare.schemas.state import (
    FinalRecommendation,
    OwnerContactPreferences,
    RiskAssessment,
    SafetyFinalStatus,
    SafetyReview,
)


class CommunicationAgent:
    """Formats safety-approved recommendations for owners or sitters."""

    agent_name = "CommunicationAgent"

    def format_owner_message(
        self,
        *,
        risk_assessment: RiskAssessment,
        safety_review: SafetyReview,
        owner_preferences: OwnerContactPreferences | None = None,
    ) -> FinalRecommendation:
        if safety_review.final_status == SafetyFinalStatus.blocked_needs_human_review:
            raise ValueError("Cannot format owner message for blocked recommendation")

        summary = self._summary_from_risk(risk_assessment)
        recommendation = self._recommendation_from_action(risk_assessment)
        owner_message = self._owner_message(
            risk_assessment=risk_assessment,
            owner_preferences=owner_preferences,
        )

        return FinalRecommendation(
            risk_level=risk_assessment.risk_level,
            risk_band=risk_assessment.risk_band,
            summary=summary,
            recommendation=recommendation,
            owner_message=owner_message,
            escalation_conditions=list(risk_assessment.escalation_conditions),
            safety_checked=True,
            source_guideline_ids=list(risk_assessment.source_guideline_ids),
        )

    def _summary_from_risk(self, risk_assessment: RiskAssessment) -> str:
        if risk_assessment.risk_factors:
            return "Observed concern: " + "; ".join(risk_assessment.risk_factors) + "."
        if risk_assessment.protective_factors:
            return (
                "Current interaction includes reassuring signals: "
                + "; ".join(risk_assessment.protective_factors)
                + "."
            )
        return "The current observation needs continued monitoring."

    def _recommendation_from_action(self, risk_assessment: RiskAssessment) -> str:
        action_map = {
            "separate_and_notify_owner": (
                "Separate the pets calmly, prevent shared access to high-value items, "
                "and notify the owner."
            ),
            "manage_environment_and_monitor": (
                "Increase distance around high-value items, manage the environment, "
                "and continue monitoring body language."
            ),
            "continue_monitoring": (
                "Continue monitoring and keep the interaction calm and supervised."
            ),
            "monitor_and_collect_more_information": (
                "Continue monitoring and collect more detail before escalating the interpretation."
            ),
        }
        return action_map.get(
            risk_assessment.recommended_action,
            "Continue monitoring and follow the listed escalation conditions.",
        )

    def _owner_message(
        self,
        *,
        risk_assessment: RiskAssessment,
        owner_preferences: OwnerContactPreferences | None,
    ) -> str:
        if any("known veterinary diagnosis context" in factor for factor in risk_assessment.risk_factors):
            return self._known_condition_followup_message(risk_assessment)

        if any(
            guideline_id.startswith("GL_CONDITION_")
            for guideline_id in risk_assessment.source_guideline_ids
        ):
            return self._condition_triage_message(risk_assessment)

        if (
            "GL_ACL_POSTOP_001" in risk_assessment.source_guideline_ids
            and any("rehabilitation difficulty" in factor for factor in risk_assessment.risk_factors)
        ):
            return self._post_op_rehab_message(risk_assessment)

        tone = owner_preferences.tone_preference if owner_preferences else None
        prefix = "Quick update:"
        if tone == "calm_and_brief":
            prefix = "Quick update:"

        if risk_assessment.risk_band in {"high", "urgent"}:
            urgency = "I am treating this as something that needs prompt attention."
        elif risk_assessment.risk_band == "moderate":
            urgency = "I am monitoring this closely."
        else:
            urgency = "I will keep an eye on it."

        observed = self._summary_from_risk(risk_assessment)
        escalation = ""
        if risk_assessment.escalation_conditions:
            escalation = (
                " I will update you if "
                + ", ".join(risk_assessment.escalation_conditions[:3])
                + "."
            )

        return f"{prefix} {observed} {urgency}{escalation}"

    def _post_op_rehab_message(self, risk_assessment: RiskAssessment) -> str:
        escalation = ""
        if risk_assessment.escalation_conditions:
            escalation = (
                " Please check with the surgical veterinarian if "
                + ", ".join(risk_assessment.escalation_conditions[-1:])
                + ", or if the prescribed exercises still cannot be done."
            )

        return (
            "Quick update: I reviewed the post-op recovery and lameness guidance linked to "
            "GL_ACL_POSTOP_001 and GL_LAMENESS_001. This sounds like difficulty with prescribed "
            "rehab exercises rather than a simple status update. Keep following the veterinarian's "
            "specific exercise plan, but make the session easier: try very short sets, use a small "
            "treat to guide the movement, keep him calm and distracted, and choose a time when he "
            "seems more comfortable. If the vet has already approved warm or cold compresses, doing "
            "the exercise after the painful period settles may help him tolerate it better. Do not "
            "force through struggling or pain."
            + escalation
        )

    def _condition_triage_message(self, risk_assessment: RiskAssessment) -> str:
        profile = self._condition_profile(risk_assessment.source_guideline_ids)
        urgent_prefix = (
            "This has urgent red flags.\n\n"
            if risk_assessment.risk_band in {"high", "urgent"}
            else ""
        )
        escalation = (
            "When to contact a vet urgently:\n- "
            + "; ".join(risk_assessment.escalation_conditions[:4])
            + "."
            if risk_assessment.escalation_conditions
            else "When to contact a vet urgently:\n- If symptoms worsen, combine with low energy, pain, blood, breathing trouble, or refusal to eat or drink."
        )
        return (
            f"{urgent_prefix}I can't diagnose from the app.\n\n"
            "Possible categories to discuss with a veterinarian:\n"
            f"- {', '.join(profile['possible'])}.\n\n"
            "Check whether you see:\n"
            f"- {profile['watch']}.\n\n"
            "What to record before the visit:\n"
            f"- {', '.join(profile['record'])}.\n\n"
            f"{escalation}"
        )

    def _known_condition_followup_message(self, risk_assessment: RiskAssessment) -> str:
        profile = self._condition_profile(risk_assessment.source_guideline_ids)
        escalation = (
            "Contact the veterinarian promptly if "
            + "; ".join(risk_assessment.escalation_conditions[:4])
            + "."
            if risk_assessment.escalation_conditions
            else "Contact the veterinarian promptly if swelling grows quickly, pain increases, eating or swallowing changes, breathing changes, bleeding, low energy, or refusal to eat or drink appears."
        )
        return (
            "I will treat this as a veterinarian-diagnosed condition already on the care plan, "
            "not as a new app diagnosis. Follow the veterinarian's instructions, keep recording changes, "
            f"and track: {', '.join(profile['record'])}. "
            f"Watch for: {profile['watch']}. "
            f"{escalation}"
        )

    def _condition_profile(self, guideline_ids: list[str]) -> dict[str, list[str] | str]:
        profiles: dict[str, dict[str, list[str] | str]] = {
            "GL_CONDITION_GI_001": {
                "possible": ["dietary upset", "gastroenteritis", "parasites", "foreign material", "medication side effects", "infectious disease"],
                "watch": "vomiting frequency, stool quality, appetite, water intake, energy, blood, black/tarry stool, and dehydration signs",
                "record": ["timing", "frequency", "stool photos if helpful", "appetite", "water intake", "energy", "medication use", "possible exposures"],
            },
            "GL_CONDITION_ORAL_NECK_001": {
                "possible": ["salivary mucocele", "dental or oral disease", "trauma", "abscess", "lymph node swelling", "another mass"],
                "watch": "rapid enlargement, pain, drooling, trouble eating, trouble swallowing, breathing changes, bleeding, or low energy",
                "record": ["location", "size", "firmness", "whether it moves", "pain", "drooling", "eating or swallowing changes", "growth speed"],
            },
            "GL_CONDITION_MOBILITY_001": {
                "possible": ["strain", "joint injury", "paw injury", "post-operative complication", "pain"],
                "watch": "weight-bearing, pain signs, swelling, sudden worsening, and activity changes",
                "record": ["affected limb", "weight-bearing ability", "pain signs", "swelling", "recent activity", "recent injury or surgery"],
            },
            "GL_CONDITION_SKIN_LUMP_001": {
                "possible": ["allergy", "insect bite", "skin infection", "cyst", "trauma", "mass"],
                "watch": "rapid growth, redness, heat, pain, bleeding, discharge, itchiness, and behavior changes",
                "record": ["size", "location", "color", "texture", "photos", "itchiness", "pain", "discharge", "growth speed"],
            },
            "GL_CONDITION_URINARY_001": {
                "possible": ["urinary tract irritation or infection", "bladder stones", "inflammation", "urinary blockage"],
                "watch": "straining, blood, frequent trips, accidents, pain, and whether urine is actually passing",
                "record": ["frequency", "amount", "straining", "blood", "accidents", "water intake", "whether urine is passing"],
            },
            "GL_CONDITION_RESPIRATORY_001": {
                "possible": ["airway irritation", "respiratory infection", "heart or lung concern", "allergy", "foreign material"],
                "watch": "breathing effort, cough frequency, gum color, collapse, low energy, and worsening signs",
                "record": ["cough timing", "frequency", "triggers", "resting breathing rate", "gum color", "energy", "appetite", "exposures"],
            },
        }
        for guideline_id in guideline_ids:
            if guideline_id in profiles:
                return profiles[guideline_id]
        return profiles["GL_CONDITION_GI_001"]
