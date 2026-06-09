from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi.testclient import TestClient

from pawcare.api import create_app
from pawcare.services import InMemoryPetRepository, SemanticCareContextCache


FORBIDDEN_REPORT_FIELDS = {"agent_outputs", "proposed_update", "safety_review"}


@dataclass(frozen=True)
class RouteCallResult:
    scenario_id: str
    route_name: str
    method_path: str
    duration_ms: float
    success: bool
    status_code: int | None = None
    event_count: int | None = None
    final_event_seen: bool | None = None
    cache_status: str | None = None
    response_size_bytes: int = 0
    estimated_context_tokens: int | None = None
    failure: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "route_name": self.route_name,
            "method_path": self.method_path,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "status_code": self.status_code,
            "event_count": self.event_count,
            "final_event_seen": self.final_event_seen,
            "cache_status": self.cache_status,
            "response_size_bytes": self.response_size_bytes,
            "estimated_context_tokens": self.estimated_context_tokens,
            "failure": self.failure,
        }


def run_route_benchmark() -> dict[str, Any]:
    cache = SemanticCareContextCache()
    client = TestClient(create_app(repository=InMemoryPetRepository(), care_context_cache=cache))
    runner = _RouteBenchmarkRunner(client=client)
    started = time.perf_counter()
    results = runner.run()
    total_ms = round((time.perf_counter() - started) * 1000, 3)
    return _build_report(results=results, total_ms=total_ms, cache_metrics=cache.metrics())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PawCare route benchmark.")
    parser.add_argument("--report-json", default=None)
    args = parser.parse_args()
    report = run_route_benchmark()
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(_format_report(report))


