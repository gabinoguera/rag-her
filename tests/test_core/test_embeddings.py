"""Tests for EmbeddingService (google-genai migration, RAG-02).

These tests are written TDD-style: they describe the expected behaviour of the
new Gemini-based EmbeddingService and should FAIL while embeddings.py still
uses OpenAI/tiktoken.  Once RAG-02 is implemented they should all pass.

Mock strategy:
  - We never instantiate a real genai.Client.
  - We replace service._client directly after construction so we avoid patching
    the import in cases where only the client behaviour matters.
  - For init tests we patch "app.core.embeddings.genai.Client" so the
    constructor itself is intercepted.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from app.core.embeddings import EmbeddingError, EmbeddingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_embed_response(vectors: list[list[float]]) -> MagicMock:
    """Build a mock EmbedContentResponse with the given embedding vectors."""
    response = MagicMock()
    response.embeddings = [MagicMock(values=v) for v in vectors]
    return response


def _make_service(mock_aio_response: MagicMock | None = None) -> EmbeddingService:
    """Construct EmbeddingService with a mocked genai client.

    If *mock_aio_response* is provided the async embed_content call will
    return it; otherwise no mock is attached (useful for error-path tests
    where the caller sets up the side_effect themselves).
    """
    service = EmbeddingService(
        api_key="test-key",
        model="text-multilingual-embedding-002",
        dimensions=768,
    )
    if mock_aio_response is not None:
        service._client = MagicMock()
        service._client.aio = MagicMock()
        service._client.aio.models.embed_content = AsyncMock(
            return_value=mock_aio_response
        )
    return service


def _make_service_with_error(error: Exception) -> EmbeddingService:
    """Construct EmbeddingService whose async embed_content raises *error*."""
    service = EmbeddingService(
        api_key="test-key",
        model="text-multilingual-embedding-002",
        dimensions=768,
    )
    service._client = MagicMock()
    service._client.aio = MagicMock()
    service._client.aio.models.embed_content = AsyncMock(side_effect=error)
    return service


# ---------------------------------------------------------------------------
# TestEmbeddingServiceInit
# ---------------------------------------------------------------------------


class TestEmbeddingServiceInit:
    def test_client_initialized_with_api_key(self) -> None:
        """EmbeddingService.__init__ must call genai.Client with the api_key."""
        with patch("app.core.embeddings.genai.Client") as mock_cls:
            EmbeddingService(
                api_key="my-secret-key",
                model="text-multilingual-embedding-002",
                dimensions=768,
            )
            mock_cls.assert_called_once_with(api_key="my-secret-key")

    def test_model_stored_on_instance(self) -> None:
        """The model name passed to __init__ is stored as _model."""
        with patch("app.core.embeddings.genai.Client"):
            svc = EmbeddingService(
                api_key="k",
                model="text-multilingual-embedding-002",
                dimensions=768,
            )
        assert svc._model == "text-multilingual-embedding-002"

    def test_dimensions_stored_on_instance(self) -> None:
        """The dimensions value passed to __init__ is stored as _dimensions."""
        with patch("app.core.embeddings.genai.Client"):
            svc = EmbeddingService(
                api_key="k",
                model="text-multilingual-embedding-002",
                dimensions=768,
            )
        assert svc._dimensions == 768


# ---------------------------------------------------------------------------
# TestGenerateSingleEmbedding
# ---------------------------------------------------------------------------


class TestGenerateSingleEmbedding:
    @pytest.mark.asyncio
    async def test_returns_768_floats(self) -> None:
        """generate_single_embedding returns a list of exactly 768 floats."""
        service = _make_service(_make_mock_embed_response([[0.1] * 768]))
        result = await service.generate_single_embedding("texto de prueba")
        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_task_type_retrieval_document_by_default(self) -> None:
        """Without explicit task_type, RETRIEVAL_DOCUMENT is sent to the SDK."""
        response = _make_mock_embed_response([[0.1] * 768])
        service = _make_service(response)

        await service.generate_single_embedding("indexar chunk")

        call_kwargs = service._client.aio.models.embed_content.call_args
        # Support both positional and keyword call styles
        config = call_kwargs.kwargs.get("config") or (
            call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
        )
        assert config is not None, "config argument not found in embed_content call"
        assert config.task_type == "RETRIEVAL_DOCUMENT"

    @pytest.mark.asyncio
    async def test_task_type_retrieval_query_when_specified(self) -> None:
        """task_type='RETRIEVAL_QUERY' is forwarded to the SDK correctly."""
        response = _make_mock_embed_response([[0.1] * 768])
        service = _make_service(response)

        await service.generate_single_embedding(
            "buscar algo", task_type="RETRIEVAL_QUERY"
        )

        call_kwargs = service._client.aio.models.embed_content.call_args
        config = call_kwargs.kwargs.get("config") or (
            call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
        )
        assert config is not None, "config argument not found in embed_content call"
        assert config.task_type == "RETRIEVAL_QUERY"

    @pytest.mark.asyncio
    async def test_empty_text_raises_embedding_error(self) -> None:
        """An empty string must raise EmbeddingError (not call the SDK)."""
        service = _make_service(_make_mock_embed_response([[0.1] * 768]))
        with pytest.raises(EmbeddingError):
            await service.generate_single_embedding("")


# ---------------------------------------------------------------------------
# TestGenerateEmbeddings  (batch)
# ---------------------------------------------------------------------------


class TestGenerateEmbeddings:
    @pytest.mark.asyncio
    async def test_batch_returns_list_of_768_float_lists(self) -> None:
        """generate_embeddings(['a','b']) returns 2 lists each of 768 floats."""
        vectors = [[0.1] * 768, [0.2] * 768]
        service = _make_service(_make_mock_embed_response(vectors))

        result = await service.generate_embeddings(["texto1", "texto2"])

        assert len(result) == 2
        for emb in result:
            assert len(emb) == 768
            assert all(isinstance(v, float) for v in emb)

    @pytest.mark.asyncio
    async def test_batch_preserves_order(self) -> None:
        """Embeddings are returned in the same order as the input texts."""
        v1 = [0.1] * 768
        v2 = [0.9] * 768
        service = _make_service(_make_mock_embed_response([v1, v2]))

        result = await service.generate_embeddings(["primero", "segundo"])

        assert result[0] == v1
        assert result[1] == v2

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_without_api_call(self) -> None:
        """An empty list returns [] and must NOT call the Gemini SDK."""
        # No mock response provided — if SDK were called it would raise
        service = EmbeddingService(
            api_key="test-key",
            model="text-multilingual-embedding-002",
            dimensions=768,
        )
        # Attach a mock that would fail if called
        service._client = MagicMock()
        service._client.aio = MagicMock()
        service._client.aio.models.embed_content = AsyncMock(
            side_effect=AssertionError("SDK must not be called for empty input")
        )

        result = await service.generate_embeddings([])

        assert result == []
        service._client.aio.models.embed_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_call_to_sdk_for_batch(self) -> None:
        """The batch path makes exactly one SDK call (not one per text)."""
        texts = ["a", "b", "c"]
        vectors = [[float(i)] * 768 for i in range(len(texts))]
        service = _make_service(_make_mock_embed_response(vectors))

        await service.generate_embeddings(texts)

        assert service._client.aio.models.embed_content.call_count == 1


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_resource_exhausted_raises_embedding_error(self) -> None:
        """ResourceExhausted (quota) surfaces as EmbeddingError with quota msg."""
        service = _make_service_with_error(
            google_exceptions.ResourceExhausted("quota exceeded")
        )
        with pytest.raises(EmbeddingError, match="[Rr]ate limit|quota"):
            await service.generate_embeddings(["texto"])

    @pytest.mark.asyncio
    async def test_unauthenticated_raises_embedding_error(self) -> None:
        """Unauthenticated error maps to EmbeddingError with auth message."""
        service = _make_service_with_error(
            google_exceptions.Unauthenticated("invalid API key")
        )
        with pytest.raises(
            EmbeddingError, match="[Aa]uthentication|[Aa]utenticación"
        ):
            await service.generate_embeddings(["texto"])

    @pytest.mark.asyncio
    async def test_null_vector_raises_embedding_error(self) -> None:
        """A response containing an all-zeros vector raises EmbeddingError."""
        service = _make_service(_make_mock_embed_response([[0.0] * 768]))
        with pytest.raises(EmbeddingError):
            await service.generate_embeddings(["texto"])

    @pytest.mark.asyncio
    async def test_google_api_call_error_raises_embedding_error(self) -> None:
        """A generic GoogleAPICallError maps to EmbeddingError."""
        service = _make_service_with_error(
            google_exceptions.GoogleAPICallError("server error")
        )
        with pytest.raises(EmbeddingError, match="[Aa]PI error|[Ee]rror"):
            await service.generate_embeddings(["texto"])

    @pytest.mark.asyncio
    async def test_empty_embeddings_in_response_raises_embedding_error(
        self,
    ) -> None:
        """A response with an empty embeddings list raises EmbeddingError."""
        response = MagicMock()
        response.embeddings = []
        service = _make_service(response)
        with pytest.raises(EmbeddingError):
            await service.generate_embeddings(["texto"])
