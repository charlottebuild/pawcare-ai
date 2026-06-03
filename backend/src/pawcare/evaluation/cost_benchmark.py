from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from pawcare.api import create_app
from pawcare.services import InMemoryPetRepository, SemanticCareContextCache


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    species: str
    breed: str | None
    queries: list[str]


DEFAULT_SCENARIOS = [
    BenchmarkScenario(
        scenario_id="gi_bloody_stool",
        species="dog",
        breed="Poodle",
        queries=[
            "Mochi poo blood this morning.",
            "Mochi had bloody stool this morning.",
            "Mochi has blood in stool, should I worry?",
        ],
    ),
    BenchmarkScenario(
        scenario_id="cat_urinary",
        species="cat",
        breed="Domestic Shorthair",
        queries=[
            "NiaoNiao couldnt pee today.",
            "NiaoNiao didn't pee all day. Is there any problem?",
            "猫猫一天没上厕所",
        ],
    ),
    BenchmarkScenario(
        scenario_id="oral_salivary",
        species="dog",
        breed="Toy Poodle",
        queries=[
            "Mochi pulls his head back when eating and drools. Could it be salivary mucocele?",
            "Mochi has a small lump under the tongue and is drooling.",
            "Mochi has an oral lump and head withdrawal while eating.",
        ],
    ),
    BenchmarkScenario(
        scenario_id="mobility_non_weight_bearing",
        species="dog",
        breed="Poodle",
        queries=[
            "Mochi's leg won't touch floor after surgery.",
            "Mochi is not weight bearing on one leg.",
            "Mochi is limping and won't put foot down.",
        ],
    ),
]


def run_cost_benchmark(
    *,
    scenarios: list[BenchmarkScenario] | None = None,
) -> dict[str, Any]:
    selected = scenarios or DEFAULT_SCENARIOS
    cache = SemanticCareContextCache()
    client = TestClient(create_app(repository=InMemoryPetRepository(), care_context_cache=cache))
    _seed_benchmark_pets(client=client, scenarios=selected)

    start = time.perf_counter()
    results = [
        _run_query(client=client, scenario=scenario, query=query)
        for scenario in selected
        for query in scenario.queries
    ]
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    cache_metrics = cache.metrics()
    misses = int(cache_metrics["misses"])
    hits = int(cache_metrics["hits"])
    miss_token_estimate = _sum_estimated_context_tokens(
        result for result in results if result["cache_status"] == "miss"
    )
    hit_token_estimate = _sum_estimated_context_tokens(
        result for result in results if result["cache_status"] == "hit"
    )
    average_miss_tokens = round(miss_token_estimate / misses, 2) if misses else 0.0
    estimated_context_tokens_saved = int(round(average_miss_tokens * hits))

    return {
        "summary": {
            "scenario_count": len(selected),
            "query_count": len(results),
            "cache_hit_rate": cache_metrics["hit_rate"],
            "estimated_context_tokens_saved": estimated_context_tokens_saved,
            "retrieval_calls_avoided": hits * 2,
            "summarizer_calls_avoided": hits,
            "estimated_token_note": (
                "Deterministic estimate for retrieval/context payload size, not provider billing."
            ),
        },
        "cache_metrics": cache_metrics,
        "latency_summary": {
            "total_ms": duration_ms,
            "avg_ms": round(duration_ms / len(results), 3) if results else 0.0,
        },
        "case_results": results,
        "estimated_payload_tokens": {
            "miss_payload_tokens": miss_token_estimate,
            "hit_payload_tokens_returned": hit_token_estimate,
            "average_miss_tokens": average_miss_tokens,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PawCare semantic cache cost benchmark."
    )
    parser.add_argument("--report-json", default=None)
    args = parser.parse_args()
    report = run_cost_benchmark()
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(_format_report(report))


def _seed_benchmark_pets(
    *,
    client: TestClient,
    scenarios: list[BenchmarkScenario],
) -> None:
    response = client.post("/v1/users", json={"user_id": "user_benchmark"})
    response.raise_for_status()
    seen: set[str] = set()
    for scenario in scenarios:
        pet_id = _pet_id(scenario)
        if pet_id in seen:
            continue
        seen.add(pet_id)
        response = client.post(
            "/v1/users/user_benchmark/pets",
            json={
                "pet_id": pet_id,
                "dog_profile": {
                    "id": pet_id,
                    "name": scenario.scenario_id,
                    "species": scenario.species,
                    "breed": scenario.breed,
                },
                "behavioral_baseline": {},
                "health_baseline": {
                    "known_medical_notes": [],
                },
            },
        )
        response.raise_for_status()


def _run_query(
    *,
    client: TestClient,
    scenario: BenchmarkScenario,
    query: str,
) -> dict[str, Any]:
    response = client.post(
        f"/v1/users/user_benchmark/pets/{_pet_id(scenario)}/care-context",
        json={"raw_text": query},
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "scenario_id": scenario.scenario_id,
        "query": query,
        "cache_status": payload["cache_status"],
        "professional_reference_count": len(payload["professional_references"]),
        "related_case_count": len(payload["related_cases"]),
        "estimated_context_tokens": _estimate_context_tokens(payload),
    }


def _pet_id(scenario: BenchmarkScenario) -> str:
    return f"{scenario.species}_{scenario.scenario_id}"


def _estimate_context_tokens(payload: dict[str, Any]) -> int:
    text = json.dumps(
        {
            "professional_references": payload.get("professional_references", []),
            "related_cases": payload.get("related_cases", []),
            "context_summary": payload.get("context_summary", ""),
        },
        sort_keys=True,
    )
    return max(1, round(len(text) / 4))


def _sum_estimated_context_tokens(results) -> int:
    return sum(int(result["estimated_context_tokens"]) for result in results)


def _format_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    cache = report["cache_metrics"]
    latency = report["latency_summary"]
    return "\n".join(
        [
            "PawCare semantic cache cost benchmark",
            f"Queries: {summary['query_count']} across {summary['scenario_count']} scenarios",
            (
                "Cache: "
                f"hits={cache['hits']} misses={cache['misses']} "
                f"hit_rate={float(summary['cache_hit_rate']):.1%}"
            ),
            (
                "Estimated savings: "
                f"context_tokens={summary['estimated_context_tokens_saved']} "
                f"retrieval_calls={summary['retrieval_calls_avoided']} "
                f"summarizer_calls={summary['summarizer_calls_avoided']}"
            ),
            f"Latency: total={latency['total_ms']}ms avg={latency['avg_ms']}ms",
            str(summary["estimated_token_note"]),
        ]
    )


if __name__ == "__main__":
    main()
