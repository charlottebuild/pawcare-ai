from pathlib import Path

from pawcare.evaluation.golden_runner import load_cases, run_golden_cases


def test_golden_cases_file_loads_expected_scenarios() -> None:
    cases = load_cases()

    assert len(cases) >= 10
    assert {case["target_layer"] for case in cases} == {"service", "api"}
    assert {case["case_id"] for case in cases} >= {
        "svc_nsaid_bloody_stool_001",
        "svc_acl_postop_non_weight_bearing_001",
        "svc_cat_cannot_pee_001",
        "api_oral_care_context_001",
    }


def test_golden_dataset_runner_passes_all_cases() -> None:
    summary = run_golden_cases()

    assert summary.passed, summary.report()


def test_golden_dataset_runner_reports_readable_failures(tmp_path: Path) -> None:
    failing_cases = [
        {
            "case_id": "intentional_failure",
            "description": "Used to verify failure reporting.",
            "target_layer": "service",
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
