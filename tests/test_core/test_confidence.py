from dataclasses import dataclass

from app.core.confidence import (
    _references_factor,
    _score_to_level,
    calculate_confidence,
)


@dataclass
class FakeChunk:
    similarity_score: float
    technologies: list[str] | None = None
    total_cost: float | None = None


class TestConfidence:
    def test_no_references(self) -> None:
        result = calculate_confidence([], query_technologies=["React"])
        # variance_factor defaults to 0.3 with no data -> 0.3*0.15 = 0.045 ~ 0.04
        assert result.score < 0.1
        assert result.level == "very_low"
        assert result.factors.references_count == 0

    def test_few_references(self) -> None:
        chunks = [
            FakeChunk(similarity_score=0.7, technologies=["React"], total_cost=1000),
            FakeChunk(similarity_score=0.65, technologies=["Node.js"], total_cost=1200),
        ]
        result = calculate_confidence(chunks, query_technologies=["React"])
        # 2 chunks -> ref_factor 0.3, with some tech match and similarity
        assert result.score > 0
        assert result.score < 0.85
        assert result.factors.references_count == 2

    def test_many_high_similarity(self) -> None:
        chunks = [
            FakeChunk(
                similarity_score=0.85,
                technologies=["React", "Node.js"],
                total_cost=1000 + i * 50,
            )
            for i in range(8)
        ]
        result = calculate_confidence(
            chunks, query_technologies=["React", "Node.js"]
        )
        assert result.score > 0.7
        assert result.level in ("high", "very_high")

    def test_low_similarity(self) -> None:
        chunks = [
            FakeChunk(similarity_score=0.55, technologies=["Python"], total_cost=500)
            for _ in range(5)
        ]
        result = calculate_confidence(chunks, query_technologies=["Python"])
        # sim factor = (0.55 - 0.5) / 0.5 = 0.1 -> low contribution
        assert result.score < 0.7

    def test_high_variance(self) -> None:
        chunks = [
            FakeChunk(similarity_score=0.8, technologies=["Python"], total_cost=100),
            FakeChunk(similarity_score=0.8, technologies=["Python"], total_cost=200),
            FakeChunk(similarity_score=0.8, technologies=["Python"], total_cost=10000),
        ]
        result = calculate_confidence(chunks, query_technologies=["Python"])
        assert result.factors.variance_factor < 0.5

    def test_level_thresholds(self) -> None:
        assert _score_to_level(0.0) == "very_low"
        assert _score_to_level(0.29) == "very_low"
        assert _score_to_level(0.3) == "low"
        assert _score_to_level(0.49) == "low"
        assert _score_to_level(0.5) == "medium"
        assert _score_to_level(0.69) == "medium"
        assert _score_to_level(0.7) == "high"
        assert _score_to_level(0.84) == "high"
        assert _score_to_level(0.85) == "very_high"
        assert _score_to_level(1.0) == "very_high"

    def test_weights_sum_to_one(self) -> None:
        # All factors at 1.0 should produce score 1.0
        chunks = [
            FakeChunk(
                similarity_score=1.0,
                technologies=["React"],
                total_cost=1000,
            )
            for _ in range(15)
        ]
        result = calculate_confidence(chunks, query_technologies=["React"])
        # ref=1.0*0.35 + sim=1.0*0.30 + tech=1.0*0.20 + var=1.0*0.15 = 1.0
        assert result.score == 1.0