class _RouteBenchmarkRunner:
    def __init__(self, *, client: TestClient) -> None:
        self.client = client
        self.user_id = "user_route_benchmark"
        self.pet_id = "dog_mochi"
        self.cat_id = "cat_niaoniao"

    def run(self) -> list[RouteCallResult]:
        calls: list[tuple[str, str, str, Callable[[], RouteCallResult]]] = [
            ("workspace_setup", "create_user", "POST /v1/users", self._create_user),
            ("workspace_setup", "create_pet_dog", "POST /v1/users/{user_id}/pets", self._create_dog),
            ("workspace_setup", "create_pet_cat", "POST /v1/users/{user_id}/pets", self._create_cat),
            ("workspace_setup", "list_pets", "GET /v1/users/{user_id}/pets", self._list_pets),
            ("normal_update", "message_sync", "POST /v1/users/{user_id}/pets/{pet_id}/messages", self._message_sync),
            ("triage_update", "message_stream", "POST /v1/users/{user_id}/pets/{pet_id}/messages/stream", self._message_stream),
            ("care_context_miss", "care_context", "POST /v1/users/{user_id}/pets/{pet_id}/care-context", self._care_context_miss),
            ("care_context_hit", "care_context", "POST /v1/users/{user_id}/pets/{pet_id}/care-context", self._care_context_hit),
            ("stored_history", "list_observations", "GET /v1/users/{user_id}/pets/{pet_id}/observations", self._list_observations),
        ]
        return [self._capture(scenario_id, route_name, method_path, call) for scenario_id, route_name, method_path, call in calls]

    def _capture(
        self,
        scenario_id: str,
        route_name: str,
        method_path: str,
        call: Callable[[], RouteCallResult],
    ) -> RouteCallResult:
        started = time.perf_counter()
        try:
            result = call()
        except Exception as exc:  # pragma: no cover - exercised through CLI failures
            return RouteCallResult(
                scenario_id=scenario_id,
                route_name=route_name,
                method_path=method_path,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                success=False,
                failure=str(exc),
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        return RouteCallResult(
            **{
                **result.as_dict(),
                "duration_ms": duration_ms,
            }
        )

    def _create_user(self) -> RouteCallResult:
        response = self.client.post(
            "/v1/users",
            json={"user_id": self.user_id, "display_name": "Route Benchmark"},
        )
        return _http_result(
            scenario_id="workspace_setup",
            route_name="create_user",
            method_path="POST /v1/users",
            response=response,
        )

    def _create_dog(self) -> RouteCallResult:
        response = self.client.post(
            f"/v1/users/{self.user_id}/pets",
            json=_pet_payload(pet_id=self.pet_id, name="Mochi", species="dog", breed="Poodle"),
        )
        return _http_result(
            scenario_id="workspace_setup",
            route_name="create_pet_dog",
            method_path="POST /v1/users/{user_id}/pets",
            response=response,
        )

    def _create_cat(self) -> RouteCallResult:
        response = self.client.post(
            f"/v1/users/{self.user_id}/pets",
            json=_pet_payload(
                pet_id=self.cat_id,
                name="NiaoNiao",
                species="cat",
                breed="Domestic Shorthair",
            ),
        )
        return _http_result(
            scenario_id="workspace_setup",
            route_name="create_pet_cat",
            method_path="POST /v1/users/{user_id}/pets",
            response=response,
        )

    def _list_pets(self) -> RouteCallResult:
        response = self.client.get(f"/v1/users/{self.user_id}/pets")
        return _http_result(
            scenario_id="workspace_setup",
            route_name="list_pets",
            method_path="GET /v1/users/{user_id}/pets",
            response=response,
        )

    def _message_sync(self) -> RouteCallResult:
        response = self.client.post(
            f"/v1/users/{self.user_id}/pets/{self.pet_id}/messages",
            json={
                "raw_text": "Mochi ate breakfast normally today.",
                "timestamp": "2026-05-08T08:00:00-07:00",
            },
        )
        return _http_result(
            scenario_id="normal_update",
            route_name="message_sync",
            method_path="POST /v1/users/{user_id}/pets/{pet_id}/messages",
            response=response,
        )

    def _message_stream(self) -> RouteCallResult:
        with self.client.stream(
            "POST",
            f"/v1/users/{self.user_id}/pets/{self.cat_id}/messages/stream",
            json={
                "raw_text": "NiaoNiao is coughing and breathing hard today.",
                "timestamp": "2026-05-08T09:00:00-07:00",
            },
        ) as response:
            text = response.read().decode("utf-8")
        events = _sse_events(text)
        final_payloads = [data for event, data in events if event == "final"]
        response_size = len(text.encode("utf-8"))
        _assert_no_internal_fields(final_payloads[0] if final_payloads else {})
        return RouteCallResult(
            scenario_id="triage_update",
            route_name="message_stream",
            method_path="POST /v1/users/{user_id}/pets/{pet_id}/messages/stream",
            duration_ms=0.0,
            success=response.status_code == 200 and bool(final_payloads),
            status_code=response.status_code,
            event_count=len(events),
            final_event_seen=bool(final_payloads),
            response_size_bytes=response_size,
            estimated_context_tokens=_estimate_context_tokens(
                final_payloads[0].get("care_context", {}) if final_payloads else {}
            ),
            failure=None if response.status_code == 200 and final_payloads else "stream did not include final event",
        )

    def _care_context_miss(self) -> RouteCallResult:
        response = self.client.post(
            f"/v1/users/{self.user_id}/pets/{self.cat_id}/care-context",
            json={"raw_text": "NiaoNiao couldn't pee today.", "limit": 3},
        )
        return _http_result(
            scenario_id="care_context_miss",
            route_name="care_context",
            method_path="POST /v1/users/{user_id}/pets/{pet_id}/care-context",
            response=response,
            include_context_tokens=True,
        )

    def _care_context_hit(self) -> RouteCallResult:
        response = self.client.post(
            f"/v1/users/{self.user_id}/pets/{self.cat_id}/care-context",
            json={"raw_text": "NiaoNiao didn't pee all day. Is there any problem?", "limit": 3},
        )
        return _http_result(
            scenario_id="care_context_hit",
            route_name="care_context",
            method_path="POST /v1/users/{user_id}/pets/{pet_id}/care-context",
            response=response,
            include_context_tokens=True,
        )

    def _list_observations(self) -> RouteCallResult:
        response = self.client.get(
            f"/v1/users/{self.user_id}/pets/{self.cat_id}/observations"
        )
        return _http_result(
            scenario_id="stored_history",
            route_name="list_observations",
            method_path="GET /v1/users/{user_id}/pets/{pet_id}/observations",
            response=response,
        )


def _http_result(
    *,
    scenario_id: str,
    route_name: str,
    method_path: str,
    response,
    include_context_tokens: bool = False,
) -> RouteCallResult:
    payload = response.json() if response.content else {}
    _assert_no_internal_fields(payload)
    return RouteCallResult(
        scenario_id=scenario_id,
        route_name=route_name,
        method_path=method_path,
        duration_ms=0.0,
        success=200 <= response.status_code < 300,
        status_code=response.status_code,
        cache_status=payload.get("cache_status") if isinstance(payload, dict) else None,
        response_size_bytes=len(response.content or b""),
        estimated_context_tokens=(
            _estimate_context_tokens(payload) if include_context_tokens else 0
        ),
        failure=None if 200 <= response.status_code < 300 else str(payload)[:240],
    )


def _build_report(
    *,
    results: list[RouteCallResult],
    total_ms: float,
    cache_metrics: dict[str, int | float],
) -> dict[str, Any]:
    route_scores = _route_scores(results)
    estimated_tokens = [
        result.estimated_context_tokens
        for result in results
        if result.estimated_context_tokens is not None
    ]
    return {
        "summary": {
            "passed": all(result.success for result in results),
            "route_count": len(route_scores),
            "scenario_count": len({result.scenario_id for result in results}),
            "call_count": len(results),
            "total_ms": total_ms,
            "p50_ms": _percentile([result.duration_ms for result in results], 0.50),
            "p95_ms": _percentile([result.duration_ms for result in results], 0.95),
            "max_ms": round(max((result.duration_ms for result in results), default=0.0), 3),
        },
        "latency_summary": {
            "total_ms": total_ms,
            "avg_ms": round(total_ms / len(results), 3) if results else 0.0,
            "p50_ms": _percentile([result.duration_ms for result in results], 0.50),
            "p95_ms": _percentile([result.duration_ms for result in results], 0.95),
            "max_ms": round(max((result.duration_ms for result in results), default=0.0), 3),
            "note": "Local TestClient end-to-end route timing, not production latency.",
        },
        "route_scores": route_scores,
        "cost_summary": {
            "estimated_context_tokens": sum(int(token or 0) for token in estimated_tokens),
            "cache_hit_rate": cache_metrics["hit_rate"],
            "cache_hits": cache_metrics["hits"],
            "cache_misses": cache_metrics["misses"],
            "provider_billing_available": False,
            "note": "Token values are deterministic context-size estimates, not provider billing.",
        },
        "case_results": [result.as_dict() for result in results],
    }


def _route_scores(results: list[RouteCallResult]) -> dict[str, dict[str, int | float]]:
    scores: dict[str, dict[str, int | float]] = {}
    for result in results:
        bucket = scores.setdefault(
            result.route_name,
            {
                "call_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "max_ms": 0.0,
                "_durations": [],
            },
        )
        bucket["call_count"] = int(bucket["call_count"]) + 1
        if result.success:
            bucket["success_count"] = int(bucket["success_count"]) + 1
        else:
            bucket["failure_count"] = int(bucket["failure_count"]) + 1
        bucket["_durations"].append(result.duration_ms)  # type: ignore[union-attr]
    for bucket in scores.values():
        durations = list(bucket.pop("_durations"))  # type: ignore[arg-type]
        bucket["avg_ms"] = round(sum(durations) / len(durations), 3) if durations else 0.0
        bucket["p50_ms"] = _percentile(durations, 0.50)
        bucket["p95_ms"] = _percentile(durations, 0.95)
        bucket["max_ms"] = round(max(durations), 3) if durations else 0.0
    return scores


def _pet_payload(*, pet_id: str, name: str, species: str, breed: str) -> dict[str, object]:
    return {
        "pet_id": pet_id,
        "dog_profile": {
            "id": pet_id,
            "name": name,
            "species": species,
            "breed": breed,
            "care_notes": ["avatar:cat" if species == "cat" else "avatar:collie"],
        },
        "behavioral_baseline": {},
        "health_baseline": {
            "normal_appetite": "normal",
            "normal_stool_quality": "firm",
            "normal_activity_level": "medium",
            "known_medical_notes": [],
        },
    }


def _sse_events(text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in text.strip().split("\n\n"):
        event = "message"
        data: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            if line.startswith("data:"):
                data = json.loads(line.removeprefix("data:").strip())
        if data:
            events.append((event, data))
    return events


def _estimate_context_tokens(payload: dict[str, Any]) -> int:
    context_payload = {
        "professional_references": payload.get("professional_references", []),
        "related_cases": payload.get("related_cases", []),
        "context_summary": payload.get("context_summary", ""),
    }
    text = json.dumps(context_payload, sort_keys=True)
    return max(1, round(len(text) / 4)) if text else 0


def _assert_no_internal_fields(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    for field in FORBIDDEN_REPORT_FIELDS:
        if field in text:
            raise AssertionError(f"route benchmark payload exposed {field}")


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(
        len(sorted_values) - 1,
        max(0, round((len(sorted_values) - 1) * percentile)),
    )
    return round(sorted_values[index], 3)


def _format_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    cost = report["cost_summary"]
    lines = [
        "PawCare route benchmark",
        (
            f"Routes: {summary['route_count']} across {summary['scenario_count']} "
            f"scenarios ({summary['call_count']} calls)"
        ),
        (
            "Latency: "
            f"p50={summary['p50_ms']}ms p95={summary['p95_ms']}ms "
            f"max={summary['max_ms']}ms total={summary['total_ms']}ms"
        ),
        (
            "Care-context cache: "
            f"hits={cost['cache_hits']} misses={cost['cache_misses']} "
            f"hit_rate={float(cost['cache_hit_rate']):.1%}"
        ),
        (
            "Estimated context tokens: "
            f"{cost['estimated_context_tokens']} "
            "(deterministic estimate, not provider billing)"
        ),
    ]
    for route_name, score in sorted(report["route_scores"].items()):
        lines.append(
            f"- {route_name}: calls={score['call_count']} "
            f"success={score['success_count']} avg={score['avg_ms']}ms"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
