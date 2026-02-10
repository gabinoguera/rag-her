import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.ranking import (
    ScoredResult,
    calculate_final_score,
    cost_range_score,
    deduplicate_results,
    recency_score,
    technology_match_score,
)


class TestTechnologyMatchScore:
    def test_perfect_match(self) -> None:
        score = technology_match_score(["React", "Node.js"], ["React", "Node.js"])
        assert score == 1.0

    def test_partial_match(self) -> None:
        score = technology_match_score(
            ["React", "Node.js", "PostgreSQL"], ["React", "Vue.js"]
        )
        assert 0.0 < score < 1.0

    def test_no_match(self) -> None:
        score = technology_match_score(["React"], ["Django"])
        assert score == 0.0

    def test_empty_query_techs_returns_neutral(self) -> None:
        score = technology_match_score(["React"], [])
        assert score == 0.5

    def test_none_query_techs_returns_neutral(self) -> None:
        score = technology_match_score(["React"], None)
        assert score == 0.5

    def test_empty_chunk_techs_returns_zero(self) -> None:
        score = technology_match_score([], ["React"])
        assert score == 0.0


class TestRecencyScore:
    def test_recent_is_high(self) -> None:
        now = datetime.now(UTC)
        score = recency_score(now - timedelta(days=7), now)
        assert score > 0.9

    def test_old_is_lower(self) -> None:
        now = datetime.now(UTC)
        score = recency_score(now - timedelta(days=365), now)
        assert score < 0.7

    def test_very_old_below_threshold(self) -> None:
        now = datetime.now(UTC)
        # ~4.5 years -> ~54 months -> exp(-0.03*54) ≈ 0.20
        score = recency_score(now - timedelta(days=1700), now)
        assert score < 0.2


class TestCostRangeScore:
    def test_normal_value(self) -> None:
        costs = [100.0, 110.0, 105.0, 95.0, 108.0]
        score = cost_range_score(105.0, costs)
        assert score == 1.0

    def test_severe_outlier(self) -> None:
        costs = [100.0, 110.0, 105.0, 95.0, 500.0]
        score = cost_range_score(500.0, costs)
        assert score == 0.2

    def test_none_cost_returns_neutral(self) -> None:
        costs = [100.0, 200.0, 300.0]
        score = cost_range_score(None, costs)
        assert score == 0.5

    def test_fewer_than_3_returns_neutral(self) -> None:
        costs = [100.0, 200.0]
        score = cost_range_score(150.0, costs)
        assert score == 0.5


class TestCalculateFinalScore:
    def test_perfect_scores_equal_one(self) -> None:
        score = calculate_final_score(
            similarity=1.0, tech_match=1.0, recency=1.0, cost_range=1.0
        )
        assert abs(score - 1.0) < 1e-9

    def test_weights_are_correct(self) -> None:
        # Only similarity=1.0, rest=0.0
        score = calculate_final_score(
            similarity=1.0, tech_match=0.0, recency=0.0, cost_range=0.0
        )
        assert abs(score - 0.50) < 1e-9

        # Only tech=1.0
        score = calculate_final_score(
            similarity=0.0, tech_match=1.0, recency=0.0, cost_range=0.0
        )
        assert abs(score - 0.25) < 1e-9


class TestDeduplicateResults:
    def _make_result(
        self,
        doc_id: uuid.UUID,
        chunk_type: str,
        final_score: float,
    ) -> ScoredResult:
        return ScoredResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            chunk_type=chunk_type,
            content_text="test",
            metadata=None,
            project_title="Test",
            technologies=None,
            total_cost=None,
            currency=None,
            created_at=datetime.now(UTC),
            similarity_score=0.9,
            final_score=final_score,
        )

    def test_same_doc_and_type_keeps_highest(self) -> None:
        doc_id = uuid.uuid4()
        results = [
            self._make_result(doc_id, "scope_block", 0.7),
            self._make_result(doc_id, "scope_block", 0.9),
        ]
        deduped = deduplicate_results(results)
        assert len(deduped) == 1
        assert deduped[0].final_score == 0.9

    def test_different_types_keeps_both(self) -> None:
        doc_id = uuid.uuid4()
        results = [
            self._make_result(doc_id, "scope_block", 0.8),
            self._make_result(doc_id, "line_item", 0.7),
        ]
        deduped = deduplicate_results(results)
        assert len(deduped) == 2

    def test_result_sorted_by_score_desc(self) -> None:
        doc1 = uuid.uuid4()
        doc2 = uuid.uuid4()
        results = [
            self._make_result(doc1, "scope_block", 0.5),
            self._make_result(doc2, "scope_block", 0.9),
        ]
        deduped = deduplicate_results(results)
        assert deduped[0].final_score > deduped[1].final_score
