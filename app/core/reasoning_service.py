"""Service wrapping OpenAI reasoning models (o4-mini) with Structured Output.

Uses the Responses API (client.responses.parse) with:
- instructions parameter for system/developer prompt
- input parameter for user messages
- text_format for Pydantic Structured Output
- max_output_tokens instead of max_completion_tokens
- No temperature parameter (not supported by o4-mini)
- Longer timeout (120s) for internal chain-of-thought reasoning
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from app.api.schemas.quote_output import QuoteOutput
from app.api.schemas.transcription_analysis import TranscriptionAnalysis
from app.core.quote_prompt_builder import (
    ANALYSIS_PROMPT,
    GENERATION_PROMPT,
    build_analysis_user_prompt,
    build_generation_user_prompt,
)

logger = structlog.stdlib.get_logger()


class ReasoningError(Exception):
    """Raised when reasoning model call fails."""


class ReasoningService:
    """Wraps o4-mini with Structured Output for transcription analysis and quote generation."""

    def __init__(
        self,
        api_key: str,
        model: str = "o4-mini",
        max_output_tokens: int = 16384,
        timeout: int = 120,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=2,
        )
        self._model = model
        self._max_output_tokens = max_output_tokens

    async def analyze_transcription(
        self,
        transcription: str,
        context: Any | None = None,
    ) -> tuple[TranscriptionAnalysis, int]:
        """Step 1: Analyze transcription and extract structured requirements.

        Returns (analysis, total_tokens_used).
        """
        user_prompt = build_analysis_user_prompt(transcription, context)

        response = await self._call_with_retries(
            instructions=ANALYSIS_PROMPT,
            user_content=user_prompt,
            text_format=TranscriptionAnalysis,
        )

        parsed = response.output_parsed
        if parsed is None:
            raise ReasoningError(
                "Reasoning model returned empty parsed result for analysis"
            )

        total_tokens = response.usage.total_tokens if response.usage else 0
        return parsed, total_tokens

    async def generate_quote(
        self,
        analysis: TranscriptionAnalysis,
        rag_chunks: list[Any],
        currency: str = "EUR",
        context: Any | None = None,
    ) -> tuple[QuoteOutput, int]:
        """Step 3: Generate a detailed QuoteOutput from analysis + RAG context.

        Returns (quote, total_tokens_used).
        """
        user_prompt = build_generation_user_prompt(
            analysis, rag_chunks, currency, context
        )

        response = await self._call_with_retries(
            instructions=GENERATION_PROMPT,
            user_content=user_prompt,
            text_format=QuoteOutput,
        )

        parsed = response.output_parsed
        if parsed is None:
            raise ReasoningError(
                "Reasoning model returned empty parsed result for quote generation"
            )

        total_tokens = response.usage.total_tokens if response.usage else 0
        return parsed, total_tokens

    async def _call_with_retries(
        self,
        instructions: str,
        user_content: str,
        text_format: type,
    ) -> Any:
        """Call the reasoning model with retry logic."""
        try:
            return await self._call_parse(instructions, user_content, text_format)
        except AuthenticationError as e:
            await logger.aerror("OpenAI authentication failed", error=str(e))
            raise ReasoningError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            for attempt, delay in enumerate([2, 4, 8], 1):
                await logger.awarning(
                    "Rate limited, retrying",
                    attempt=attempt,
                    delay=delay,
                    model=self._model,
                )
                await asyncio.sleep(delay)
                try:
                    return await self._call_parse(instructions, user_content, text_format)
                except RateLimitError:
                    continue
                except AuthenticationError as auth_e:
                    raise ReasoningError(
                        f"Authentication failed: {auth_e}"
                    ) from auth_e
            raise ReasoningError(
                f"Rate limit exceeded after 3 retries: {e}"
            ) from e
        except APITimeoutError as e:
            await logger.awarning(
                "Reasoning model timeout, retrying once", model=self._model
            )
            try:
                return await self._call_parse(instructions, user_content, text_format)
            except (APITimeoutError, APIError) as retry_e:
                raise ReasoningError(
                    f"Reasoning model timeout after retry: {retry_e}"
                ) from retry_e
        except APIError as e:
            status = getattr(e, "status_code", None)
            if status and status >= 500:
                for attempt in range(1, 3):
                    await logger.awarning(
                        "Server error, retrying",
                        attempt=attempt,
                        status=status,
                        model=self._model,
                    )
                    try:
                        return await self._call_parse(instructions, user_content, text_format)
                    except APIError:
                        continue
            raise ReasoningError(f"API error: {e}") from e

    async def _call_parse(
        self,
        instructions: str,
        user_content: str,
        text_format: type,
    ) -> Any:
        """Single call using Responses API .parse() with Structured Output."""
        response = await self._client.responses.parse(
            model=self._model,
            instructions=instructions,
            input=[{"role": "user", "content": user_content}],
            text_format=text_format,
            max_output_tokens=self._max_output_tokens,
        )

        return response
