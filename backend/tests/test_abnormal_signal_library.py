from pawcare.knowledge.abnormal_signals import (
    abnormal_care_context_terms,
    abnormal_signal_term_groups,
    seed_abnormal_signal_records,
)
from pawcare.services.professional_reference_service import seed_professional_references
from pawcare.services.similar_case_service import seed_community_cases
from pawcare.skills.symptom_understanding import (
    extract_canonical_terms,
    has_care_context_trigger,
)


def test_abnormal_signal_records_link_to_existing_references_and_cases() -> None:
    reference_ids = {
        reference.reference_id
        for reference in seed_professional_references()
    }
    case_ids = {case.case_id for case in seed_community_cases()}

    for record in seed_abnormal_signal_records():
        assert record.signal_id
        assert record.domain
        assert record.canonical_terms
        assert record.user_phrases
        assert record.safe_language
        assert set(record.reference_ids) <= reference_ids
        assert set(record.case_ids) <= case_ids


def test_abnormal_signal_term_groups_drive_care_context_triggers() -> None:
    groups = abnormal_signal_term_groups()

    assert "cannot_pee" in groups
    assert "一天没上厕所" in groups["cannot_pee"]
    assert "non_weight_bearing" in groups
    assert "一只脚落不了地" in groups["non_weight_bearing"]
    assert "cannot_pee" in abnormal_care_context_terms()
    assert "non_weight_bearing" in abnormal_care_context_terms()


def test_abnormal_signal_library_matches_real_user_phrases() -> None:
    examples = [
        ("猫猫一天没上厕所", "cannot_pee"),
        ("NiaoNiao has not gone to the bathroom today", "cannot_pee"),
        ("狗狗一只脚落不了地", "non_weight_bearing"),
        ("Heidou has bloody stool", "bloody_stool"),
        ("Niao Niao poo blood", "bloody_stool"),
        ("Heidou has blood in poop", "bloody_stool"),
        ("her breathing looks labored", "breathing_hard"),
        ("Heidou collapsed and started shaking uncontrollably", "seizure"),
        ("her belly is hard and she is trying to vomit but nothing comes out", "bloat"),
        ("NiaoNiao has an eye injury and cannot see well", "eye_injury"),
    ]

    for raw_text, expected_term in examples:
        assert has_care_context_trigger(raw_text)
        assert expected_term in extract_canonical_terms(raw_text)


def test_normal_daily_update_does_not_trigger_abnormal_signal_library() -> None:
    assert not has_care_context_trigger("Heidou ate breakfast and went for a walk.")
