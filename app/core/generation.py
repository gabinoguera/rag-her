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

from app.core.prompt_builder import RESPONSE_JSON_SCHEMA, build_estimation_prompt
from app.core.response_parser import LLMEstimationResponse, ParseError, parse_llm_response

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
        max_tokens: int = 4096,
        temperature: float = 0.2,
        timeout: int = 30,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=0)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw = await self._call_llm_with_retries(messages)
        except GenerationError:
            await logger.awarning("LLM call failed, using fallback estimation")
            return self.build_fallback_estimation(chunks, currency), chunks_used

        try:
            parsed = parse_llm_response(raw, currency)
            return parsed, chunks_used
        except ParseError:
            await logger.awarning("Parse failed, retrying with correction prompt")
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": CORRECTION_PROMPT})
            try:
                raw_retry = await self._call_llm_with_retries(messages)
                parsed = parse_llm_response(raw_retry, currency)
                return parsed, chunks_used
            except (ParseError, GenerationError):
                await logger.awarning("Correction retry failed, using fallback")
                return self.build_fallback_estimation(chunks, currency), chunks_used

    async def _call_llm_with_retries(self, messages: list[dict]) -> str:
        """Call the LLM with retry logic per error type."""
        try:
            return await self._call_llm(messages)
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
                    return await self._call_llm(messages)
                except RateLimitError:
                    continue
                except AuthenticationError as auth_e:
                    raise GenerationError(f"Authentication failed: {auth_e}") from auth_e
            raise GenerationError(f"Rate limit exceeded after 3 retries: {e}") from e
        except APITimeoutError as e:
            # 1 retry
            await logger.awarning("LLM timeout, retrying once")
            try:
                return await self._call_llm(messages)
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
                        return await self._call_llm(messages)
                    except APIError:
                        continue
            raise GenerationError(f"API error: {e}") from e

    async def _call_llm(self, messages: list[dict]) -> str:
        """Single LLM call."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise GenerationError("Empty response from LLM")
        return content

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

        # Estimate days from costs using a rough unit price
        meta_prices = []
        for c in chunks:
            meta = getattr(c, "metadata", None) or {}
            if isinstance(meta, dict):
                up = meta.get("unit_price")
                if up and float(up) > 0:
                    meta_prices.append(float(up))

        if meta_prices:
            unit_price = statistics.median(meta_prices)
        else:
            unit_price = 350.0  # fallback default

        expected_days = max(1, round(median_cost / unit_price)) if unit_price > 0 else 1
        optimistic_days = max(1, round(expected_days * 0.7))
        pessimistic_days = max(expected_days + 1, round(expected_days * 1.5))

        # Ensure strict ordering
        if optimistic_days >= expected_days:
            optimistic_days = max(1, expected_days - 1)
        if pessimistic_days <= expected_days:
            pessimistic_days = expected_days + 1

        all_techs: set[str] = set()
        for c in chunks:
            if getattr(c, "technologies", None):
                all_techs.update(c.technologies)

        return LLMEstimationResponse(
            summary="Estimación degradada generada a partir de datos estadísticos (el LLM no respondió correctamente).",
            estimated_effort={
                "optimistic": {"days": optimistic_days, "hours": optimistic_days * 8},
                "expected": {"days": expected_days, "hours": expected_days * 8},
                "pessimistic": {"days": pessimistic_days, "hours": pessimistic_days * 8},
            },
            estimated_cost={
                "optimistic": {"amount": round(optimistic_days * unit_price, 2), "currency": currency},
                "expected": {"amount": round(expected_days * unit_price, 2), "currency": currency},
                "pessimistic": {"amount": round(pessimistic_days * unit_price, 2), "currency": currency},
            },
            suggested_unit_price={
                "amount": unit_price,
                "unit": "día",
                "currency": currency,
                "basis": "Mediana de precios unitarios en referencias históricas (fallback estadístico)",
            },
            suggested_breakdown=[
                {
                    "name": "Estimación general (fallback)",
                    "days": expected_days,
                    "unit_price": unit_price,
                    "total": round(expected_days * unit_price, 2),
                }
            ],
            suggested_technologies=sorted(all_techs),
            notes="Esta estimación fue generada mediante cálculo estadístico directo (fallback). "
            "El modelo LLM no pudo generar una respuesta válida. La confianza es muy baja.",
        )
