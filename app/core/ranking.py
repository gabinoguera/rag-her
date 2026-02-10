from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median


def technology_match_score(
    chunk_techs: list[str] | None, query_techs: list[str] | None
) -> float:
    """Jaccard similarity between chunk and query technologies.

    Returns 0.5 (neutral) if query_techs is empty/None.
    Returns 0.0 if chunk has no technologies but query does.
    """
    if not query_techs:
        return 0.5

    if not chunk_techs:
        return 0.0

    chunk_set = {t.lower() for t in chunk_techs}
    query_set = {t.lower() for t in query_techs}
    intersection = chunk_set & query_set
    union = chunk_set | query_set

    if not union:
        return 0.5

    return len(intersection) / len(union)


def recency_score(created_at: datetime, now: datetime | None = None) -> float:
    """Exponential decay based on age in months.

    Formula: exp(-0.03 * age_months)
    """
    if now is None:
        now = datetime.now(UTC)

    delta = now - created_at
    age_months = delta.days / 30.44  # average days per month

    return math.exp(-0.03 * age_months)


def cost_range_score(
    chunk_cost: Decimal | float | None,
    all_costs: list[Decimal | float],
) -> float:
    """MAD-based outlier scoring.

    Returns 1.0 for normal values, 0.6 for mild outliers (>1 MAD),
    0.2 for severe outliers (>2 MAD).
    Returns 0.5 (neutral) if fewer than 3 data points or cost is None.
    """
    if chunk_cost is None:
        return 0.5

    valid_costs = [float(c) for c in all_costs if c is not None]
    if len(valid_costs) < 3:
        return 0.5

    med = median(valid_costs)
    absolute_deviations = [abs(c - med) for c in valid_costs]
    mad = median(absolute_deviations)

    if mad == 0:
        return 1.0

    deviation = abs(float(chunk_cost) - med) / mad

    if deviation > 2:
        return 0.2
    if deviation > 1:
        return 0.6
    return 1.0


def calculate_final_score(
    similarity: float,
    tech_match: float,
    recency: float,
    cost_range: float,
) -> float:
    """Weighted composite score.

    Weights: similarity 0.50, tech_match 0.25, recency 0.15, cost_range 0.10
    """
    return (
        0.50 * similarity
        + 0.25 * tech_match
        + 0.15 * recency
        + 0.10 * cost_range
    )


@dataclass
class ScoredResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_type: str
    content_text: str
    metadata: dict | None
    project_title: str | None
    technologies: list[str] | None
    total_cost: Decimal | None
    currency: str | None
    created_at: datetime
    similarity_score: float
    final_score: float


def deduplicate_results(results: list[ScoredResult]) -> list[ScoredResult]:
    """Remove duplicates by (document_id, chunk_type), keeping highest final_score."""
    best: dict[tuple[uuid.UUID, str], ScoredResult] = {}

    for result in results:
        key = (result.document_id, result.chunk_type)
        if key not in best or result.final_score > best[key].final_score:
            best[key] = result

    # Return sorted by final_score descending
    return sorted(best.values(), key=lambda r: r.final_score, reverse=True)
