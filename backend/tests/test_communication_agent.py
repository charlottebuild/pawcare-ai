import pytest

from pawcare.agents import CommunicationAgent
from pawcare.schemas.state import (
    OwnerContactPreferences,
    RiskAssessment,
    SafetyReview,
)


def test_communication_agent_formats_safety_approved_owner_message() -> None:
    risk = RiskAssessment(
        risk_level=6,
        risk_band="moderate",
        primary_risk_domain="social",
        risk_factors=["stress signals near high-value resource"],
        protective_factors=[],
        missing_information=["resource_guarding_history"],
        recommended_action="manage_environment_and_monitor",
        escalation_conditions=[
            "stress signals increase",
            "resource guarding repeats",
            "growling, snapping, or injury occurs",
        ],
        logic="Stress body-language signals appeared in a resource context.",
        source_guideline_ids=[
            "GL_SOCIAL_STRESS_001",
            "GL_RESOURCE_GUARDING_001",
        ],
    )
    safety_review = SafetyReview(
        safety_checked=True,
        diagnosis_present=False,
        medication_advice_present=False,
        over_reassurance_present=False,
        source_guideline_ids_present=True,
        final_status="approved",
    )

    recommendation = CommunicationAgent().format_owner_message(
        risk_assessment=risk,
        safety_review=safety_review,
        owner_preferences=OwnerContactPreferences(tone_preference="calm_and_brief"),
    )

    assert recommendation.risk_level == 6
    assert recommendation.risk_band == "moderate"
    assert recommendation.safety_checked is True
    assert recommendation.source_guideline_ids == [
        "GL_SOCIAL_STRESS_001",
        "GL_RESOURCE_GUARDING_001",
    ]
    assert "stress signals near high-value resource" in recommendation.owner_message
    assert "I am monitoring this closely" in recommendation.owner_message
    assert "resource guarding repeats" in recommendation.owner_message


def test_communication_agent_refuses_blocked_safety_review() -> None:
    risk = RiskAssessment(
        risk_level=8,
        risk_band="high",
        primary_risk_domain="health",
        risk_factors=["vomiting and lethargy"],
        recommended_action="separate_and_notify_owner",
        escalation_conditions=["symptoms worsen"],
        logic="High risk profile.",
        source_guideline_ids=["GL_VOMITING_001"],
    )
    blocked_review = SafetyReview(
        safety_checked=True,
        blocked_content=["diagnosis"],
        diagnosis_present=True,
        medication_advice_present=False,
        over_reassurance_present=False,
        source_guideline_ids_present=True,
        final_status="blocked_needs_human_review",
    )

    with pytest.raises(ValueError, match="blocked recommendation"):
        CommunicationAgent().format_owner_message(
            risk_assessment=risk,
            safety_review=blocked_review,
        )


def test_communication_agent_keeps_low_risk_play_message_conservative() -> None:
    risk = RiskAssessment(
        risk_level=2,
        risk_band="low",
        primary_risk_domain="social",
        risk_factors=[],
        protective_factors=[
            "loose body and play bow suggest appropriate play context",
        ],
        recommended_action="continue_monitoring",
        escalation_conditions=["play becomes one-sided", "stress signals appear"],
        logic="Loose body language and play bow are reassuring signs.",
        source_guideline_ids=["GL_SOCIAL_PLAY_001"],
    )
    safety_review = SafetyReview(
        safety_checked=True,
        diagnosis_present=False,
        medication_advice_present=False,
        over_reassurance_present=False,
        source_guideline_ids_present=True,
        final_status="approved",
    )

    recommendation = CommunicationAgent().format_owner_message(
        risk_assessment=risk,
        safety_review=safety_review,
    )

    assert recommendation.risk_band == "low"
    assert "I will keep an eye on it" in recommendation.owner_message
    assert "Don't worry" not in recommendation.owner_message
    assert "it will be fine" not in recommendation.owner_message
