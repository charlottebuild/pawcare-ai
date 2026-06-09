from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pawcare.evaluation.route_benchmark import run_route_benchmark


def test_route_benchmark_reports_route_latency_and_cost_estimates() -> None:
    report = run_route_benchmark()

    assert report["summary"]["passed"] is True
    assert report["summary"]["route_count"] >= 7
    assert report["summary"]["call_count"] >= 9
    assert report["summary"]["p50_ms"] >= 0
    assert report["summary"]["p95_ms"] >= 0
    assert "latency_summary" in report
    assert "route_scores" in report
    assert "case_results" in report
    assert "cost_summary" in report
    assert report["cost_summary"]["estimated_context_tokens"] > 0
    assert report["cost_summary"]["provider_billing_available"] is False
    assert "not provider billing" in report["cost_summary"]["note"]


def test_route_benchmark_records_care_context_cache_hit() -> None:
    report = run_route_benchmark()
    care_context_results = [
        result
        for result in report["case_results"]
        if result["route_name"] == "care_context"
    ]

    assert [result["cache_status"] for result in care_context_results] == [
        "miss",
        "hit",
    ]
    assert all(
        int(result["estimated_context_tokens"] or 0) > 0
        for result in care_context_results
    )
    assert report["cost_summary"]["cache_hits"] >= 1
    assert report["cost_summary"]["cache_misses"] >= 1


def test_route_benchmark_records_stream_events_without_internal_state() -> None:
    report = run_route_benchmark()
    stream_result = next(
        result
        for result in report["case_results"]
        if result["route_name"] == "message_stream"
    )
    rendered = json.dumps(report, sort_keys=True)

    assert stream_result["status_code"] == 200
    assert int(stream_result["event_count"] or 0) >= 2
    assert stream_result["final_event_seen"] is True
    assert "agent_outputs" not in rendered
    assert "proposed_update" not in rendered
    assert "safety_review" not in rendered


def test_route_benchmark_marks_normal_routes_with_zero_context_tokens() -> None:
    report = run_route_benchmark()
    normal_results = [
        result
        for result in report["case_results"]
        if result["route_name"] in {"create_user", "create_pet_dog", "list_pets"}
    ]

    assert normal_results
    assert all(result["estimated_context_tokens"] == 0 for result in normal_results)


def test_route_benchmark_writes_json_report(tmp_path: Path) -> None:
    report_path = tmp_path / "pawcare_route_benchmark.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pawcare.evaluation.route_benchmark",
            "--report-json",
            str(report_path),
        ],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert result.returncode == 0
    assert "PawCare route benchmark" in result.stdout
    assert report["summary"]["passed"] is True
    assert report["summary"]["route_count"] >= 7
    assert report["route_scores"]["care_context"]["call_count"] == 2
