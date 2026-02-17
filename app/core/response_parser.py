from __future__ import annotations

import json
import re

import structlog
from pydantic import BaseModel, Field

logger = structlog.stdlib.get_logger()


class ParseError(Exception):
    """Raised when the LLM response cannot be parsed."""


class LLMEffortEstimate(BaseModel):
    days: int = Field(gt=0)
    hours: int = Field(gt=0)


class LLMCostEstimate(BaseModel):
    amount: float = Field(gt=0)
    currency: str


class LLMBreakdownItem(BaseModel):
    name: str
    days: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    total: float = Field(gt=0)


class LLMEstimationResponse(BaseModel):
    summary: str
    estimated_effort: dict[str, LLMEffortEstimate]
    estimated_cost: dict[str, LLMCostEstimate]
    suggested_unit_price: dict
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

    # Fix effort ordering: optimistic < expected < pessimistic
    effort = data.get("estimated_effort", {})
    scenarios = ["optimistic", "expected", "pessimistic"]
    effort_days = []
    for s in scenarios:
        if s in effort and isinstance(effort[s], dict):
            effort_days.append(effort[s].get("days", 0))
        else:
            effort_days.append(0)

    sorted_days = sorted(effort_days)
    if effort_days != sorted_days:
        warnings.append("Reordered effort scenarios (optimistic < expected < pessimistic)")
        for s, d in zip(scenarios, sorted_days):
            if s in effort:
                effort[s]["days"] = d

    # Recalculate hours = days * 8
    for s in scenarios:
        if s in effort and isinstance(effort[s], dict):
            days = effort[s].get("days", 0)
            expected_hours = days * 8
            if effort[s].get("hours") != expected_hours:
                effort[s]["hours"] = expected_hours

    # Fix cost ordering: optimistic < expected < pessimistic
    cost = data.get("estimated_cost", {})
    cost_amounts = []
    for s in scenarios:
        if s in cost and isinstance(cost[s], dict):
            cost_amounts.append(cost[s].get("amount", 0))
        else:
            cost_amounts.append(0)

    sorted_costs = sorted(cost_amounts)
    if cost_amounts != sorted_costs:
        warnings.append("Reordered cost scenarios (optimistic < expected < pessimistic)")
        for s, a in zip(scenarios, sorted_costs):
            if s in cost:
                cost[s]["amount"] = a

    # Fix currency
    for s in scenarios:
        if s in cost and isinstance(cost[s], dict):
            cost[s]["currency"] = currency

    # Check breakdown total vs expected cost (±10%)
    breakdown = data.get("suggested_breakdown", [])
    if breakdown and "expected" in cost:
        breakdown_total = sum(item.get("total", 0) for item in breakdown)
        expected_amount = cost["expected"].get("amount", 0)
        if expected_amount > 0:
            diff_pct = abs(breakdown_total - expected_amount) / expected_amount
            if diff_pct > 0.10:
                warnings.append(
                    f"Breakdown total ({breakdown_total}) differs from expected cost "
                    f"({expected_amount}) by {diff_pct:.0%}"
                )

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
