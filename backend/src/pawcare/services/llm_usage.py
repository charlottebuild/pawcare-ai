from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMUsageRecord:
    """Optional LLM usage telemetry captured from provider responses."""

    provider: str
    model: str
    source: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class LLMUsageCollector:
    records: list[LLMUsageRecord] = field(default_factory=list)

    def add(self, record: LLMUsageRecord | None) -> None:
        if record is not None:
            self.records.append(record)

    def summary(self) -> dict[str, object]:
        return summarize_usage(self.records)


def summarize_usage(records: list[LLMUsageRecord]) -> dict[str, object]:
    total_prompt_tokens = sum(record.prompt_tokens for record in records)
    total_completion_tokens = sum(record.completion_tokens for record in records)
    total_tokens = sum(record.total_tokens for record in records)
    estimated_costs = [
        record.estimated_cost_usd
        for record in records
        if record.estimated_cost_usd is not None
    ]
    return {
        "available": bool(records),
        "call_count": len(records),
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": (
            round(sum(estimated_costs), 8) if estimated_costs else None
        ),
        "records": [record.as_dict() for record in records],
        "before_after_token_comparison": None,
    }


def extract_openai_usage_record(
    response: Any,
    *,
    model: str,
    source: str,
) -> LLMUsageRecord | None:
    """Extract token usage from OpenAI-style responses when it is present."""

    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    prompt_tokens = _int_field(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _int_field(usage, "completion_tokens", "output_tokens")
    total_tokens = _int_field(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    if total_tokens == 0:
        return None
    return LLMUsageRecord(
        provider="openai",
        model=model,
        source=source,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=_estimate_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def _int_field(value: Any, *names: str) -> int:
    for name in names:
        if isinstance(value, dict):
            candidate = value.get(name)
        else:
            candidate = getattr(value, name, None)
        try:
            parsed = int(candidate)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return 0


def _estimate_cost(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float | None:
    # Conservative local estimator for tests and reports. Unknown models are
    # marked unavailable instead of inventing pricing.
    pricing_per_1m = {
        "test-model": (1.0, 2.0),
    }
    pricing = pricing_per_1m.get(model)
    if pricing is None:
        return None
    input_rate, output_rate = pricing
    return round(
        (prompt_tokens / 1_000_000 * input_rate)
        + (completion_tokens / 1_000_000 * output_rate),
        8,
    )
