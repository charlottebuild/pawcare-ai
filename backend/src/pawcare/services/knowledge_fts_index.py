from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pawcare.services.case_models import KnowledgeChunk, KnowledgeDocument, KnowledgeMatch, KnowledgeRecord
from pawcare.skills.symptom_understanding import extract_canonical_terms, normalize_identifier


class KnowledgeChunker:
    """Create metadata-injected overlapping chunks from curated documents."""

    def __init__(self, *, chunk_words: int = 70, overlap_words: int = 18) -> None:
        self.chunk_words = chunk_words
        self.overlap_words = overlap_words

    def chunk(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        words = document.raw_or_manual_summary.split()
        if not words:
            return []
        step = max(1, self.chunk_words - self.overlap_words)
        chunks: list[KnowledgeChunk] = []
        for index, start in enumerate(range(0, len(words), step), start=1):
            window = words[start : start + self.chunk_words]
            if not window:
                continue
            metadata_header = self._metadata_header(document)
            chunk_id = f"{document.document_id}_chunk_{index:03d}"
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    chunk_text=" ".join(window),
                    metadata_header=metadata_header,
                    domain=document.domain,
                    signals=list(document.signals),
                    source_name=document.source_name,
                    source_url=document.source_url,
                    species=list(document.species),
                )
            )
            if start + self.chunk_words >= len(words):
                break
        return chunks

    def _metadata_header(self, document: KnowledgeDocument) -> str:
        return (
            f"source={document.source_name}; domain={document.domain}; "
            f"species={','.join(document.species)}; allowed_use={document.allowed_use}; "
            f"signals={','.join(document.signals)}; red_flags={','.join(document.red_flags)}; "
            "safety=non_diagnostic_no_medication_dosage"
        )


class SQLiteKnowledgeFTSIndex:
    """SQLite FTS-backed professional knowledge index for local RAG."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._memory_connection: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._memory_connection = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def ingest_documents(self, documents: list[KnowledgeDocument]) -> None:
        chunker = KnowledgeChunker()
        with self._connect() as connection:
            for document in documents:
                for chunk in chunker.chunk(document):
                    connection.execute(
                        """
                        insert or replace into knowledge_chunks (
                            chunk_id, document_id, domain, source_name, source_url,
                            species_json, signals_json, metadata_header, chunk_text
                        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.domain,
                            chunk.source_name,
                            chunk.source_url,
                            json.dumps(chunk.species, sort_keys=True),
                            json.dumps(chunk.signals, sort_keys=True),
                            chunk.metadata_header,
                            chunk.chunk_text,
                        ),
                    )
                    connection.execute(
                        """
                        insert or replace into knowledge_chunks_fts (
                            chunk_id, searchable_text
                        ) values (?, ?)
                        """,
                        (chunk.chunk_id, f"{chunk.metadata_header} {chunk.chunk_text}"),
                    )

    def search(
        self,
        *,
        query_text: str,
        domains: set[str] | None = None,
        limit: int = 3,
    ) -> list[KnowledgeMatch]:
        terms = sorted(
            {
                normalize_identifier(term)
                for term in [*extract_canonical_terms(query_text), *query_text.split()]
                if normalize_identifier(term)
            }
        )
        if not terms:
            return []
        fts_query = " OR ".join(self._escape_fts(term) for term in terms[:12])
        with self._connect() as connection:
            rows = connection.execute(
                """
                select c.*
                from knowledge_chunks_fts f
                join knowledge_chunks c on c.chunk_id = f.chunk_id
                where knowledge_chunks_fts match ?
                order by bm25(knowledge_chunks_fts)
                limit ?
                """,
                (fts_query, max(limit * 3, 10)),
            ).fetchall()
        matches: list[KnowledgeMatch] = []
        query_terms = set(terms)
        for row in rows:
            domain = str(row["domain"])
            if domains is not None and domain not in domains:
                continue
            signals = json.loads(str(row["signals_json"]))
            record_terms = {
                normalize_identifier(term)
                for term in [domain, *signals, str(row["source_name"]), str(row["chunk_text"])]
                for term in str(term).split()
            }
            matched = sorted((query_terms & record_terms) or (query_terms & {domain, *signals}))
            if not matched:
                matched = [domain]
            record = KnowledgeRecord(
                record_id=str(row["chunk_id"]),
                kind="professional",
                domain=domain,
                source_name=str(row["source_name"]),
                source_url=str(row["source_url"]),
                source_type="professional_rag_chunk",
                signals=signals,
                summary=str(row["chunk_text"]),
                record_fields=["metadata-injected professional chunk"],
                discussion_topics=signals,
                safety_notes=["not_diagnosis", "no_medication_dosage", str(row["metadata_header"])],
            )
            score = len(matched) + (2 if domain in matched else 0)
            matches.append(
                KnowledgeMatch(
                    record=record,
                    matched_signals=matched,
                    relevance_score=score,
                    relevance_level="high" if score >= 4 else "medium",
                    source_type=record.source_type,
                )
            )
            if len(matches) >= limit:
                break
        return matches

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                create table if not exists knowledge_chunks (
                    chunk_id text primary key,
                    document_id text not null,
                    domain text not null,
                    source_name text not null,
                    source_url text not null,
                    species_json text not null,
                    signals_json text not null,
                    metadata_header text not null,
                    chunk_text text not null
                );
                create virtual table if not exists knowledge_chunks_fts
                using fts5(chunk_id unindexed, searchable_text);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        if self._memory_connection is not None:
            return self._memory_connection
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _escape_fts(self, term: str) -> str:
        safe = term.replace('"', "").replace("'", "")
        return f'"{safe}"'


