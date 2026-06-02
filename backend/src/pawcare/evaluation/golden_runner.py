from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from pawcare.api import create_app
from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline
from pawcare.services import InMemoryPetRepository, LogProcessingService, PetRecord, UserAccount


DEFAULT_CASES_PATH = Path(__file__).with_name("golden_cases.json")


@dataclass(frozen=True)
class GoldenMetricResult:
    metric: str
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GoldenCaseResult:
    case_id: str
    target_layer: str
    category: str
    priority: str
    metrics: list[str]
    passed: bool
    failures: list[str] = field(default_factory=list)
    metric_results: list[GoldenMetricResult] = field(default_factory=list)
    actual: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoldenRunSummary:
    results: list[GoldenCaseResult]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def failed_count(self) -> int:
        return len(self.results) - self.passed_count

    @property
    def category_scores(self) -> dict[str, dict[str, int | float]]:
        return self._scores_by(lambda result: result.category)

    @property
    def metric_scores(self) -> dict[str, dict[str, int | float]]:
        scores: dict[str, dict[str, int | float]] = {}
        for result in self.results:
            for metric_result in result.metric_results:
                bucket = scores.setdefault(
                    metric_result.metric,
                    {"passed": 0, "total": 0, "pass_rate": 0.0},
                )
                bucket["total"] = int(bucket["total"]) + 1
                if metric_result.passed:
                    bucket["passed"] = int(bucket["passed"]) + 1
        for bucket in scores.values():
            total = int(bucket["total"])
            bucket["pass_rate"] = round(int(bucket["passed"]) / total, 4) if total else 0.0
        return scores

    @property
    def high_priority_failures(self) -> list[GoldenCaseResult]:
        return [
            result
            for result in self.results
            if not result.passed and result.priority == "high"
        ]

    def report(self) -> str:
        lines = [
            f"Golden dataset: {self.passed_count}/{len(self.results)} passed "
            f"({self._pass_rate(self.passed_count, len(self.results)):.1%})"
        ]
        lines.append("Category scores:")
        for category, score in sorted(self.category_scores.items()):
            lines.append(
                f"  - {category}: {score['passed']}/{score['total']} "
                f"({float(score['pass_rate']):.1%})"
            )
        lines.append("Metric scores:")
        for metric, score in sorted(self.metric_scores.items()):
            lines.append(
                f"  - {metric}: {score['passed']}/{score['total']} "
                f"({float(score['pass_rate']):.1%})"
            )
        if self.high_priority_failures:
            lines.append("High-priority failures:")
            for result in self.high_priority_failures:
                lines.append(f"  - {result.case_id}")
        for result in self.results:
            if result.passed:
                continue
            lines.append(
                f"\nFAIL {result.case_id} [{result.target_layer}] "
                f"category={result.category} priority={result.priority}"
            )
            failed_metrics = [
                metric_result.metric
                for metric_result in result.metric_results
                if not metric_result.passed
            ]
            if failed_metrics:
                lines.append("  failed_metrics: " + ", ".join(failed_metrics))
            for failure in result.failures:
                lines.append(f"  - {failure}")
            message = str(result.actual.get("message") or "")
            if message:
                lines.append(f"  message: {message[:220]}")
            if result.actual.get("source_guideline_ids") is not None:
                lines.append(
                    "  guideline_ids: "
                    + ", ".join(result.actual.get("source_guideline_ids") or [])
                )
            if result.actual.get("care_context") is not None:
                lines.append(
                    "  care_context: "
                    + json.dumps(result.actual["care_context"], sort_keys=True)[:500]
                )
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "passed": self.passed,
                "passed_count": self.passed_count,
                "failed_count": self.failed_count,
                "total_count": len(self.results),
                "pass_rate": self._pass_rate(self.passed_count, len(self.results)),
                "high_priority_failures": [
                    result.case_id for result in self.high_priority_failures
                ],
            },
            "category_scores": self.category_scores,
            "metric_scores": self.metric_scores,
            "case_results": [
                {
                    "case_id": result.case_id,
                    "target_layer": result.target_layer,
                    "category": result.category,
                    "priority": result.priority,
                    "passed": result.passed,
                    "failures": result.failures,
                    "metrics": [
                        {
                            "metric": metric_result.metric,
                            "passed": metric_result.passed,
                            "failures": metric_result.failures,
                        }
                        for metric_result in result.metric_results
                    ],
                    "actual": result.actual,
                }
                for result in self.results
            ],
        }

    def _scores_by(self, key_fn) -> dict[str, dict[str, int | float]]:
        scores: dict[str, dict[str, int | float]] = {}
        for result in self.results:
            key = key_fn(result)
            bucket = scores.setdefault(key, {"passed": 0, "total": 0, "pass_rate": 0.0})
            bucket["total"] = int(bucket["total"]) + 1
            if result.passed:
                bucket["passed"] = int(bucket["passed"]) + 1
        for bucket in scores.values():
            total = int(bucket["total"])
            bucket["pass_rate"] = self._pass_rate(int(bucket["passed"]), total)
        return scores

    def _pass_rate(self, passed: int, total: int) -> float:
        return round(passed / total, 4) if total else 0.0


