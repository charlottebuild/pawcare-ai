from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pawcare.evaluation.cost_benchmark import run_cost_benchmark


def test_cost_benchmark_reports_cache_savings() -> None:
    report = run_cost_benchmark()

    summary = report["summary"]
    cache_metrics = report["cache_metrics"]

    assert summary["query_count"] == 12
    assert summary["scenario_count"] == 4
    assert cache_metrics["hits"] > 0
    assert cache_metrics["misses"] > 0
    assert summary["cache_hit_rate"] > 0
    assert summary["estimated_context_tokens_saved"] > 0
    assert summary["retrieval_calls_avoided"] > 0
    assert summary["summarizer_calls_avoided"] > 0
    assert "not provider billing" in summary["estimated_token_note"]
    assert report["latency_summary"]["total_ms"] >= 0


def test_cost_benchmark_writes_json_report(tmp_path: Path) -> None:
    report_path = tmp_path / "pawcare_cost_benchmark.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pawcare.evaluation.cost_benchmark",
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
    assert "PawCare semantic cache cost benchmark" in result.stdout
    assert report["summary"]["estimated_context_tokens_saved"] > 0
    assert report["cache_metrics"]["hit_rate"] > 0
    assert "case_results" in report
