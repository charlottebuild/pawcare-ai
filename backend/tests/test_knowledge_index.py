from pathlib import Path

from pawcare.services import KnowledgePackLoader, LocalKnowledgeIndex


def _index() -> LocalKnowledgeIndex:
    return LocalKnowledgeIndex(records=KnowledgePackLoader().load_seed_records())


def test_health_records_match_all_core_domains() -> None:
    index = _index()
    cases = [
        ("vomiting and diarrhea, could it be gastroenteritis?", "gi"),
        ("lump under tongue and drooling, could it be salivary mucocele?", "oral_neck"),
        ("post-op ACL leg is not weight bearing, should I worry?", "mobility"),
        ("new itchy skin lump, what might this be?", "skin_lump"),
        ("cat cannot pee and has blood in urine, is there any problem?", "urinary"),
        ("coughing and breathing hard, what might this be?", "respiratory"),
    ]

    for query_text, domain in cases:
        matches = index.search(query_text=query_text, kinds={"professional"}, limit=5)
        assert any(match.record.domain == domain for match in matches)


def test_behavior_records_match_specific_context_before_history() -> None:
    index = _index()

    matches = index.search(
        query_text="resource_guarding stress_signals frozen lip_licking social_interaction",
        kinds={"behavior"},
        limit=3,
    )

    assert matches[0].record.domain == "resource_guarding"
    assert any(match.record.domain == "behavior_history" for match in matches)


def test_community_cases_match_seeded_symptom_domains() -> None:
    index = _index()
    cases = [
        ("ACL post-op non weight bearing", "case_acl_postop_001"),
        ("head withdrawal tongue lump salivary", "case_oral_neck_001"),
        ("cannot pee blood in urine", "case_urinary_001"),
        ("vomiting diarrhea GI", "case_gi_001"),
        ("breathing hard coughing", "case_respiratory_001"),
        ("skin lump itching", "case_skin_lump_001"),
    ]

    for query_text, record_id in cases:
        matches = index.search(
            query_text=query_text,
            kinds={"community_case"},
            limit=5,
        )
        assert any(match.record.record_id == record_id for match in matches)


def test_load_json_records_for_manual_import(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        """
        [
          {
            "record_id": "manual_case_001",
            "kind": "community_case",
            "domain": "mobility",
            "source_name": "Manual ACL case",
            "source_url": "https://example.com/manual",
            "signals": ["acl", "post_op"],
            "summary": "Short manual summary only."
          }
        ]
        """,
        encoding="utf-8",
    )

    records = KnowledgePackLoader().load_json_records(path)

    assert records[0].record_id == "manual_case_001"
    assert records[0].summary == "Short manual summary only."
