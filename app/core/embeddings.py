import structlog
from openai import APIError, AsyncOpenAI, AuthenticationError, RateLimitError

logger = structlog.stdlib.get_logger()


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class EmbeddingService:
    """Service for generating text embeddings using OpenAI API."""

    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        self._client = AsyncOpenAI(api_key=api_key, max_retries=3)
        self._model = model
        self._dimensions = dimensions

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            embeddings = [item.embedding for item in response.data]

            # Validate dimensions and null vectors
            for i, emb in enumerate(embeddings):
                if len(emb) != self._dimensions:
                    raise EmbeddingError(
                        f"Embedding {i} has {len(emb)} dimensions, "
                        f"expected {self._dimensions}"
                    )
                if all(v == 0.0 for v in emb):
                    raise EmbeddingError(f"Embedding {i} is a null vector")

            await logger.ainfo(
                "Embeddings generated",
                texts_count=len(texts),
                model=self._model,
                usage_tokens=response.usage.total_tokens if response.usage else None,
            )
            return embeddings

        except AuthenticationError as e:
            await logger.aerror("OpenAI authentication failed", error=str(e))
            raise EmbeddingError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            await logger.awarning("OpenAI rate limit hit", error=str(e))
            raise EmbeddingError(f"Rate limit exceeded: {e}") from e
        except APIError as e:
            await logger.aerror(
                "OpenAI API error", error=str(e), status_code=getattr(e, "status_code", None)
            )
            raise EmbeddingError(f"API error: {e}") from e

    async def generate_single_embedding(self, text: str) -> list[float]:
        """Convenience wrapper for generating a single embedding."""
        results = await self.generate_embeddings([text])
        return results[0]
