import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


async def _ingest_full_quote(client: AsyncClient) -> str:
    """Helper: ingest the full quote fixture and return document_id."""
    data = _load_fixture("quote_platform_ia.json")
    response = await client.post("/api/v1/ingest", json=data)
    assert response.status_code == 200
    return response.json()["document_id"]


class TestSearchEndpoint:
    @pytest.mark.asyncio
    async def test_basic_search_returns_results(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_embeddings)

        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "backend API desarrollo"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_results"] > 0
        assert len(body["results"]) > 0

    @pytest.mark.asyncio
    async def test_search_filter_by_chunk_type(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_embeddings)

        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={
                "query": "presupuesto del proyecto",
                "filters": {"chunk_types": ["project_overview"]},
            },
        )
        assert response.status_code == 200
        body = response.json()
        for result in body["results"]:
            assert result["chunk_type"] == "project_overview"

    @pytest.mark.asyncio
    async def test_search_filter_by_technologies(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_embeddings)

        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={
                "query": "desarrollo con React",
                "filters": {"technologies": ["React"]},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_results"] > 0
        # All returned chunks should have React in their technologies
        for result in body["results"]:
            if result["technologies"]:
                assert "React" in result["technologies"]

    @pytest.mark.asyncio
    async def test_search_response_format(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_embeddings)

        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "proyecto IA"},
        )
        assert response.status_code == 200
        body = response.json()

        assert "results" in body
        assert "total_results" in body
        assert "query_processing_time_ms" in body
        assert "detected_technologies" in body
        assert "suggested_chunk_types" in body

        if body["results"]:
            item = body["results"][0]
            assert "chunk_id" in item
            assert "chunk_type" in item
            assert "similarity_score" in item
            assert "final_score" in item
            assert "content_text" in item
            assert "source_document_id" in item

    @pytest.mark.asyncio
    async def test_search_top_k_limits_results(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_embeddings)

        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "desarrollo", "top_k": 3},
        )
        assert response.status_code == 200
        body = response.json()
        # After dedup, should be at most 3 (but dedup can reduce further)
        assert body["total_results"] <= 3

    @pytest.mark.asyncio
    async def test_search_empty_query_whitespace_returns_400(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "   "},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_search_empty_string_returns_422(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": ""},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_results_ordered_by_final_score(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_embeddings)

        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "React frontend desarrollo"},
        )
        assert response.status_code == 200
        body = response.json()
        scores = [r["final_score"] for r in body["results"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_search_logging_recorded(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_embeddings)

        # Perform a search
        await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "backend API"},
        )

        # Check stats to verify search was logged
        stats_response = await client_with_mock_embeddings.get("/api/v1/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["search_metrics_last_30d"]["total_searches"] >= 1

    @pytest.mark.asyncio
    async def test_search_invalid_chunk_type_returns_422(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={
                "query": "test",
                "filters": {"chunk_types": ["invalid_type"]},
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_no_results_empty_db(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "busqueda sin datos"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_results"] == 0
        assert body["results"] == []
