from pawcare.agents import SafetyAgent
from pawcare.schemas.state import FinalRecommendation


def test_safety_agent_approves_grounded_non_diagnostic_recommendation() -> None:
    recommendation = FinalRecommendation(
        risk_level=6,
        risk_band="moderate",
        summary="Mochi showed stress signals when a larger dog approached her chew.",
        recommendation=(
            "Increase distance around high-value items, remove the chew during shared time, "
            "and continue monitoring body language."
        ),
        owner_message=(
            "Quick update: Mochi became tense when another dog came near her chew. "
            "I separated them calmly and will keep monitoring."
        ),
        escalation_conditions=[
            "growling, snapping, or lunging increases",
            "either dog cannot relax after separation",
        ],
        safety_checked=True,
        source_guideline_ids=[
            "GL_SOCIAL_STRESS_001",
            "GL_RESOURCE_GUARDING_001",
        ],
    )

    review = SafetyAgent().review_recommendation(recommendation)

    assert review.final_status == "approved"
    assert review.diagnosis_present is False
    assert review.medication_advice_present is False
    assert review.source_guideline_ids_present is True


def test_safety_agent_blocks_diagnosis() -> None:
    recommendation = FinalRecommendation(
        risk_level=8,
        risk_band="high",
        summary="Your dog has parvo.",
        recommendation="Contact a vet.",
        safety_checked=True,
        source_guideline_ids=["GL_VOMITING_001", "GL_STOOL_001"],
    )

    review = SafetyAgent().review_recommendation(recommendation)

    assert review.final_status == "blocked_needs_human_review"
    assert review.diagnosis_present is True
    assert "diagnosis" in review.blocked_content


def test_safety_agent_blocks_condition_triage_diagnosis_terms() -> None:
    recommendation = FinalRecommendation(
        risk_level=6,
        risk_band="moderate",
        summary="Your dog has salivary mucocele.",
        recommendation="Contact a vet.",
        owner_message="Your dog has UTI and has gastroenteritis.",
        escalation_conditions=["symptoms worsen"],
        safety_checked=True,
        source_guideline_ids=["GL_CONDITION_ORAL_NECK_001"],
    )

    review = SafetyAgent().review_recommendation(recommendation)

    assert review.diagnosis_present is True
    assert "diagnosis" in review.blocked_content


def test_safety_agent_blocks_related_case_diagnosis_phrasing() -> None:
    recommendation = FinalRecommendation(
        risk_level=6,
        risk_band="moderate",
        summary="Your dog has ACL tear.",
        recommendation="Similar cases confirm this is patellar luxation.",
        owner_message="Your dog has urinary blockage.",
        escalation_conditions=["symptoms worsen"],
        safety_checked=True,
        source_guideline_ids=["GL_CONDITION_MOBILITY_001"],
    )

    review = SafetyAgent().review_recommendation(recommendation)

    assert review.diagnosis_present is True
    assert "diagnosis" in review.blocked_content


def test_safety_agent_blocks_medication_dosage_advice() -> None:
    recommendation = FinalRecommendation(
        risk_level=5,
        risk_band="moderate",
        summary="Loose stool reported.",
        recommendation="Give 2 mg per 10 pounds of human anti-diarrhea medicine.",
        safety_checked=True,
        source_guideline_ids=["GL_MEDICATION_SAFETY_001"],
    )

    review = SafetyAgent().review_recommendation(recommendation)

    assert review.final_status == "blocked_needs_human_review"
    assert review.medication_advice_present is True
    assert "medication_advice" in review.blocked_content


def test_safety_agent_rewrites_over_reassurance() -> None:
    recommendation = FinalRecommendation(
        risk_level=3,
        risk_band="low",
        summary="One vomiting event reported.",
        recommendation="Don't worry, it will be fine.",
        escalation_conditions=["vomiting repeats", "energy drops"],
        safety_checked=True,
        source_guideline_ids=["GL_VOMITING_001"],
    )

    review = SafetyAgent().review_recommendation(recommendation)

    assert review.final_status == "approved_with_rewrites"
    assert review.over_reassurance_present is True
    assert review.rewrites_applied
