from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import PetRecord, SimilarCaseService


def _pet() -> PetRecord:
    return PetRecord(
        pet_id="dog_heidou",
        user_id="user_123",
        dog_profile=DogProfile(
            id="dog_heidou",
            name="Heidou",
            species="dog",
            breed="Border Collie",
        ),
        behavioral_baseline=BehavioralBaseline(),
        health_baseline=HealthBaseline(
            normal_appetite="normal",
            normal_stool_quality="firm",
            normal_activity_level="medium",
            known_medical_notes=["ACL post-op recovery"],
        ),
    )


def test_matches_acl_and_patellar_related_mobility_cases() -> None:
    matches = SimilarCaseService().find_matches(
        raw_text=(
            "Heidou is one month post-op after ACL surgery and still will not put "
            "weight on the leg. Could it be patellar luxation too?"
        ),
        pet=_pet(),
    )

    case_ids = [match.case_id for match in matches]

    assert "case_acl_postop_001" in case_ids
    assert "case_patella_001" in case_ids
    assert matches[0].case_relevance_level == "high"
    assert matches[0].condition_discussion_priority == "discuss_soon"


def test_plain_status_update_does_not_trigger_similar_cases() -> None:
    matches = SimilarCaseService().find_matches(
        raw_text="Heidou did not have breakfast this morning.",
        pet=_pet(),
    )

    assert matches == []


def test_abnormal_signals_trigger_similar_cases_without_question_intent() -> None:
    service = SimilarCaseService()

    urinary = service.find_matches(raw_text="猫猫一天没上厕所", pet=_pet())
    mobility = service.find_matches(raw_text="狗狗一只脚落不了地", pet=_pet())
    gi = service.find_matches(raw_text="Heidou has bloody stool", pet=_pet())
    neurologic = service.find_matches(raw_text="Heidou is convulsing", pet=_pet())
    abdominal = service.find_matches(raw_text="her belly is hard and bloated", pet=_pet())
    eye = service.find_matches(raw_text="NiaoNiao has an eye injury", pet=_pet())

    assert urinary[0].case_id == "case_urinary_001"
    assert mobility[0].case_id in {"case_acl_postop_001", "case_patella_001"}
    assert gi[0].case_id == "case_gi_001"
    assert neurologic[0].case_id == "case_seizure_001"
    assert abdominal[0].case_id == "case_bloat_001"
    assert eye[0].case_id == "case_eye_injury_001"


def test_matches_oral_salivary_lump_case() -> None:
    matches = SimilarCaseService().find_matches(
        raw_text=(
            "Heidou suddenly shrinks his head while eating, tilts his head, drools, "
            "and I see a small lump under his tongue. Could it be salivary mucocele?"
        ),
        pet=_pet(),
    )

    assert matches[0].case_id == "case_oral_neck_001"
    assert "salivary_gland" in matches[0].possible_discussion_topics
    assert "trouble swallowing" in matches[0].red_flags


def test_matches_gi_urinary_respiratory_and_skin_domains() -> None:
    service = SimilarCaseService()

    gi = service.find_matches(raw_text="vomiting and diarrhea, what might this be?", pet=_pet())
    urinary = service.find_matches(
        raw_text="blood in urine and he cannot pee, should I worry?", pet=_pet()
    )
    respiratory = service.find_matches(
        raw_text="coughing and breathing hard, what might this be?", pet=_pet()
    )
    skin = service.find_matches(raw_text="new itchy skin lump, I am worried", pet=_pet())

    assert gi[0].case_id == "case_gi_001"
    assert urinary[0].case_id == "case_urinary_001"
    assert respiratory[0].case_id == "case_respiratory_001"
    assert skin[0].case_id == "case_skin_lump_001"


def test_matches_mistyped_couldnt_pee_question_to_urinary_case() -> None:
    service = SimilarCaseService()

    matches = service.find_matches(
        raw_text="niao niao couldnt' pee today,all day long ,is there any problem ?",
        pet=_pet(),
    )

    assert matches[0].case_id == "case_urinary_001"


def test_case_payload_contains_summary_and_link_not_full_source_text() -> None:
    service = SimilarCaseService()
    matches = service.find_matches(
        raw_text="head shrinking while eating and tongue lump, what might this be?",
        pet=_pet(),
    )
    payload = service.as_payload(matches)

    first = payload[0]
    assert first["source_url"].startswith("https://")
    assert "case_summary" in first
    assert "privacy_safe_snippet" in first
    assert "raw_text" not in first
    assert "full_text" not in first
