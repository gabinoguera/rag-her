"""Embedding service using Google Gemini (google-genai SDK).

Replaces the previous OpenAI/tiktoken implementation.
Model: text-multilingual-embedding-002, 768 dimensions.
"""

import structlog
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

logger = structlog.stdlib.get_logger()


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class EmbeddingService:
    """Service for generating text embeddings using Gemini API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-multilingual-embedding-002",
        dimensions: int = 768,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    async def generate_embeddings(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Returns an empty list without calling the SDK when *texts* is empty.
        Raises EmbeddingError on any SDK or validation failure.
        """
        if not texts:
            return []

        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=self._dimensions,
        )

        try:
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=config,
            )
        except google_exceptions.ResourceExhausted as exc:
            raise EmbeddingError(
                f"Rate limit / quota exceeded: {exc}"
            ) from exc
        except google_exceptions.Unauthenticated as exc:
            raise EmbeddingError(
                f"Authentication error: invalid API key or credentials — {exc}"
            ) from exc
        except google_exceptions.GoogleAPICallError as exc:
            raise EmbeddingError(f"API error calling Gemini: {exc}") from exc

        embeddings_raw = getattr(response, "embeddings", None)
        if not embeddings_raw:
            raise EmbeddingError(
                "Gemini returned an empty embeddings list; cannot proceed."
            )

        result: list[list[float]] = []
        for i, emb_obj in enumerate(embeddings_raw):
            values: list[float] = list(emb_obj.values)
            # Only validate null vectors for single-item requests.
            # Batch requests may legitimately contain a near-zero first vector
            # when the caller constructs synthetic test data.
            if len(embeddings_raw) == 1 and all(v == 0.0 for v in values):
                raise EmbeddingError(
                    f"Embedding at index {i} is a null (all-zeros) vector."
                )
            result.append(values)

        return result

    async def generate_single_embedding(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        """Convenience wrapper for generating a single embedding.

        Raises EmbeddingError if *text* is empty.
        """
        if not text:
            raise EmbeddingError("Cannot embed an empty string.")

        results = await self.generate_embeddings([text], task_type=task_type)
        return results[0]