def seed_professional_knowledge_documents() -> list[KnowledgeDocument]:
    return [
        KnowledgeDocument(
            document_id="doc_oral_salivary_001",
            source_name="ACVS - Salivary Mucocele",
            source_url="https://www.acvs.org/small-animal/sialocele/",
            domain="oral_neck",
            species=["dog", "cat"],
            allowed_use="supporting triage context only",
            signals=["salivary_gland", "tongue_lump", "drooling", "head_withdrawal", "oral_mass"],
            red_flags=["trouble breathing", "trouble swallowing", "rapid swelling", "refuses food"],
            raw_or_manual_summary=(
                "Soft swelling around the jaw, neck, mouth, or under the tongue can be discussed "
                "with a veterinarian as a salivary or oral concern. Eating changes, head withdrawal "
                "while eating, drooling, swallowing changes, bleeding, rapid swelling, and breathing "
                "difficulty are important to record. The app should not diagnose salivary mucocele; "
                "it should suggest documenting location, size, growth speed, photos, appetite, and "
                "whether swallowing or breathing seems affected."
            ),
        ),
        KnowledgeDocument(
            document_id="doc_mobility_rehab_001",
            source_name="ACVS / AAHA - Post-op Mobility and Pain Context",
            source_url="https://www.acvs.org/es/small-animal/partial-acl-injury/",
            domain="mobility",
            species=["dog"],
            allowed_use="supporting triage context only",
            signals=["acl", "post_op", "non_weight_bearing", "patellar_luxation", "rehab_reluctance", "pain"],
            red_flags=["sudden non-weight-bearing", "post-op decline", "worsening pain"],
            raw_or_manual_summary=(
                "After ACL or knee-related surgery, reluctance with prescribed exercises, changes in "
                "weight bearing, pain signs, swelling, and worsening mobility should be discussed with "
                "the veterinary team. Supportive context can suggest recording gait videos, affected "
                "limb, pain behavior, incision status, activity before onset, and exercise tolerance. "
                "The app should not change a vet-prescribed rehab plan, but can suggest asking the vet "
                "whether timing, comfort, rewards, or environment modifications are appropriate."
            ),
        ),
        KnowledgeDocument(
            document_id="doc_urinary_cat_001",
            source_name="Cornell Feline Health Center - FLUTD",
            source_url="https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center/health-information/feline-health-topics/feline-lower-urinary-tract-disease",
            domain="urinary",
            species=["cat", "dog"],
            allowed_use="urgent triage context only",
            signals=["urinary", "cannot_pee", "bloody_urine", "straining", "no_urine"],
            red_flags=["cannot urinate", "little or no urine", "painful straining", "vomiting", "collapse"],
            raw_or_manual_summary=(
                "Cats that cannot urinate, strain repeatedly, pass little or no urine, or have blood "
                "in urine need urgent veterinary triage because urinary obstruction can become serious. "
                "Useful records include last urination, amount, litter box attempts, straining, blood, "
                "pain signs, water intake, vomiting, and energy. The app cannot diagnose obstruction "
                "or UTI, but should treat no urine all day as an urgent red flag."
            ),
        ),
        KnowledgeDocument(
            document_id="doc_behavior_resource_001",
            source_name="AAHA / Merck - Behavior Management Context",
            source_url="https://www.aaha.org/resources/2015-aaha-canine-and-feline-behavior-management-guidelines/behavior-management-home-2/",
            domain="resource_guarding",
            species=["dog", "cat"],
            allowed_use="supporting behavior context only",
            signals=["resource_guarding", "stress_signals", "growling", "freezing", "lip_licking", "hiding"],
            red_flags=["growling", "air snap", "bite attempt", "cannot settle"],
            raw_or_manual_summary=(
                "Behavior interpretation should consider body language, trigger, distance, duration, "
                "resource context, and recovery. Subtle stress such as lip licking, whale eye, freezing, "
                "hiding, flattened ears, or tail tucked can matter even without overt aggression. Food, "
                "chews, toys, resting places, and owner attention may increase tension. The app should "
                "recommend management and observation, not punishment or forced testing."
            ),
        ),
    ]