def load_cases(path: str | Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_golden_cases(
    *,
    cases_path: str | Path = DEFAULT_CASES_PATH,
    layer: str = "all",
) -> GoldenRunSummary:
    cases = load_cases(cases_path)
    selected = [
        case
        for case in cases
        if layer == "all" or case.get("target_layer") == layer
    ]
    return GoldenRunSummary(results=[run_case(case) for case in selected])


def run_case(case: dict[str, Any]) -> GoldenCaseResult:
    target_layer = str(case["target_layer"])
    category = str(case.get("category") or "uncategorized")
    priority = str(case.get("priority") or "medium")
    metrics = list(case.get("metrics") or _default_metrics(case.get("expected", {})))
    if target_layer == "service":
        actual = _run_service_case(case)
    elif target_layer == "api":
        actual = _run_api_case(case)
    else:
        return GoldenCaseResult(
            case_id=str(case.get("case_id", "unknown")),
            target_layer=target_layer,
            category=category,
            priority=priority,
            metrics=metrics,
            passed=False,
            failures=[f"Unsupported target_layer: {target_layer}"],
            metric_results=[
                GoldenMetricResult(
                    metric="api_contract",
                    passed=False,
                    failures=[f"Unsupported target_layer: {target_layer}"],
                )
            ],
        )
    metric_failures = _check_expected_by_metric(
        actual=actual,
        expected=case.get("expected", {}),
        metrics=metrics,
    )
    metric_results = [
        GoldenMetricResult(
            metric=metric,
            passed=not failures,
            failures=failures,
        )
        for metric, failures in metric_failures.items()
    ]
    failures = [
        failure
        for metric_result in metric_results
        for failure in metric_result.failures
    ]
    return GoldenCaseResult(
        case_id=str(case["case_id"]),
        target_layer=target_layer,
        category=category,
        priority=priority,
        metrics=metrics,
        passed=not failures,
        failures=failures,
        metric_results=metric_results,
        actual=actual,
    )


def _run_service_case(case: dict[str, Any]) -> dict[str, Any]:
    pet = _pet_from_case(case)
    result = LogProcessingService().process_log(
        workflow_id=f"wf_golden_{case['case_id']}",
        dog_id=pet.pet_id,
        raw_text=str(case["raw_text"]),
        timestamp=str(case["timestamp"]),
        dog_profile=pet.dog_profile,
        behavioral_baseline=pet.behavioral_baseline,
        health_baseline=pet.health_baseline,
        species=pet.dog_profile.species,
    )
    payload = result.response.model_dump(mode="json")
    payload["care_context"] = None
    return payload


def _run_api_case(case: dict[str, Any]) -> dict[str, Any]:
    repository = InMemoryPetRepository()
    client = TestClient(create_app(repository=repository))
    pet = _pet_from_case(case)
    client.post(
        "/v1/users",
        json={
            "user_id": pet.user_id,
            "display_name": "Golden User",
            "email": "golden@example.com",
        },
    )
    client.post(
        f"/v1/users/{pet.user_id}/pets",
        json={
            "pet_id": pet.pet_id,
            "dog_profile": pet.dog_profile.model_dump(mode="json"),
            "behavioral_baseline": pet.behavioral_baseline.model_dump(mode="json"),
            "health_baseline": pet.health_baseline.model_dump(mode="json"),
        },
    )
    message_response = client.post(
        f"/v1/users/{pet.user_id}/pets/{pet.pet_id}/messages",
        json={
            "raw_text": case["raw_text"],
            "timestamp": case["timestamp"],
            "workflow_id": f"wf_golden_{case['case_id']}",
        },
    )
    payload = message_response.json()
    payload["_message_status_code"] = message_response.status_code
    if case.get("expected", {}).get("care_context_expected") is not None:
        care_response = client.post(
            f"/v1/users/{pet.user_id}/pets/{pet.pet_id}/care-context",
            json={"raw_text": case["raw_text"]},
        )
        payload["care_context"] = care_response.json()
        payload["_care_context_status_code"] = care_response.status_code
    else:
        payload["care_context"] = None
    return payload


def _pet_from_case(case: dict[str, Any]) -> PetRecord:
    profile = case["pet_profile"]
    pet_id = str(profile.get("id") or profile.get("pet_id") or "pet_golden")
    user_id = str(profile.get("user_id") or "user_golden")
    dog_profile = DogProfile.model_validate(
        {
            "id": pet_id,
            "name": profile.get("name", "Mochi"),
            "species": profile.get("species", "dog"),
            "breed": profile.get("breed"),
            "care_notes": profile.get("care_notes", []),
        }
    )
    behavioral_baseline = BehavioralBaseline.model_validate(
        profile.get("behavioral_baseline")
        or {
            "general_temperament": "food_motivated",
            "social_profile": {
                "large_dog_reaction": "neutral",
                "small_dog_reaction": "friendly",
                "prey_drive_level": 4,
            },
            "resource_guarding_profile": {
                "toy_guarding": "mild",
                "known_guarded_resources": ["high_value_chews"],
            },
        }
    )
    health_baseline = HealthBaseline.model_validate(
        profile.get("health_baseline")
        or {
            "normal_appetite": "high",
            "normal_stool_quality": "firm",
            "normal_activity_level": "medium",
            "known_medical_notes": profile.get("known_medical_notes", []),
        }
    )
    return PetRecord(
        pet_id=pet_id,
        user_id=user_id,
        dog_profile=dog_profile,
        behavioral_baseline=behavioral_baseline,
        health_baseline=health_baseline,
    )


def _default_metrics(expected: dict[str, Any]) -> list[str]:
    metrics = ["risk_classification"]
    if expected.get("must_include_guideline_ids"):
        metrics.append("guideline_grounding")
    if expected.get("must_include_text"):
        metrics.append("response_content")
    if expected.get("must_not_include_text"):
        metrics.append("safety_forbidden_text")
    if expected.get("care_context_expected") is not None:
        metrics.append("care_context_retrieval")
    return metrics


def _check_expected_by_metric(
    *,
    actual: dict[str, Any],
    expected: dict[str, Any],
    metrics: list[str],
) -> dict[str, list[str]]:
    metric_failures: dict[str, list[str]] = {metric: [] for metric in metrics}
    if "risk_classification" in metric_failures:
        _check_equal(
            metric_failures["risk_classification"],
            actual=actual,
            expected=expected,
            field="status",
        )
        _check_equal(
            metric_failures["risk_classification"],
            actual=actual,
            expected=expected,
            field="risk_band",
        )
    guideline_ids = set(actual.get("source_guideline_ids") or [])
    if "guideline_grounding" in metric_failures:
        for guideline_id in expected.get("must_include_guideline_ids", []):
            if guideline_id not in guideline_ids:
                metric_failures["guideline_grounding"].append(
                    f"Expected guideline id {guideline_id!r} not found."
                )
    message = str(actual.get("message") or "")
    message_lower = message.lower()
    if "response_content" in metric_failures:
        for text in expected.get("must_include_text", []):
            if str(text).lower() not in message_lower:
                metric_failures["response_content"].append(
                    f"Expected message to include {text!r}."
                )
    if "safety_forbidden_text" in metric_failures:
        for text in expected.get("must_not_include_text", []):
            if str(text).lower() in message_lower:
                metric_failures["safety_forbidden_text"].append(
                    f"Message included forbidden text {text!r}."
                )
    care_context = actual.get("care_context")
    if "care_context_retrieval" in metric_failures:
        if expected.get("care_context_expected") is True:
            if not care_context:
                metric_failures["care_context_retrieval"].append(
                    "Expected care_context payload."
                )
            else:
                _check_care_context(
                    failures=metric_failures["care_context_retrieval"],
                    care_context=care_context,
                    expected=expected,
                )
        if expected.get("care_context_expected") is False and care_context:
            if care_context.get("professional_references") or care_context.get("related_cases"):
                metric_failures["care_context_retrieval"].append(
                    "Expected empty care_context payload."
                )
    if "api_contract" in metric_failures:
        if actual.get("_message_status_code") not in {None, 200}:
            metric_failures["api_contract"].append(
                f"Expected message API status 200, got {actual.get('_message_status_code')}."
            )
        if actual.get("_care_context_status_code") not in {None, 200}:
            metric_failures["api_contract"].append(
                "Expected care-context API status 200, got "
                f"{actual.get('_care_context_status_code')}."
            )
        for forbidden_field in ["agent_outputs", "proposed_update", "safety_review"]:
            if forbidden_field in actual:
                metric_failures["api_contract"].append(
                    f"API response leaked internal field {forbidden_field!r}."
                )
    return metric_failures


def _check_equal(
    failures: list[str],
    *,
    actual: dict[str, Any],
    expected: dict[str, Any],
    field: str,
) -> None:
    if field not in expected:
        return
    if actual.get(field) != expected[field]:
        failures.append(
            f"Expected {field}={expected[field]!r}, got {actual.get(field)!r}."
        )


def _check_care_context(
    *,
    failures: list[str],
    care_context: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    context_summary = str(care_context.get("context_summary") or "")
    if "diagnosis" not in str(care_context.get("non_diagnostic_notice") or "").lower():
        failures.append("Expected care context non-diagnostic notice.")
    for domain in expected.get("expected_reference_domains", []):
        domains = {
            reference.get("domain")
            for reference in care_context.get("professional_references", [])
        }
        if domain not in domains:
            failures.append(f"Expected professional reference domain {domain!r}.")
    related_topics = {
        topic
        for case in care_context.get("related_cases", [])
        for topic in case.get("possible_discussion_topics", [])
    }
    for topic in expected.get("expected_related_case_topics", []):
        if topic not in related_topics:
            failures.append(f"Expected related case topic {topic!r}.")
    for text in expected.get("care_context_must_include_text", []):
        if str(text).lower() not in context_summary.lower():
            failures.append(f"Expected care context summary to include {text!r}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PawCare golden dataset checks.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--layer", choices=["service", "api", "all"], default="all")
    parser.add_argument("--report-json", default=None)
    args = parser.parse_args()
    summary = run_golden_cases(cases_path=args.cases, layer=args.layer)
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(summary.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(summary.report())
    raise SystemExit(0 if summary.passed else 1)


if __name__ == "__main__":
    main()
