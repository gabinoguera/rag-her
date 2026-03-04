from __future__ import annotations

import asyncio
import statistics
from typing import Any

import structlog
from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from app.core.prompt_builder import RESPONSE_JSON_SCHEMA, build_estimation_prompt, build_validation_prompt
from app.core.response_parser import (
    LLMEstimationResponse,
    LLMValidationResponse,
    ParseError,
    parse_llm_response,
    parse_validation_response,
)

logger = structlog.stdlib.get_logger()


class GenerationError(Exception):
    """Raised when LLM generation fails."""


CORRECTION_PROMPT = (
    "Tu respuesta anterior no fue un JSON válido. Por favor responde ÚNICAMENTE "
    "con el JSON, sin texto adicional, sin bloques de código markdown, sin "
    "explicaciones. Solo el JSON siguiendo este schema:\n"
    f"{RESPONSE_JSON_SCHEMA}"
)


class GenerationService:
    """Service for generating estimations using OpenAI LLM."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_output_tokens: int = 16384,
        timeout: int = 120,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=0)
        self._model = model
        self._max_output_tokens = max_output_tokens

    async def generate_estimation(
        self,
        query: str,
        context: Any | None,
        chunks: list[Any],
        currency: str = "EUR",
    ) -> tuple[LLMEstimationResponse, int]:
        """Generate an estimation. Returns (response, chunks_used_count)."""
        system_prompt, user_prompt, chunks_used = build_estimation_prompt(
            query, context, chunks, currency
        )

        try:
            raw = await self._call_llm_with_retries(system_prompt, user_prompt)
        except GenerationError:
            await logger.awarning("LLM call failed, using fallback estimation")
            return self.build_fallback_estimation(chunks, currency), chunks_used

        try:
            parsed = parse_llm_response(raw, currency)
            return parsed, chunks_used
        except ParseError:
            await logger.awarning("Parse failed, retrying with correction prompt")
            correction_user = f"{user_prompt}\n\n---\nTu respuesta anterior:\n{raw}\n\n---\n{CORRECTION_PROMPT}"
            try:
                raw_retry = await self._call_llm_with_retries(system_prompt, correction_user)
                parsed = parse_llm_response(raw_retry, currency)
                return parsed, chunks_used
            except (ParseError, GenerationError):
                await logger.awarning("Correction retry failed, using fallback")
                return self.build_fallback_estimation(chunks, currency), chunks_used

    async def _call_llm_with_retries(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM with retry logic per error type."""
        try:
            return await self._call_llm(system_prompt, user_prompt)
        except AuthenticationError as e:
            await logger.aerror("OpenAI authentication failed", error=str(e))
            raise GenerationError(f"Authentication failed: {e}") from e
        except RateLimitError as e:
            # Retry with exponential backoff: 2s, 4s, 8s
            for attempt, delay in enumerate([2, 4, 8], 1):
                await logger.awarning(
                    "Rate limited, retrying", attempt=attempt, delay=delay
                )
                await asyncio.sleep(delay)
                try:
                    return await self._call_llm(system_prompt, user_prompt)
                except RateLimitError:
                    continue
                except AuthenticationError as auth_e:
                    raise GenerationError(f"Authentication failed: {auth_e}") from auth_e
            raise GenerationError(f"Rate limit exceeded after 3 retries: {e}") from e
        except APITimeoutError as e:
            # 1 retry
            await logger.awarning("LLM timeout, retrying once")
            try:
                return await self._call_llm(system_prompt, user_prompt)
            except (APITimeoutError, APIError) as retry_e:
                raise GenerationError(f"LLM timeout after retry: {retry_e}") from retry_e
        except APIError as e:
            status = getattr(e, "status_code", None)
            if status and status >= 500:
                # 2 retries for server errors
                for attempt in range(1, 3):
                    await logger.awarning(
                        "Server error, retrying", attempt=attempt, status=status
                    )
                    try:
                        return await self._call_llm(system_prompt, user_prompt)
                    except APIError:
                        continue
            raise GenerationError(f"API error: {e}") from e

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Single LLM call using Responses API."""
        response = await self._client.responses.create(
            model=self._model,
            instructions=system_prompt,
            input=[{"role": "user", "content": user_prompt}],
            max_output_tokens=self._max_output_tokens,
        )
        content = response.output_text
        if not content:
            raise GenerationError("Empty response from LLM")
        return content

    async def validate_estimation(
        self,
        original_breakdown: list[Any],
        task_references: list[Any],
        original_effort: dict,
        currency: str = "EUR",
    ) -> LLMValidationResponse | None:
        """Second-pass: validate hours using per-task historical references.

        Returns None if validation fails (caller should use original estimation).
        """
        system_prompt, user_prompt = build_validation_prompt(
            original_breakdown, task_references, original_effort, currency
        )

        try:
            raw = await self._call_llm_with_retries(system_prompt, user_prompt)
        except GenerationError:
            await logger.awarning("Validation LLM call failed, returning original")
            return None

        try:
            return parse_validation_response(raw, currency)
        except ParseError:
            await logger.awarning("Validation parse failed, returning original")
            return None

    @staticmethod
    def build_fallback_estimation(
        chunks: list[Any], currency: str = "EUR"
    ) -> LLMEstimationResponse:
        """Build a degraded estimation from chunk statistics."""
        costs = [c.total_cost for c in chunks if getattr(c, "total_cost", None)]

        if costs:
            median_cost = statistics.median(costs)
        else:
            median_cost = 0.0

        # Estimate hours from costs using a rough hourly rate
        meta_prices = []
        for c in chunks:
            meta = getattr(c, "metadata", None) or {}
            if isinstance(meta, dict):
                up = meta.get("unit_price")
                if up and float(up) > 0:
                    meta_prices.append(float(up))

        if meta_prices:
            daily_rate = statistics.median(meta_prices)
        else:
            daily_rate = 350.0  # fallback default

        expected_days = max(1, round(median_cost / daily_rate)) if daily_rate > 0 else 1
        expected_hours = expected_days * 8
        optimistic_hours = max(8, round(expected_hours * 0.7))
        pessimistic_hours = max(expected_hours + 8, round(expected_hours * 1.5))

        # Ensure strict ordering
        if optimistic_hours >= expected_hours:
            optimistic_hours = max(8, expected_hours - 8)
        if pessimistic_hours <= expected_hours:
            pessimistic_hours = expected_hours + 8

        all_techs: set[str] = set()
        for c in chunks:
            if getattr(c, "technologies", None):
                all_techs.update(c.technologies)

        return LLMEstimationResponse(
            summary="Estimación degradada generada a partir de datos estadísticos (el LLM no respondió correctamente).",
            estimated_effort={
                "optimistic": {"hours": optimistic_hours},
                "expected": {"hours": expected_hours},
                "pessimistic": {"hours": pessimistic_hours},
            },
            suggested_breakdown=[
                {
                    "name": "General",
                    "tasks": [
                        {"name": "Estimación general (fallback)", "hours": expected_hours},
                    ],
                }
            ],
            suggested_technologies=sorted(all_techs),
            notes="Esta estimación fue generada mediante cálculo estadístico directo (fallback). "
            "El modelo LLM no pudo generar una respuesta válida. La confianza es muy baja.",
        )
