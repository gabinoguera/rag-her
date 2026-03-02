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


class TestEstimateEndpoint:
    @pytest.mark.asyncio
    async def test_estimate_basic(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={"query": "Desarrollo de módulo de autenticación OAuth2"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "estimation" in body
        assert "references" in body
        assert "metadata" in body

    @pytest.mark.asyncio
    async def test_estimate_has_three_scenarios(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={"query": "Desarrollo de API REST para gestión de usuarios"},
        )
        assert response.status_code == 200
        estimation = response.json()["estimation"]
        effort = estimation["estimated_effort"]
        assert "optimistic" in effort
        assert "expected" in effort
        assert "pessimistic" in effort
        # Should only have hours, not days or costs
        assert "hours" in effort["expected"]
        assert "days" not in effort["expected"]
        assert "estimated_cost" not in estimation

    @pytest.mark.asyncio
    async def test_estimate_has_breakdown(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={"query": "Desarrollo de módulo de pagos con Stripe"},
        )
        assert response.status_code == 200
        breakdown = response.json()["estimation"]["suggested_breakdown"]
        assert len(breakdown) >= 1
        for item in breakdown:
            assert "name" in item
            assert "tasks" in item
            assert len(item["tasks"]) >= 1
            for task in item["tasks"]:
                assert "name" in task
                assert "hours" in task

    @pytest.mark.asyncio
    async def test_estimate_has_confidence(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={"query": "Desarrollo del sistema de notificaciones push"},
        )
        assert response.status_code == 200
        confidence = response.json()["estimation"]["confidence"]
        assert "score" in confidence
        assert "level" in confidence
        assert "factors" in confidence
        assert 0.0 <= confidence["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_estimate_has_references(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={"query": "Desarrollo del dashboard de analíticas en tiempo real"},
        )
        assert response.status_code == 200
        references = response.json()["references"]
        assert len(references) >= 1
        ref = references[0]
        assert "chunk_id" in ref
        assert "similarity_score" in ref

    @pytest.mark.asyncio
    async def test_estimate_respects_currency(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={
                "query": "Desarrollo de integración con sistema de pagos",
                "options": {"currency": "USD"},
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_estimate_respects_top_k(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={
                "query": "Desarrollo de módulo de gestión de contenidos CMS",
                "options": {"top_k": 3},
            },
        )
        assert response.status_code == 200
        references = response.json()["references"]
        assert len(references) <= 3

    @pytest.mark.asyncio
    async def test_estimate_short_query_fails(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={"query": "short"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_estimate_metadata_complete(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate",
            json={"query": "Estimación para desarrollo de microservicios backend"},
        )
        assert response.status_code == 200
        metadata = response.json()["metadata"]
        assert "llm_model" in metadata
        assert "processing_time_ms" in metadata
        assert "query_embedding_model" in metadata
        assert "chunks_retrieved" in metadata
        assert "chunks_used_for_generation" in metadata

    @pytest.mark.asyncio
    async def test_estimate_batch_basic(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate/batch",
            json={
                "queries": [
                    {"id": "q1", "query": "Desarrollo de módulo de autenticación"},
                    {"id": "q2", "query": "Desarrollo de módulo de pagos online"},
                    {"id": "q3", "query": "Desarrollo de API de reportes analytics"},
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["estimations"]) == 3
        assert "aggregated" in body

    @pytest.mark.asyncio
    async def test_estimate_batch_aggregated(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        await _ingest_full_quote(client_with_mock_llm)
        response = await client_with_mock_llm.post(
            "/api/v1/estimate/batch",
            json={
                "queries": [
                    {"id": "q1", "query": "Desarrollo de módulo de autenticación"},
                    {"id": "q2", "query": "Desarrollo de módulo de pagos online"},
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        aggregated = body["aggregated"]

        # Sum of individual expected hours should match aggregated
        individual_hours = sum(
            item["estimation"]["estimated_effort"]["expected"]["hours"]
            for item in body["estimations"]
            if item.get("estimation")
        )
        assert aggregated["total_estimated_effort"]["expected"]["hours"] == individual_hours

    @pytest.mark.asyncio
    async def test_estimate_batch_max_queries(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        queries = [
            {"id": f"q{i}", "query": f"Desarrollo de módulo número {i} completo"}
            for i in range(21)
        ]
        response = await client_with_mock_llm.post(
            "/api/v1/estimate/batch",
            json={"queries": queries},
        )
        assert response.status_code == 422
