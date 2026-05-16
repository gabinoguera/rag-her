from __future__ import annotations

import asyncio

import structlog
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

logger = structlog.stdlib.get_logger()


class GenerationError(Exception):
    """Raised when LLM generation fails."""


class GenerationService:
    """Service for generating text using Google Gemini."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        max_output_tokens: int = 8192,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> str:
        """Generate text from a prompt using Gemini.

        Retry strategy:
          ResourceExhausted  -> 4 retries, exponential backoff 2s->4s->8s->16s
          DeadlineExceeded   -> 1 retry, 4s delay
          Unauthenticated    -> fail immediately (no retries)
          other GoogleAPICallError -> fail immediately
        """
        config = types.GenerateContentConfig(
            max_output_tokens=self._max_output_tokens,
            system_instruction=system_instruction,
        )

        # ResourceExhausted: up to 4 retries with exponential backoff
        resource_exhausted_delays = [2, 4, 8, 16]

        last_exception: Exception | None = None

        for attempt in range(5):  # 1 initial + 4 retries
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                text = response.text
                if not text:
                    raise GenerationError("Empty response from model (vacía o None)")
                return text

            except google_exceptions.ResourceExhausted as e:
                last_exception = e
                if attempt < 4:
                    delay = resource_exhausted_delays[attempt]
                    logger.warning(
                        "ResourceExhausted, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                # All retries exhausted
                raise GenerationError(
                    f"ResourceExhausted after {attempt + 1} attempts: {e}"
                ) from e

            except google_exceptions.DeadlineExceeded as e:
                last_exception = e
                if attempt == 0:
                    logger.warning("DeadlineExceeded, retrying once", delay=4)
                    await asyncio.sleep(4)
                    continue
                raise GenerationError(
                    f"DeadlineExceeded after retry: {e}"
                ) from e

            except google_exceptions.Unauthenticated as e:
                raise GenerationError(
                    f"Authentication failed: {e}"
                ) from e

            except google_exceptions.GoogleAPICallError as e:
                raise GenerationError(
                    f"Google API error: {e}"
                ) from e

        # Should not reach here, but guard just in case
        raise GenerationError(
            f"Generation failed after retries: {last_exception}"
        ) from last_exception
