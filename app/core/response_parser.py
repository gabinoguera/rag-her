from __future__ import annotations

import json
import re

import structlog
from pydantic import BaseModel, Field

logger = structlog.stdlib.get_logger()


class ParseError(Exception):
    """Raised when the LLM response cannot be parsed."""


class LLMEffortEstimate(BaseModel):
    hours: int = Field(gt=0)


class LLMBreakdownTask(BaseModel):
    name: str
    hours: int = Field(gt=0)


class LLMBreakdownItem(BaseModel):
    name: str
    tasks: list[LLMBreakdownTask] = Field(min_length=1)


class LLMEstimationResponse(BaseModel):
    summary: str
    estimated_effort: dict[str, LLMEffortEstimate]
    suggested_breakdown: list[LLMBreakdownItem]
    suggested_technologies: list[str]
    notes: str


def _extract_json(raw: str) -> str:
    """Extract JSON from the raw LLM response."""
    # Try ```json ... ``` block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try outermost { ... }
    first_brace = raw.find("{")
    if first_brace == -1:
        raise ParseError("No JSON object found in response")

    depth = 0
    last_brace = -1
    for i in range(first_brace, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                last_brace = i
                break

    if last_brace == -1:
        raise ParseError("Unmatched braces in JSON response")

    return raw[first_brace : last_brace + 1]


def _fix_coherence(data: dict, currency: str) -> list[str]:
    """Fix coherence issues in-place. Return list of warnings."""
    warnings: list[str] = []

    # Fix effort ordering: optimistic < expected < pessimistic (hours only)
    effort = data.get("estimated_effort", {})
    scenarios = ["optimistic", "expected", "pessimistic"]
    effort_hours = []
    for s in scenarios:
        if s in effort and isinstance(effort[s], dict):
            effort_hours.append(effort[s].get("hours", 0))
        else:
            effort_hours.append(0)

    sorted_hours = sorted(effort_hours)
    if effort_hours != sorted_hours:
        warnings.append("Reordered effort scenarios (optimistic < expected < pessimistic)")
        for s, h in zip(scenarios, sorted_hours):
            if s in effort:
                effort[s]["hours"] = h

    return warnings


def parse_llm_response(raw: str, currency: str = "EUR") -> LLMEstimationResponse:
    """Parse and validate the LLM response."""
    json_str = _extract_json(raw)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ParseError("Expected a JSON object at top level")

    warnings = _fix_coherence(data, currency)
    for w in warnings:
        logger.warning("Coherence fix applied", warning=w)

    try:
        return LLMEstimationResponse.model_validate(data)
    except Exception as e:
        raise ParseError(f"Validation failed: {e}") from e
