from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import PetRecord, ProfessionalReferenceService, SimilarCaseService


def _pet() -> PetRecord:
    return PetRecord(
        pet_id="pet_123",
        user_id="user_123",
        dog_profile=DogProfile(
            id="pet_123",
            name="Heidou",
            species="dog",
            breed="Toy Poodle",
        ),
        behavioral_baseline=BehavioralBaseline(),
        health_baseline=HealthBaseline(
            normal_appetite="normal",
            normal_stool_quality="firm",
            normal_activity_level="medium",
            known_medical_notes=["ACL post-op recovery"],
        ),
    )


def test_matches_professional_references_for_all_condition_domains() -> None:
    service = ProfessionalReferenceService()
    cases = [
        ("vomiting and diarrhea, could it be gastroenteritis?", "gi"),
        ("drooling and a lump under tongue, could it be salivary mucocele?", "oral_neck"),
        ("post-op ACL leg is not weight bearing, should I worry?", "mobility"),
        ("new itchy skin lump, what might this be?", "skin_lump"),
        ("cat cannot pee and has blood in urine, is there any problem?", "urinary"),
        ("coughing and breathing hard, what might this be?", "respiratory"),
        ("Heidou collapsed and started shaking uncontrollably.", "neurologic"),
        ("Her belly is hard and she is trying to vomit but nothing comes out.", "abdominal"),
        ("NiaoNiao has an eye injury and cannot see well.", "eye"),
    ]

    for raw_text, domain in cases:
        matches = service.find_matches(raw_text=raw_text, pet=_pet())
        assert matches
        assert matches[0].domain == domain
        assert matches[0].source_url.startswith("https://")
        assert matches[0].red_flags
        assert matches[0].what_to_record
        assert matches[0].vet_discussion_topics


def test_plain_status_update_does_not_return_professional_references() -> None:
    matches = ProfessionalReferenceService().find_matches(
        raw_text="Heidou did not have breakfast this morning.",
        pet=_pet(),
    )

    assert matches == []


def test_abnormal_signals_return_professional_references_without_question_intent() -> None:
    service = ProfessionalReferenceService()

    urinary = service.find_matches(raw_text="猫猫一天没上厕所", pet=_pet())
    mobility = service.find_matches(raw_text="狗狗一只脚落不了地", pet=_pet())
    gi = service.find_matches(raw_text="Heidou has bloody stool", pet=_pet())
    neurologic = service.find_matches(raw_text="Heidou is convulsing", pet=_pet())
    abdominal = service.find_matches(raw_text="her belly is hard and bloated", pet=_pet())
    eye = service.find_matches(raw_text="NiaoNiao has an eye injury", pet=_pet())

    assert urinary[0].domain == "urinary"
    assert mobility[0].domain == "mobility"
    assert gi[0].domain == "gi"
    assert neurologic[0].domain == "neurologic"
    assert abdominal[0].domain == "abdominal"
    assert eye[0].domain == "eye"


def test_output_is_structured_summary_not_full_source_text() -> None:
    service = ProfessionalReferenceService()
    matches = service.find_matches(
        raw_text="cat couldn't pee all day, should I worry?",
        pet=_pet(),
    )
    payload = service.as_payload(matches)

    first = payload[0]
    assert "source_url" in first
    assert "summary" in first
    assert "what_to_record" in first
    assert "full_text" not in first
    assert "raw_text" not in first


def test_key_domains_return_professional_reference_and_similar_case() -> None:
    reference_service = ProfessionalReferenceService()
    case_service = SimilarCaseService()
    raw_text = "Heidou pulls his head back eating and has a tongue lump. Could it be salivary mucocele?"

    references = reference_service.find_matches(raw_text=raw_text, pet=_pet())
    cases = case_service.find_matches(raw_text=raw_text, pet=_pet())

    assert references[0].domain == "oral_neck"
    assert cases[0].case_id == "case_oral_neck_001"


def test_matches_patellar_luxation_and_pain_references() -> None:
    service = ProfessionalReferenceService()

    patella_matches = service.find_matches(
        raw_text="He is skipping on his back leg. Could it be patellar luxation?",
        pet=_pet(),
    )
    pain_matches = service.find_matches(
        raw_text="He is post-op and seems painful during rehab exercise. Should I worry?",
        pet=_pet(),
    )

    assert any("Patellar Luxation" in match.source_name for match in patella_matches)
    assert any("Pain Management" in match.source_name for match in pain_matches)


def test_matches_oral_pain_reference_without_copying_source_text() -> None:
    service = ProfessionalReferenceService()
    matches = service.find_matches(
        raw_text="He pulls his head back while eating and seems to have mouth pain. What might this be?",
        pet=_pet(),
    )

    assert any("Disorders of the Mouth" in match.source_name for match in matches)
    assert all(len(match.summary) < 280 for match in matches)


def test_hybrid_retrieval_recalls_oral_neck_from_messy_real_world_wording() -> None:
    matches = ProfessionalReferenceService().find_matches(
        raw_text="His chin looks swollen and he eats weird, could it be a saliva cyst?",
        pet=_pet(),
    )

    assert matches[0].domain == "oral_neck"
    assert any("salivary" in topic for topic in matches[0].vet_discussion_topics)
