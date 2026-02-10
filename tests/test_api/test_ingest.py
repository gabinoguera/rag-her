import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


class TestIngestEndpoint:
    @pytest.mark.asyncio
    async def test_ingest_full_quote(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_platform_ia.json")
        response = await client_with_mock_embeddings.post("/api/v1/ingest", json=data)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert "document_id" in body
        assert "20 chunks" in body["message"]

    @pytest.mark.asyncio
    async def test_ingest_minimal_quote(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_minimal.json")
        response = await client_with_mock_embeddings.post("/api/v1/ingest", json=data)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert "3 chunks" in body["message"]

    @pytest.mark.asyncio
    async def test_ingest_invalid_json(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/ingest",
            json={"quote": {"not_a_valid_field": True}},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_missing_items(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_invalid_missing_items.json")
        response = await client_with_mock_embeddings.post("/api/v1/ingest", json=data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_duplicate_detection(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_platform_ia.json")

        # First ingest should succeed
        response1 = await client_with_mock_embeddings.post("/api/v1/ingest", json=data)
        assert response1.status_code == 200

        # Second ingest of same quote should return 409
        response2 = await client_with_mock_embeddings.post("/api/v1/ingest", json=data)
        assert response2.status_code == 409

    @pytest.mark.asyncio
    async def test_ingest_payload_too_large(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_minimal.json")
        response = await client_with_mock_embeddings.post(
            "/api/v1/ingest",
            json=data,
            headers={"content-length": str(6 * 1024 * 1024)},  # 6MB header
        )
        assert response.status_code == 413


class TestIngestStatusEndpoint:
    @pytest.mark.asyncio
    async def test_ingest_status_success(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_platform_ia.json")
        ingest_response = await client_with_mock_embeddings.post(
            "/api/v1/ingest", json=data
        )
        doc_id = ingest_response.json()["document_id"]

        response = await client_with_mock_embeddings.get(
            f"/api/v1/ingest/{doc_id}/status"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["chunks_created"] == 20
        assert body["breakdown"]["project_overview"] == 1
        assert body["breakdown"]["scope_block"] == 3
        assert body["breakdown"]["line_item"] == 10
        assert body["breakdown"]["phase"] == 5
        assert body["breakdown"]["team_conditions"] == 1

    @pytest.mark.asyncio
    async def test_ingest_status_not_found(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await client_with_mock_embeddings.get(
            f"/api/v1/ingest/{fake_id}/status"
        )
        assert response.status_code == 404


class TestDeleteEndpoint:
    @pytest.mark.asyncio
    async def test_delete_document(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        data = _load_fixture("quote_minimal.json")
        ingest_response = await client_with_mock_embeddings.post(
            "/api/v1/ingest", json=data
        )
        doc_id = ingest_response.json()["document_id"]

        # Delete
        response = await client_with_mock_embeddings.delete(
            f"/api/v1/ingest/{doc_id}"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "deleted"
        assert body["chunks_deleted"] == 3

        # Verify it's gone
        status_response = await client_with_mock_embeddings.get(
            f"/api/v1/ingest/{doc_id}/status"
        )
        assert status_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await client_with_mock_embeddings.delete(
            f"/api/v1/ingest/{fake_id}"
        )
        assert response.status_code == 404
