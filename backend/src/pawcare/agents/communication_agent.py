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
