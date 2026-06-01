from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pawcare.services.case_models import KnowledgeRecord
from pawcare.services.knowledge_adapters import (
    behavior_reference_to_record,
    community_case_to_record,
    professional_reference_to_record,
)
from pawcare.services.behavior_reference_service import seed_behavior_references
from pawcare.services.professional_reference_service import seed_professional_references
from pawcare.services.similar_case_service import seed_community_cases


class KnowledgePackLoader:
    """Loads curated knowledge records from seeds or manual JSON packs."""

    def load_seed_records(self) -> list[KnowledgeRecord]:
        records: list[KnowledgeRecord] = []
        records.extend(
            professional_reference_to_record(reference)
            for reference in seed_professional_references()
        )
        records.extend(
            behavior_reference_to_record(reference)
            for reference in seed_behavior_references()
        )
        records.extend(community_case_to_record(case) for case in seed_community_cases())
        return records

    def load_json_records(self, path: str | Path) -> list[KnowledgeRecord]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("knowledge pack must be a list of records")
        return [self._record_from_json(item) for item in raw]

    def _record_from_json(self, item: dict[str, Any]) -> KnowledgeRecord:
        return KnowledgeRecord(
            record_id=str(item["record_id"]),
            kind=item["kind"],
            domain=str(item["domain"]),
            source_name=str(item["source_name"]),
            source_url=str(item["source_url"]),
            source_type=str(item.get("source_type", item["kind"])),
            signals=list(item.get("signals", [])),
            summary=str(item["summary"]),
            red_flags=list(item.get("red_flags", [])),
            record_fields=list(item.get("record_fields", [])),
            discussion_topics=list(item.get("discussion_topics", [])),
            safety_notes=list(item.get("safety_notes", [])),
            title=item.get("title"),
            privacy_safe_snippet=item.get("privacy_safe_snippet"),
            vet_outcome=item.get("vet_outcome"),
        )
