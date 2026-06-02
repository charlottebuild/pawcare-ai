from pawcare.services import (
    KnowledgeChunker,
    KnowledgeDocument,
    SQLiteKnowledgeFTSIndex,
    seed_professional_knowledge_documents,
)


def test_chunker_creates_overlapping_metadata_injected_chunks() -> None:
    document = KnowledgeDocument(
        document_id="doc_test",
        source_name="Vet Manual",
        source_url="https://example.com/vet",
        domain="oral_neck",
        species=["dog"],
        allowed_use="supporting context only",
        signals=["salivary_gland", "tongue_lump"],
        red_flags=["trouble swallowing"],
        raw_or_manual_summary=" ".join(f"word{i}" for i in range(150)),
    )
    chunks = KnowledgeChunker(chunk_words=50, overlap_words=10).chunk(document)

    assert len(chunks) >= 3
    assert "source=Vet Manual" in chunks[0].metadata_header
    assert "domain=oral_neck" in chunks[0].metadata_header
    assert "non_diagnostic_no_medication_dosage" in chunks[0].metadata_header
    assert set(chunks[0].chunk_text.split()) & set(chunks[1].chunk_text.split())


def test_sqlite_fts_retrieves_professional_chunks_with_source_and_summary(tmp_path) -> None:
    index = SQLiteKnowledgeFTSIndex(tmp_path / "knowledge.sqlite3")
    index.ingest_documents(seed_professional_knowledge_documents())

    oral = index.search(query_text="tongue lump could it be salivary mucocele", limit=2)
    urinary = index.search(query_text="cat cannot pee all day", limit=2)
    behavior = index.search(query_text="resource guarding freezing lip licking", limit=2)

    assert oral[0].record.domain == "oral_neck"
    assert oral[0].record.source_url.startswith("https://")
    assert len(oral[0].record.summary) < 600
    assert urinary[0].record.domain == "urinary"
    assert behavior[0].record.domain == "resource_guarding"
    assert "no_medication_dosage" in behavior[0].record.safety_notes
