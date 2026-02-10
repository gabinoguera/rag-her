import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


class TestStatsEndpoint:
    @pytest.mark.asyncio
    async def test_document_count_after_ingest(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_platform_ia.json")
        await client_with_mock_embeddings.post("/api/v1/ingest", json=data)

        response = await client_with_mock_embeddings.get("/api/v1/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["documents_by_status"].get("completed", 0) >= 1

    @pytest.mark.asyncio
    async def test_chunks_by_type_after_ingest(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_platform_ia.json")
        await client_with_mock_embeddings.post("/api/v1/ingest", json=data)

        response = await client_with_mock_embeddings.get("/api/v1/stats")
        assert response.status_code == 200
        body = response.json()
        # Full quote produces 20 chunks total
        total_chunks = sum(body["chunks_by_type"].values())
        assert total_chunks == 20

    @pytest.mark.asyncio
    async def test_search_metrics_empty(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.get("/api/v1/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["search_metrics_last_30d"]["total_searches"] == 0
        assert body["search_metrics_last_30d"]["avg_response_time_ms"] is None

    @pytest.mark.asyncio
    async def test_embedding_model_info(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.get("/api/v1/stats")
        assert response.status_code == 200
        body = response.json()
        assert "embedding_model" in body
        assert "embedding_dimensions" in body
        assert body["embedding_dimensions"] == 1536
