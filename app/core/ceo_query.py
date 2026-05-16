"""CEO RAG query pipeline.

Embeds the CEO's question, retrieves relevant check-in chunks from pgvector,
applies recency+similarity re-ranking, and synthesises a ~80-word answer
using Gemini 2.5 Flash.
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import EmbeddingService
from app.core.generation import GenerationService
from app.core.prompts import CEO_SYNTHESIS_PROMPT, CEO_SYSTEM_INSTRUCTION
from app.core.ranking import calculate_final_score, recency_score

logger = structlog.stdlib.get_logger()

_NO_DATA_ANSWER = (
    "No hay información disponible en los check-ins para responder esta consulta."
)

_RETRIEVAL_SQL = text("""
    SELECT
        cic.id,
        cic.answer_text,
        cic.question_text,
        cic.created_at,
        e.name  AS employee_name,
        ci.started_at,
        1 - (cic.embedding <=> CAST(:q_vec AS vector)) AS similarity
    FROM her.check_in_chunks cic
    JOIN her.check_ins  ci ON ci.id  = cic.checkin_id
    JOIN her.employees  e  ON e.id   = ci.employee_id
    WHERE
        cic.embedding IS NOT NULL
        AND ci.status = 'completed'
        AND 1 - (cic.embedding <=> CAST(:q_vec AS vector)) >= :min_similarity
    ORDER BY cic.embedding <=> CAST(:q_vec AS vector)
    LIMIT :top_k
""")


def _confidence(final_score: float) -> str:
    if final_score >= 0.70:
        return "alta"
    if final_score >= 0.45:
        return "media"
    return "baja"


async def query(
    question: str,
    db: AsyncSession,
    embedding_service: EmbeddingService,
    generation_service: GenerationService,
    top_k: int = 10,
    min_similarity: float = 0.30,
) -> dict:
    """Run the full CEO RAG pipeline.

    Args:
        question: Natural-language question from the CEO.
        db: Async SQLAlchemy session (read-only usage).
        embedding_service: Service to embed the question.
        generation_service: Service to synthesise the answer.
        top_k: Maximum number of chunks to retrieve from pgvector.
        min_similarity: Cosine similarity threshold (0–1).

    Returns:
        dict with keys:
            answer (str): Synthesised response, ~80 words.
            confidence (str): "alta" | "media" | "baja" | "sin_datos".
            sources (list[dict]): Up to 5 items with employee_name, date, excerpt.
    """
    # 1. Embed the question
    q_embedding = await embedding_service.generate_single_embedding(
        question, task_type="RETRIEVAL_QUERY"
    )

    # Convert to pgvector literal string format: '[0.1,0.2,...]'
    q_vec_str = "[" + ",".join(str(v) for v in q_embedding) + "]"

    # 2. Retrieve chunks via pgvector
    result = await db.execute(
        _RETRIEVAL_SQL,
        {"q_vec": q_vec_str, "min_similarity": min_similarity, "top_k": top_k},
    )
    rows = result.mappings().all()

    logger.info("ceo_query_retrieved", question=question[:80], chunk_count=len(rows))

    # 3. Early exit when no data
    if not rows:
        return {
            "answer": _NO_DATA_ANSWER,
            "confidence": "sin_datos",
            "sources": [],
        }

    # 4. Re-rank: recency(0.30) + similarity(0.70)
    scored = [
        (row, calculate_final_score(float(row["similarity"]), recency_score(row["created_at"])))
        for row in rows
    ]
    scored.sort(key=lambda t: t[1], reverse=True)

    # 5. Confidence based on top-1 final score
    top_score = scored[0][1]
    confidence = _confidence(top_score)

    # 6. Build context for Gemini
    context_lines = [
        f"[{row['employee_name']} — {row['started_at'].date()}]: {row['answer_text']}"
        for row, _ in scored
    ]
    context_str = "\n".join(context_lines)
    prompt = CEO_SYNTHESIS_PROMPT.format(context=context_str, question=question)

    # 7. Synthesise answer
    answer = await generation_service.generate(prompt, system_instruction=CEO_SYSTEM_INSTRUCTION)

    # 8. Build sources (max 5, excerpt max 200 chars)
    sources = [
        {
            "employee_name": row["employee_name"],
            "date": row["started_at"].date().isoformat(),
            "excerpt": row["answer_text"][:200],
        }
        for row, _ in scored[:5]
    ]

    logger.info("ceo_query_complete", confidence=confidence, sources_count=len(sources))

    return {
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
    }
