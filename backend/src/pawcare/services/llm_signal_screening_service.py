from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from pawcare.skills.symptom_understanding import TRIAGE_INTENT_TERMS, contains_any


@dataclass(frozen=True)
class LLMSignalScreeningResult:
    possible_domains: list[str]
    matched_phrases: list[str]
    suggested_canonical_terms: list[str]
    suggested_guideline_ids: list[str]
    confidence: float
    reasoning_summary: str

    def is_empty(self) -> bool:
        return not (
            self.possible_domains
            or self.matched_phrases
            or self.suggested_canonical_terms
            or self.suggested_guideline_ids
        )

    def as_payload(self) -> dict[str, object]:
        return asdict(self)


class LLMSignalScreeningService(Protocol):
    def screen(
        self,
        *,
        raw_text: str,
        pet_context: dict[str, object],
        target: str,
    ) -> LLMSignalScreeningResult:
        """Return conservative structured screening hints for a target agent."""


class DeterministicLLMSignalScreeningService:
    """No-op fallback used when optional LLM screening is disabled."""

    def screen(
        self,
        *,
        raw_text: str,
        pet_context: dict[str, object],
        target: str,
    ) -> LLMSignalScreeningResult:
        return empty_llm_signal_screening_result()


class OpenAILLMSignalScreeningService:
    def __init__(
        self,
        *,
        fallback: LLMSignalScreeningService | None = None,
        client: Any | None = None,
        model: str | None = None,
    ) -> None:
        self.fallback = fallback or DeterministicLLMSignalScreeningService()
        self.client = client
        self.model = model or os.getenv("PAWCARE_SCREENING_MODEL", "gpt-5.2")

    def screen(
        self,
        *,
        raw_text: str,
        pet_context: dict[str, object],
        target: str,
    ) -> LLMSignalScreeningResult:
        if not should_llm_screen(raw_text):
            return empty_llm_signal_screening_result()
        try:
            client = self.client or self._openai_client()
            response = client.responses.create(
                model=self.model,
                input=self._prompt(
                    raw_text=raw_text,
                    pet_context=pet_context,
                    target=target,
                ),
            )
            text = str(getattr(response, "output_text", "")).strip()
            return self._parse_result(text)
        except Exception:
            return self.fallback.screen(
                raw_text=raw_text,
                pet_context=pet_context,
                target=target,
            )

    def _openai_client(self) -> Any:
        from openai import OpenAI

        return OpenAI()

    def _prompt(
        self,
        *,
        raw_text: str,
        pet_context: dict[str, object],
        target: str,
    ) -> str:
        return (
            "You are a conservative pet-care signal screening helper. "
            "Return only JSON with keys: possible_domains, matched_phrases, "
            "suggested_canonical_terms, suggested_guideline_ids, confidence, reasoning_summary. "
            "Do not diagnose. Do not provide medication dosage or medication instructions. "
            "Do not say the pet is fine or that there is nothing to worry about. "
            "Only suggest signals that should be reviewed by the PawCare agent.\n\n"
            f"Target agent: {target}\n"
            f"Pet context: {pet_context}\n"
            f"User text: {raw_text}\n"
        )

    def _parse_result(self, text: str) -> LLMSignalScreeningResult:
        payload = json.loads(text)
        if self._unsafe_text(str(payload.get("reasoning_summary") or "")):
            return empty_llm_signal_screening_result()
        result = LLMSignalScreeningResult(
            possible_domains=self._string_list(payload.get("possible_domains")),
            matched_phrases=self._string_list(payload.get("matched_phrases")),
            suggested_canonical_terms=self._string_list(
                payload.get("suggested_canonical_terms")
            ),
            suggested_guideline_ids=self._safe_guideline_ids(
                payload.get("suggested_guideline_ids")
            ),
            confidence=self._confidence(payload.get("confidence")),
            reasoning_summary=self._safe_reasoning(payload.get("reasoning_summary")),
        )
        if self._unsafe_text(" ".join([result.reasoning_summary, *result.suggested_guideline_ids])):
            return empty_llm_signal_screening_result()
        return result

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:8]

    def _safe_guideline_ids(self, value: object) -> list[str]:
        return [
            item
            for item in self._string_list(value)
            if item.startswith("GL_") and "MEDICATION_DOSAGE" not in item
        ][:6]

    def _confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, confidence))

    def _safe_reasoning(self, value: object) -> str:
        text = str(value or "").strip()
        return "" if self._unsafe_text(text) else text[:300]

    def _unsafe_text(self, text: str) -> bool:
        lowered = text.lower()
        blocked_terms = [
            "has gastroenteritis",
            "has salivary mucocele",
            "has uti",
            "has urinary blockage",
            "give ",
            "dosage",
            "dose",
            "nothing to worry",
            "definitely normal",
            "it is fine",
        ]
        return any(term in lowered for term in blocked_terms)


def empty_llm_signal_screening_result() -> LLMSignalScreeningResult:
    return LLMSignalScreeningResult(
        possible_domains=[],
        matched_phrases=[],
        suggested_canonical_terms=[],
        suggested_guideline_ids=[],
        confidence=0.0,
        reasoning_summary="",
    )


def should_llm_screen(raw_text: str) -> bool:
    lowered = raw_text.lower()
    care_terms = [
        "what can i do",
        "what should i do",
        "care question",
        "is this normal",
        "normal?",
        "strange",
        "odd",
        "weird",
        "problem",
        "worry",
        "worried",
        "help",
        "stress",
        "anxious",
        "scared",
        "aggressive",
        "guarding",
        "pain",
        "hurt",
        "sick",
        "不正常",
        "奇怪",
        "担心",
        "怎么办",
        "要紧吗",
        "疼",
        "焦虑",
        "害怕",
        "护食",
    ]
    return contains_any(raw_text, TRIAGE_INTENT_TERMS) or any(
        term in lowered for term in care_terms
    )


def build_llm_signal_screening_service() -> LLMSignalScreeningService:
    if (
        os.getenv("PAWCARE_ENABLE_LLM_SCREENING", "").lower() == "true"
        and os.getenv("OPENAI_API_KEY")
    ):
        return OpenAILLMSignalScreeningService()
    return DeterministicLLMSignalScreeningService()
