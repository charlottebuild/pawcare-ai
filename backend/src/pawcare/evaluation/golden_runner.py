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
class GoldenCaseResult:
    case_id: str
    target_layer: str
    passed: bool
    failures: list[str] = field(default_factory=list)
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

    def report(self) -> str:
        lines = [
            f"Golden dataset: {self.passed_count}/{len(self.results)} passed"
        ]
        for result in self.results:
            if result.passed:
                continue
            lines.append(f"\nFAIL {result.case_id} [{result.target_layer}]")
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
    if target_layer == "service":
        actual = _run_service_case(case)
    elif target_layer == "api":
        actual = _run_api_case(case)
    else:
        return GoldenCaseResult(
            case_id=str(case.get("case_id", "unknown")),
            target_layer=target_layer,
            passed=False,
            failures=[f"Unsupported target_layer: {target_layer}"],
        )
    failures = _check_expected(actual=actual, expected=case.get("expected", {}))
    return GoldenCaseResult(
        case_id=str(case["case_id"]),
        target_layer=target_layer,
        passed=not failures,
        failures=failures,
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
    if case.get("expected", {}).get("care_context_expected") is not None:
        care_response = client.post(
            f"/v1/users/{pet.user_id}/pets/{pet.pet_id}/care-context",
            json={"raw_text": case["raw_text"]},
        )
        payload["care_context"] = care_response.json()
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


def _check_expected(*, actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    _check_equal(failures, actual=actual, expected=expected, field="status")
    _check_equal(failures, actual=actual, expected=expected, field="risk_band")
    guideline_ids = set(actual.get("source_guideline_ids") or [])
    for guideline_id in expected.get("must_include_guideline_ids", []):
        if guideline_id not in guideline_ids:
            failures.append(f"Expected guideline id {guideline_id!r} not found.")
    message = str(actual.get("message") or "")
    message_lower = message.lower()
    for text in expected.get("must_include_text", []):
        if str(text).lower() not in message_lower:
            failures.append(f"Expected message to include {text!r}.")
    for text in expected.get("must_not_include_text", []):
        if str(text).lower() in message_lower:
            failures.append(f"Message included forbidden text {text!r}.")
    care_context = actual.get("care_context")
    if expected.get("care_context_expected") is True:
        if not care_context:
            failures.append("Expected care_context payload.")
        else:
            _check_care_context(
                failures=failures,
                care_context=care_context,
                expected=expected,
            )
    if expected.get("care_context_expected") is False and care_context:
        if care_context.get("professional_references") or care_context.get("related_cases"):
            failures.append("Expected empty care_context payload.")
    return failures


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
    args = parser.parse_args()
    summary = run_golden_cases(cases_path=args.cases, layer=args.layer)
    print(summary.report())
    raise SystemExit(0 if summary.passed else 1)


if __name__ == "__main__":
    main()
