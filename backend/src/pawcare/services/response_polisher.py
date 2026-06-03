from __future__ import annotations

import os
from typing import Any, Protocol

from pawcare.agents.safety_agent import SafetyAgent
from pawcare.schemas.state import UserResponse
from pawcare.services.llm_usage import LLMUsageCollector, extract_openai_usage_record


class ResponsePolisher(Protocol):
    def polish(
        self,
        *,
        response: UserResponse,
        care_context: dict[str, object] | None = None,
    ) -> UserResponse:
        """Return a user response with optional safer wording polish."""


class DeterministicResponsePolisher:
    def polish(
        self,
        *,
        response: UserResponse,
        care_context: dict[str, object] | None = None,
    ) -> UserResponse:
        return response


class OpenAIResponsePolisher:
    def __init__(
        self,
        *,
        fallback: ResponsePolisher | None = None,
        client: Any | None = None,
        model: str | None = None,
        usage_collector: LLMUsageCollector | None = None,
    ) -> None:
        self.fallback = fallback or DeterministicResponsePolisher()
        self.client = client
        self.model = model or os.getenv("PAWCARE_RESPONSE_POLISH_MODEL", "gpt-5.2")
        self.usage_collector = usage_collector

    def polish(
        self,
        *,
        response: UserResponse,
        care_context: dict[str, object] | None = None,
    ) -> UserResponse:
        try:
            client = self.client or self._openai_client()
            api_response = client.responses.create(
                model=self.model,
                input=self._prompt(response=response, care_context=care_context or {}),
            )
            if self.usage_collector is not None:
                self.usage_collector.add(
                    extract_openai_usage_record(
                        api_response,
                        model=self.model,
                        source="response_polisher",
                    )
                )
            polished_message = str(getattr(api_response, "output_text", "")).strip()
            if not polished_message or self._unsafe_text(polished_message):
                return self.fallback.polish(response=response, care_context=care_context)
            return response.model_copy(update={"message": polished_message})
        except Exception:
            return self.fallback.polish(response=response, care_context=care_context)

    def _openai_client(self) -> Any:
        from openai import OpenAI

        return OpenAI()

    def _prompt(
        self,
        *,
        response: UserResponse,
        care_context: dict[str, object],
    ) -> str:
        return (
            "Rewrite the PawCare user-facing message to sound warm, concise, and natural. "
            "Use only the provided structured response and care context. "
            "Do not change status, risk band, guideline IDs, or escalation conditions. "
            "Do not add medical facts, diagnosis, medication dosage, or medication instructions. "
            "Do not over-reassure. Return only the polished message text.\n\n"
            f"Status: {response.status}\n"
            f"Risk band: {response.risk_band}\n"
            f"Guideline IDs: {response.source_guideline_ids}\n"
            f"Escalation conditions: {response.escalation_conditions}\n"
            f"Current message: {response.message}\n"
            f"Care context: {care_context}\n"
        )

    def _unsafe_text(self, value: str) -> bool:
        text = value.lower()
        blocked_terms = [
            *SafetyAgent.diagnosis_terms,
            *SafetyAgent.medication_terms,
            *SafetyAgent.reassurance_terms,
            "your pet is fine",
            "your dog is fine",
            "your cat is fine",
            "use human medicine",
            "community case confirms",
            "similar case confirms",
        ]
        return any(term in text for term in blocked_terms)


def build_response_polisher() -> ResponsePolisher:
    if (
        os.getenv("PAWCARE_ENABLE_LLM_RESPONSE_POLISH", "").lower() == "true"
        and os.getenv("OPENAI_API_KEY")
    ):
        return OpenAIResponsePolisher()
    return DeterministicResponsePolisher()
