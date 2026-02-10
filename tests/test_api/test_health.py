import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_status_healthy(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_docs_accessible(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_includes_database_status(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "dependencies" in data
    assert "database" in data["dependencies"]
    assert data["dependencies"]["database"]["status"] == "healthy"
    assert "latency_ms" in data["dependencies"]["database"]


@pytest.mark.asyncio
async def test_health_includes_pgvector_status(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "dependencies" in data
    assert "pgvector" in data["dependencies"]
    assert data["dependencies"]["pgvector"]["status"] == "healthy"
    assert "version" in data["dependencies"]["pgvector"]
