import json
import uuid
from pathlib import Path
from typing import Any

from app.api.schemas.quote_input import IngestRequest, QuoteInput
from app.core.anonymization import anonymize_quote
from app.core.chunking import ChunkData, generate_chunks

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
DOC_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


def _get_full_quote() -> QuoteInput:
    data = _load_fixture("quote_platform_ia.json")
    return IngestRequest.model_validate(data).quote


def _get_minimal_quote() -> QuoteInput:
    data = _load_fixture("quote_minimal.json")
    return IngestRequest.model_validate(data).quote


def _get_anonymized_full_quote() -> QuoteInput:
    quote = _get_full_quote()
    anon, _, _ = anonymize_quote(quote)
    return anon


def _chunks_by_type(chunks: list[ChunkData]) -> dict[str, list[ChunkData]]:
    result: dict[str, list[ChunkData]] = {}
    for c in chunks:
        result.setdefault(c.chunk_type, []).append(c)
    return result


# ---------------------------------------------------------------------------
# Full quote tests
# ---------------------------------------------------------------------------


class TestFullQuoteChunking:
    def test_chunk_count(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        assert len(chunks) == 20

    def test_chunk_types_distribution(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        by_type = _chunks_by_type(chunks)

        assert len(by_type["project_overview"]) == 1
        assert len(by_type["scope_block"]) == 3
        assert len(by_type["line_item"]) == 10
        assert len(by_type["phase"]) == 5
        assert len(by_type["team_conditions"]) == 1

    def test_project_overview_content(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        overview = [c for c in chunks if c.chunk_type == "project_overview"][0]

        assert "Plataforma de Gestion con IA" in overview.content_text
        assert "Ruby on Rails" in overview.content_text
        assert "29200" in overview.content_text
        assert "12 semanas" in overview.content_text

    def test_project_overview_metadata(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        overview = [c for c in chunks if c.chunk_type == "project_overview"][0]

        assert overview.metadata["total_budget"] == 29200.0
        assert overview.metadata["team_size"] == 6
        assert overview.metadata["total_duration_weeks"] == 12
        assert overview.metadata["scope_blocks_count"] == 3
        assert overview.metadata["items_count"] == 10
        assert overview.metadata["phases_count"] == 5

    def test_scope_block_content_backend(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        backend = [
            c for c in chunks
            if c.chunk_type == "scope_block" and "Backend API" in c.content_text
        ][0]

        assert "JWT" in backend.content_text
        assert "Rate limiting" in backend.content_text or "rate limiting" in backend.content_text
        assert "Ruby on Rails" in backend.content_text

    def test_scope_block_linked_items_backend(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        backend = [
            c for c in chunks
            if c.chunk_type == "scope_block" and c.metadata.get("block_title") == "Backend API"
        ][0]

        related = backend.metadata["related_items"]
        assert len(related) >= 2
        assert backend.metadata["block_total_cost"] > 0

    def test_scope_block_content_ia(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        ia = [
            c for c in chunks
            if c.chunk_type == "scope_block" and "Modulo IA" in c.content_text
        ][0]

        assert "chatbot" in ia.content_text.lower()
        assert "OpenAI" in ia.content_text

    def test_line_item_content(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        api_item = [
            c for c in chunks
            if c.chunk_type == "line_item" and "Desarrollo API REST" in c.content_text
        ][0]

        assert "15" in api_item.content_text
        assert "500" in api_item.content_text
        assert "7500" in api_item.content_text

    def test_line_item_metadata(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        api_item = [
            c for c in chunks
            if c.chunk_type == "line_item"
            and c.metadata.get("item_name") == "Desarrollo API REST"
        ][0]

        assert api_item.metadata["quantity"] == 15
        assert api_item.metadata["unit_price"] == 500
        assert api_item.metadata["total_price"] == 7500.0
        assert api_item.metadata["unit"] == "dia"

    def test_phase_content(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        phase2 = [
            c for c in chunks
            if c.chunk_type == "phase"
            and "Desarrollo Backend" in c.content_text
        ][0]

        assert "4 semanas" in phase2.content_text
        assert "Backend API" in phase2.content_text or "API REST" in phase2.content_text.lower()

    def test_phase_metadata(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        phase2 = [
            c for c in chunks
            if c.chunk_type == "phase"
            and c.metadata.get("phase_name") == "Fase 2: Desarrollo Backend"
        ][0]

        assert phase2.metadata["duration_weeks"] == 4
        assert phase2.metadata["phase_total_cost"] == 9750.0
        assert phase2.metadata["items_count"] == 2

    def test_team_conditions_content(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        team = [c for c in chunks if c.chunk_type == "team_conditions"][0]

        assert "Tech Lead" in team.content_text
        assert "Full Stack" in team.content_text
        assert "30%" in team.content_text
        assert "Soporte extendido" in team.content_text

    def test_team_conditions_metadata(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        team = [c for c in chunks if c.chunk_type == "team_conditions"][0]

        assert team.metadata["total_team_size"] == 6
        assert team.metadata["payment_milestones"] == 4
        assert len(team.metadata["team_composition"]) == 5

    def test_all_chunks_have_project_title(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        for chunk in chunks:
            assert chunk.project_title == "Plataforma de Gestion con IA"

    def test_all_chunks_have_currency(self) -> None:
        quote = _get_full_quote()
        chunks = generate_chunks(quote, DOC_ID)
        for chunk in chunks:
            assert chunk.currency == "EUR"


# ---------------------------------------------------------------------------
# Minimal quote tests
# ---------------------------------------------------------------------------


class TestMinimalQuoteChunking:
    def test_minimal_chunk_count(self) -> None:
        quote = _get_minimal_quote()
        chunks = generate_chunks(quote, DOC_ID)
        # 1 overview + 1 scope_block + 1 line_item + 0 phases + 0 team = 3
        assert len(chunks) == 3

    def test_minimal_chunk_types(self) -> None:
        quote = _get_minimal_quote()
        chunks = generate_chunks(quote, DOC_ID)
        types = [c.chunk_type for c in chunks]
        assert "project_overview" in types
        assert "scope_block" in types
        assert "line_item" in types
        assert "phase" not in types
        assert "team_conditions" not in types


# ---------------------------------------------------------------------------
# Anonymization integration
# ---------------------------------------------------------------------------


class TestAnonymizationInChunks:
    def test_no_client_name_in_chunks(self) -> None:
        anon = _get_anonymized_full_quote()
        chunks = generate_chunks(anon, DOC_ID)
        for chunk in chunks:
            assert "Juan Garcia" not in chunk.content_text

    def test_no_client_email_in_chunks(self) -> None:
        anon = _get_anonymized_full_quote()
        chunks = generate_chunks(anon, DOC_ID)
        for chunk in chunks:
            assert "juan.garcia@empresa.com" not in chunk.content_text
