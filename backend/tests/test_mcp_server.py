from __future__ import annotations

from pawcare import mcp_server


def test_mcp_server_imports_and_registers_tools() -> None:
    assert hasattr(mcp_server, "mcp")
    assert {
        tool.name for tool in mcp_server.registry.tools
    } == {
        "screen_abnormal_signals",
        "search_care_context",
        "preview_pet_response",
        "run_golden_eval",
    }
    if hasattr(mcp_server.mcp, "tools"):
        assert {
            "screen_abnormal_signals",
            "search_care_context",
            "preview_pet_response",
            "run_golden_eval",
        }.issubset(set(mcp_server.mcp.tools))


def test_screen_abnormal_signals_handles_real_world_phrasing() -> None:
    urinary = mcp_server.screen_abnormal_signals(
        "NiaoNiao didn't pee all day.",
        species="cat",
    )
    urinary_ids = {
        signal["signal_id"] for signal in urinary["matched_signals"]
    }
    assert "cat_no_urination_24h" in urinary_ids

    bloody_stool = mcp_server.screen_abnormal_signals(
        "Mochi poo blood this morning.",
        species="dog",
    )
    bloody_ids = {
        signal["signal_id"] for signal in bloody_stool["matched_signals"]
    }
    assert "bloody_or_black_stool" in bloody_ids

    mobility = mcp_server.screen_abnormal_signals(
        "Mochi's leg won't touch floor after the walk.",
        species="dog",
    )
    mobility_ids = {
        signal["signal_id"] for signal in mobility["matched_signals"]
    }
    assert "non_weight_bearing_limb" in mobility_ids


def test_search_care_context_returns_professional_references_and_cases() -> None:
    oral_context = mcp_server.search_care_context(
        (
            "Mochi pulls his head back when eating, drools, and has a small "
            "lump under the tongue. Could it be salivary mucocele?"
        ),
        pet_profile={
            "id": "dog_mochi",
            "name": "Mochi",
            "species": "dog",
            "breed": "Toy Poodle",
        },
    )

    oral_domains = {
        reference["domain"]
        for reference in oral_context["professional_references"]
    }
    oral_topics = {
        topic
        for case in oral_context["related_cases"]
        for topic in case["possible_discussion_topics"]
    }
    assert "oral_neck" in oral_domains
    assert "salivary_gland" in oral_topics
    assert "not a diagnosis" in oral_context["non_diagnostic_notice"].lower()
    assert oral_context["context_summary"]

    eye_context = mcp_server.search_care_context(
        "Mochi has an eye scratch and cannot open the eye. Should I worry?",
        pet_profile={"id": "dog_mochi", "name": "Mochi", "species": "dog"},
    )
    eye_domains = {
        reference["domain"]
        for reference in eye_context["professional_references"]
    }
    eye_topics = {
        topic
        for case in eye_context["related_cases"]
        for topic in case["possible_discussion_topics"]
    }
    assert "eye" in eye_domains
    assert "eye_trauma" in eye_topics


def test_search_care_context_uses_semantic_cache_without_internal_fields() -> None:
    first = mcp_server.search_care_context(
        "Mochi poo blood this morning.",
        pet_profile={"id": "dog_mochi", "name": "Mochi", "species": "dog"},
    )
    second = mcp_server.search_care_context(
        "Mochi had bloody stool this morning.",
        pet_profile={"id": "dog_mochi", "name": "Mochi", "species": "dog"},
    )

    assert first["cache_status"] in {"miss", "hit"}
    assert second["cache_status"] == "hit"
    assert second["professional_references"][0]["domain"] == "gi"
    for forbidden_field in (
        "agent_outputs",
        "proposed_update",
        "safety_review",
        "response",
        "risk_band",
        "source_guideline_ids",
        "escalation_conditions",
    ):
        assert forbidden_field not in second


def test_preview_pet_response_uses_safety_chain_without_internal_fields() -> None:
    payload = mcp_server.preview_pet_response(
        "NiaoNiao couldn't pee today, she didn't pee all day. What happened?",
        pet_profile={
            "id": "cat_niaoniao",
            "name": "NiaoNiao",
            "species": "cat",
            "breed": "Domestic Shorthair",
        },
        timestamp="2026-06-02T10:00:00Z",
    )

    assert payload["status"] == "escalate"
    assert payload["risk_band"] in {"high", "urgent"}
    assert "GL_CONDITION_URINARY_001" in payload["source_guideline_ids"]
    for forbidden_field in ("agent_outputs", "proposed_update", "safety_review"):
        assert forbidden_field not in payload


def test_run_golden_eval_returns_lightweight_summary() -> None:
    payload = mcp_server.run_golden_eval(layer="all")

    assert payload["summary"]["passed"] is True
    assert payload["summary"]["total_count"] >= 50
    assert "risk_classification" in payload["metric_scores"]
    assert payload["latency_summary"]["case_count"] >= 50
    assert "quality_summary" in payload
    assert "case_results" not in payload
