from pathlib import Path

import json
import subprocess
import sys

from pawcare.evaluation.golden_runner import load_cases, run_golden_cases


def test_golden_cases_file_loads_expected_scenarios() -> None:
    cases = load_cases()

    assert len(cases) >= 40
    assert {case["target_layer"] for case in cases} == {"service", "api"}
    assert {case["case_id"] for case in cases} >= {
        "svc_nsaid_bloody_stool_001",
        "svc_acl_postop_non_weight_bearing_001",
        "svc_cat_cannot_pee_001",
        "api_oral_care_context_001",
        "api_eye_injury_care_context_001",
        "api_bloat_care_context_001",
        "api_seizure_care_context_001",
    }
    assert {case["category"] for case in cases} >= {
        "health_triage",
        "condition_triage",
        "behavior_safety",
        "care_context_retrieval",
        "normal_update",
    }
    assert all(case["category"] for case in cases)
    assert all(case["priority"] in {"high", "medium", "low"} for case in cases)
    assert all(case["metrics"] for case in cases)
    high_priority_text = " ".join(
        case["raw_text"].lower() for case in cases if case["priority"] == "high"
    )
    for red_flag_term in [
        "pee",
        "bloody stool",
        "leg",
        "breathing hard",
        "eye",
        "seizure",
        "bloated",
    ]:
        assert red_flag_term in high_priority_text


def test_golden_dataset_runner_passes_all_cases() -> None:
    summary = run_golden_cases()

    assert summary.passed, summary.report()
    assert summary.category_scores["health_triage"]["passed"] >= 11
    assert summary.category_scores["condition_triage"]["passed"] >= 10
    assert summary.category_scores["behavior_safety"]["passed"] >= 6
    assert summary.category_scores["care_context_retrieval"]["passed"] >= 9
    assert summary.category_scores["normal_update"]["passed"] >= 4
    assert summary.metric_scores["risk_classification"]["pass_rate"] == 1.0
    assert summary.metric_scores["safety_forbidden_text"]["pass_rate"] == 1.0
    assert "Metric scores:" in summary.report()
    assert summary.as_dict()["summary"]["passed"] is True


def test_golden_dataset_runner_reports_readable_failures(tmp_path: Path) -> None:
    failing_cases = [
        {
            "case_id": "intentional_failure",
            "description": "Used to verify failure reporting.",
            "target_layer": "service",
            "category": "health_triage",
            "priority": "high",
            "metrics": ["risk_classification", "guideline_grounding"],
            "pet_profile": {"id": "dog_mochi", "name": "Mochi", "species": "dog"},
            "raw_text": "Mochi barely touched breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
            "expected": {
                "status": "escalate",
                "must_include_guideline_ids": ["GL_DOES_NOT_EXIST"],
            },
        }
    ]
    path = tmp_path / "failing_golden_cases.json"
    path.write_text(__import__("json").dumps(failing_cases), encoding="utf-8")

    summary = run_golden_cases(cases_path=path)
    report = summary.report()

    assert not summary.passed
    assert "intentional_failure" in report
    assert "Expected status" in report
    assert "GL_DOES_NOT_EXIST" in report
    assert "failed_metrics: risk_classification, guideline_grounding" in report
    assert summary.high_priority_failures[0].case_id == "intentional_failure"


def test_golden_runner_writes_json_report(tmp_path: Path) -> None:
    report_path = tmp_path / "golden_report.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pawcare.evaluation.golden_runner",
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
    assert report["summary"]["passed"] is True
    assert "category_scores" in report
    assert "metric_scores" in report
    assert "case_results" in report
    assert report["metric_scores"]["care_context_retrieval"]["pass_rate"] == 1.0
