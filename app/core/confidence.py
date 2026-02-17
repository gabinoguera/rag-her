from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class ChunkLike(Protocol):
    similarity_score: float
    technologies: list[str] | None
    total_cost: float | None


@dataclass
class ConfidenceFactors:
    references_count: int
    references_factor: float
    avg_similarity: float
    similarity_factor: float
    technology_match: float
    technology_factor: float
    cost_variance: float
    variance_factor: float


@dataclass
class ConfidenceResult:
    score: float
    level: str
    factors: ConfidenceFactors


def _references_factor(count: int) -> float:
    if count == 0:
        return 0.0
    if count <= 2:
        return 0.3
    if count <= 5:
        return 0.6
    if count <= 10:
        return 0.8
    return 1.0


def _similarity_factor(chunks: list[ChunkLike]) -> tuple[float, float]:
    """Return (avg_similarity, factor)."""
    if not chunks:
        return 0.0, 0.0
    scores = [c.similarity_score for c in chunks]
    avg = statistics.mean(scores)
    factor = max(0.0, (avg - 0.5) / 0.5)
    return avg, factor


def _technology_factor(
    chunks: list[ChunkLike], query_techs: list[str] | None
) -> tuple[float, float]:
    """Return (match_ratio, factor)."""
    if not query_techs:
        return 0.5, 0.5
    all_chunk_techs: set[str] = set()
    for c in chunks:
        if c.technologies:
            all_chunk_techs.update(c.technologies)
    if not all_chunk_techs:
        return 0.0, 0.0
    query_set = set(query_techs)
    match_ratio = len(query_set & all_chunk_techs) / len(query_set)
    return match_ratio, match_ratio


def _variance_factor(chunks: list[ChunkLike]) -> tuple[float, float]:
    """Return (cv, factor)."""
    costs = [c.total_cost for c in chunks if c.total_cost is not None]
    if len(costs) < 2:
        return 0.0, 0.3
    mean_cost = statistics.mean(costs)
    if mean_cost == 0:
        return 0.0, 0.5
    cv = statistics.stdev(costs) / mean_cost
    factor = max(0.0, 1.0 - cv)
    return cv, factor


def _score_to_level(score: float) -> str:
    if score < 0.3:
        return "very_low"
    if score < 0.5:
        return "low"
    if score < 0.7:
        return "medium"
    if score < 0.85:
        return "high"
    return "very_high"


def calculate_confidence(
    chunks: list[ChunkLike],
    query_technologies: list[str] | None = None,
) -> ConfidenceResult:
    ref_factor = _references_factor(len(chunks))
    avg_sim, sim_factor = _similarity_factor(chunks)
    tech_match, tech_factor = _technology_factor(chunks, query_technologies)
    cv, var_factor = _variance_factor(chunks)

    score = (
        ref_factor * 0.35
        + sim_factor * 0.30
        + tech_factor * 0.20
        + var_factor * 0.15
    )
    score = round(score, 2)
    level = _score_to_level(score)

    factors = ConfidenceFactors(
        references_count=len(chunks),
        references_factor=round(ref_factor, 4),
        avg_similarity=round(avg_sim, 4),
        similarity_factor=round(sim_factor, 4),
        technology_match=round(tech_match, 4),
        technology_factor=round(tech_factor, 4),
        cost_variance=round(cv, 4),
        variance_factor=round(var_factor, 4),
    )

    return ConfidenceResult(score=score, level=level, factors=factors)
