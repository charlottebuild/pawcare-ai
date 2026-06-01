from __future__ import annotations

import os
from typing import Any, Protocol


class KnowledgeSummarizer(Protocol):
    def summarize(
        self,
        *,
        matches: list[dict[str, object]],
        raw_text: str,
        pet_context: dict[str, object],
    ) -> str:
        """Return a short non-diagnostic context summary."""


class DeterministicKnowledgeSummarizer:
    def summarize(
        self,
        *,
        matches: list[dict[str, object]],
        raw_text: str,
        pet_context: dict[str, object],
    ) -> str:
        if not matches:
            return ""
        pet_name = str(pet_context.get("name") or "your pet")
        topics = self._topics(matches)
        red_flags = self._red_flags(matches)
        summary = (
            f"For {pet_name}, these references are supporting context, not a diagnosis. "
            f"Discuss these possible directions with a veterinarian: {', '.join(topics[:4])}."
        )
        if red_flags:
            summary += f" Watch urgently for: {'; '.join(red_flags[:3])}."
        return summary

    def _topics(self, matches: list[dict[str, object]]) -> list[str]:
        topics: list[str] = []
        for match in matches:
            for key in ("vet_discussion_topics", "possible_discussion_topics"):
                for item in match.get(key, []) if isinstance(match.get(key), list) else []:
                    text = str(item)
                    if text and text not in topics:
                        topics.append(text)
            domain = str(match.get("domain") or "")
            if domain and domain not in topics:
                topics.append(domain)
        return topics or ["symptom tracking"]

    def _red_flags(self, matches: list[dict[str, object]]) -> list[str]:
        flags: list[str] = []
        for match in matches:
            red_flags = match.get("red_flags", [])
            if not isinstance(red_flags, list):
                continue
            for item in red_flags:
                text = str(item)
                if text and text not in flags:
                    flags.append(text)
        return flags


class OpenAIKnowledgeSummarizer:
    def __init__(
        self,
        *,
        fallback: KnowledgeSummarizer | None = None,
        client: Any | None = None,
        model: str | None = None,
    ) -> None:
        self.fallback = fallback or DeterministicKnowledgeSummarizer()
        self.client = client
        self.model = model or os.getenv("PAWCARE_SUMMARY_MODEL", "gpt-5.2")

    def summarize(
        self,
        *,
        matches: list[dict[str, object]],
        raw_text: str,
        pet_context: dict[str, object],
    ) -> str:
        if not matches:
            return ""
        try:
            client = self.client or self._openai_client()
            response = client.responses.create(
                model=self.model,
                input=self._prompt(
                    matches=matches,
                    raw_text=raw_text,
                    pet_context=pet_context,
                ),
            )
            text = getattr(response, "output_text", "")
            return str(text).strip() or self._fallback(
                matches=matches,
                raw_text=raw_text,
                pet_context=pet_context,
            )
        except Exception:
            return self._fallback(
                matches=matches,
                raw_text=raw_text,
                pet_context=pet_context,
            )

    def _openai_client(self) -> Any:
        from openai import OpenAI

        return OpenAI()

    def _fallback(
        self,
        *,
        matches: list[dict[str, object]],
        raw_text: str,
        pet_context: dict[str, object],
    ) -> str:
        return self.fallback.summarize(
            matches=matches,
            raw_text=raw_text,
            pet_context=pet_context,
        )

    def _prompt(
        self,
        *,
        matches: list[dict[str, object]],
        raw_text: str,
        pet_context: dict[str, object],
    ) -> str:
        return (
            "Summarize these pet care references in 2-3 short sentences. "
            "Do not diagnose. Do not provide medication dosage or medication instructions. "
            "Frame topics as possible directions to discuss with a veterinarian.\n\n"
            f"Pet context: {pet_context}\n"
            f"User text: {raw_text}\n"
            f"Reference matches: {matches}"
        )


def build_knowledge_summarizer() -> KnowledgeSummarizer:
    if (
        os.getenv("PAWCARE_ENABLE_OPENAI_SUMMARY", "").lower() == "true"
        and os.getenv("OPENAI_API_KEY")
    ):
        return OpenAIKnowledgeSummarizer()
    return DeterministicKnowledgeSummarizer()
