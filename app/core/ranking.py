from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


def recency_score(created_at: datetime, now: datetime | None = None) -> float:
    """Exponential decay based on age in months.

    Formula: exp(-0.03 * age_months)
    """
    if now is None:
        now = datetime.now(UTC)

    delta = now - created_at
    age_months = delta.days / 30.44  # average days per month

    return math.exp(-0.03 * age_months)


def calculate_final_score(similarity: float, recency: float) -> float:
    """Weighted composite score.

    Weights: similarity 0.70, recency 0.30
    """
    return 0.70 * similarity + 0.30 * recency


@dataclass
class ScoredResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_type: str
    content_text: str
    metadata: dict | None
    project_title: str | None
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
