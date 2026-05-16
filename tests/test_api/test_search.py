import pytest
from httpx import AsyncClient


class TestSearchEndpoint:
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="EPIC-002: rag.chunks no existe en her_poc, se migra a her.check_in_chunks")
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

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="EPIC-002: rag.chunks no existe en her_poc, se migra a her.check_in_chunks")
    async def test_search_response_format(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
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
    async def test_search_top_k_out_of_range_returns_422(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "test", "top_k": 0},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="EPIC-002: rag.chunks no existe en her_poc, se migra a her.check_in_chunks")
    async def test_search_valid_top_k_accepted(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "test", "top_k": 5},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_min_similarity_out_of_range_returns_422(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        response = await client_with_mock_embeddings.post(
            "/api/v1/search",
            json={"query": "test", "min_similarity": 1.5},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_legacy_ingest_endpoint_not_found(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        """Legacy /api/v1/ingest endpoint must not exist (EPIC-001 cleanup)."""
        response = await client_with_mock_embeddings.post(
            "/api/v1/ingest",
            json={},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_legacy_stats_endpoint_not_found(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        """Legacy /api/v1/stats endpoint must not exist (EPIC-001 cleanup)."""
        response = await client_with_mock_embeddings.get("/api/v1/stats")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_legacy_estimate_endpoint_not_found(
        self, client_with_mock_embeddings: AsyncClient
    ) -> None:
        """Legacy /api/v1/estimate endpoint must not exist (EPIC-001 cleanup)."""
        response = await client_with_mock_embeddings.post(
            "/api/v1/estimate",
            json={},
        )
        assert response.status_code == 404
