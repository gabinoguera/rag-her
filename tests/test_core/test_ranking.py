import uuid
from datetime import UTC, datetime, timedelta

from app.core.ranking import (
    ScoredResult,
    calculate_final_score,
    deduplicate_results,
    recency_score,
)


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


class TestCalculateFinalScore:
    def test_calculate_final_score_weights(self) -> None:
        result = calculate_final_score(similarity=1.0, recency=1.0)
        assert result == 1.0

    def test_calculate_final_score_similarity_weight(self) -> None:
        result = calculate_final_score(similarity=1.0, recency=0.0)
        assert abs(result - 0.70) < 0.001

    def test_calculate_final_score_recency_weight(self) -> None:
        result = calculate_final_score(similarity=0.0, recency=1.0)
        assert abs(result - 0.30) < 0.001

    def test_zero_scores_equal_zero(self) -> None:
        result = calculate_final_score(similarity=0.0, recency=0.0)
        assert result == 0.0

    def test_partial_scores_combine_correctly(self) -> None:
        # 0.70 * 0.8 + 0.30 * 0.6 = 0.56 + 0.18 = 0.74
        result = calculate_final_score(similarity=0.8, recency=0.6)
        assert abs(result - 0.74) < 0.001


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
