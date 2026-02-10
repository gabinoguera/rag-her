from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIError, AuthenticationError, RateLimitError

from app.core.embeddings import EmbeddingError, EmbeddingService


def _make_mock_response(
    embeddings: list[list[float]], total_tokens: int = 100
) -> MagicMock:
    response = MagicMock()
    response.data = [MagicMock(embedding=emb) for emb in embeddings]
    response.usage = MagicMock(total_tokens=total_tokens)
    return response


def _make_service(mock_response: MagicMock | None = None) -> EmbeddingService:
    service = EmbeddingService(api_key="test-key", model="test-model", dimensions=1536)
    if mock_response is not None:
        service._client = MagicMock()
        service._client.embeddings = MagicMock()
        service._client.embeddings.create = AsyncMock(return_value=mock_response)
    return service


class TestGenerateSingleEmbedding:
    @pytest.mark.asyncio
    async def test_returns_correct_dimensions(self) -> None:
        emb = [0.1] * 1536
        service = _make_service(_make_mock_response([emb]))

        result = await service.generate_single_embedding("test text")
        assert len(result) == 1536
        assert result == emb

    @pytest.mark.asyncio
    async def test_calls_api_with_text(self) -> None:
        emb = [0.1] * 1536
        service = _make_service(_make_mock_response([emb]))

        await service.generate_single_embedding("hello world")
        service._client.embeddings.create.assert_called_once_with(
            model="test-model", input=["hello world"]
        )


class TestGenerateBatchEmbeddings:
    @pytest.mark.asyncio
    async def test_returns_n_embeddings(self) -> None:
        embs = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        service = _make_service(_make_mock_response(embs))

        result = await service.generate_embeddings(["text1", "text2", "text3"])
        assert len(result) == 3
        assert all(len(e) == 1536 for e in result)

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self) -> None:
        service = _make_service()
        result = await service.generate_embeddings([])
        assert result == []


class TestEmbeddingValidation:
    @pytest.mark.asyncio
    async def test_wrong_dimensions_raises(self) -> None:
        emb = [0.1] * 768  # Wrong dimensions
        service = _make_service(_make_mock_response([emb]))

        with pytest.raises(EmbeddingError, match="dimensions"):
            await service.generate_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_null_vector_raises(self) -> None:
        emb = [0.0] * 1536  # All zeros
        service = _make_service(_make_mock_response([emb]))

        with pytest.raises(EmbeddingError, match="null vector"):
            await service.generate_embeddings(["test"])


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_auth_error_raises_embedding_error(self) -> None:
        service = _make_service()
        service._client = MagicMock()
        service._client.embeddings = MagicMock()
        service._client.embeddings.create = AsyncMock(
            side_effect=AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401),
                body=None,
            )
        )

        with pytest.raises(EmbeddingError, match="Authentication"):
            await service.generate_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_rate_limit_raises_embedding_error(self) -> None:
        service = _make_service()
        service._client = MagicMock()
        service._client.embeddings = MagicMock()
        service._client.embeddings.create = AsyncMock(
            side_effect=RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )
        )

        with pytest.raises(EmbeddingError, match="Rate limit"):
            await service.generate_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_api_error_raises_embedding_error(self) -> None:
        service = _make_service()
        service._client = MagicMock()
        service._client.embeddings = MagicMock()
        service._client.embeddings.create = AsyncMock(
            side_effect=APIError(
                message="Server error",
                request=MagicMock(),
                body=None,
            )
        )

        with pytest.raises(EmbeddingError, match="API error"):
            await service.generate_embeddings(["test"])
