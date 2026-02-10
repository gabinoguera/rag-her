from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.ingest_response import (
    ChunksBreakdown,
    IngestDeleteResponse,
    IngestStatusResponse,
)
from app.api.schemas.quote_input import IngestRequest
from app.core.anonymization import anonymize_quote, generate_company_hash
from app.core.chunking import generate_chunks
from app.core.embeddings import EmbeddingService
from app.models import Chunk, Document, IngestionLog
from app.utils.text_processing import parse_duration_weeks, preprocess_chunk_text

logger = structlog.stdlib.get_logger()


class IngestResult:
    """Result of a successful ingestion."""

    def __init__(
        self, document_id: uuid.UUID, chunks_count: int, processing_time_ms: int
    ) -> None:
        self.document_id = document_id
        self.chunks_count = chunks_count
        self.processing_time_ms = processing_time_ms


class DuplicateError(Exception):
    """Raised when a duplicate quote is detected."""

    def __init__(self, existing_document_id: uuid.UUID) -> None:
        self.existing_document_id = existing_document_id
        super().__init__(f"Duplicate quote detected: {existing_document_id}")


class IngestService:
    """Orchestrates the full quote ingestion pipeline."""

    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService) -> None:
        self._db = db
        self._embedding_service = embedding_service

    async def _log_step(
        self,
        document_id: uuid.UUID | None,
        action: str,
        status: str,
        details: dict | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        log_entry = IngestionLog(
            document_id=document_id,
            action=action,
            status=status,
            details=details,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        self._db.add(log_entry)

    async def _check_duplicate(self, request: IngestRequest) -> None:
        project_title = (
            request.quote.project.title.lower().strip() if request.quote.project else None
        )
        company_hash = (
            generate_company_hash(request.quote.client.company)
            if request.quote.client and request.quote.client.company
            else None
        )

        if not project_title:
            return

        stmt = select(Document).where(
            func.lower(Document.project_title) == project_title,
        )
        if company_hash:
            stmt = stmt.where(Document.client_company_hash == company_hash)

        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise DuplicateError(existing.id)

    async def ingest_quote(self, request: IngestRequest) -> IngestResult:
        """Execute the full ingestion pipeline for a quote."""
        start_time = time.monotonic()

        # Step 1: Check for duplicates
        await self._check_duplicate(request)

        # Step 2: Anonymize client data
        anonymized_quote, company_hash, sector = anonymize_quote(request.quote)

        # Calculate document-level aggregations
        total_budget = sum(
            (Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
             for item in request.quote.items),
            Decimal("0"),
        )
        all_techs = list(dict.fromkeys(
            tech
            for sb in request.quote.scope_blocks
            for tech in (sb.technologies or [])
        ))
        total_duration = sum(
            parse_duration_weeks(p.duration) or 0
            for p in (request.quote.roadmap_phases or [])
        )
        team_size = sum(
            m.quantity for m in (request.quote.team_members or [])
        )

        # Step 3: Create Document record and commit so it survives failures
        doc = Document(
            raw_json=request.quote.model_dump(mode="json"),
            project_title=(
                request.quote.project.title if request.quote.project else "Untitled"
            ),
            project_subtitle=(
                request.quote.project.subtitle if request.quote.project else None
            ),
            total_budget=total_budget,
            currency=request.quote.currency,
            total_duration_weeks=total_duration or None,
            team_size=team_size or None,
            technologies=all_techs or None,
            client_company_hash=company_hash,
            client_sector=sector,
            ingestion_status="processing",
            source=request.source,
            ingested_by=request.ingested_by,
        )
        self._db.add(doc)
        await self._db.flush()
        doc_id = doc.id

        await self._log_step(doc_id, "ingest_start", "success")
        await self._log_step(doc_id, "validation", "success")
        await self._db.commit()

        try:
            # Step 4: Generate chunks
            chunk_start = time.monotonic()
            chunk_data_list = generate_chunks(anonymized_quote, doc_id)
            chunk_ms = round((time.monotonic() - chunk_start) * 1000)

            type_counts: dict[str, int] = {}
            for cd in chunk_data_list:
                type_counts[cd.chunk_type] = type_counts.get(cd.chunk_type, 0) + 1

            await self._log_step(
                doc_id, "chunking", "success",
                details={"counts": type_counts, "total": len(chunk_data_list)},
                duration_ms=chunk_ms,
            )

            # Step 5: Preprocess texts
            for cd in chunk_data_list:
                cd.content_text = preprocess_chunk_text(cd.content_text, cd.chunk_type)

            # Step 6: Generate embeddings in batch
            emb_start = time.monotonic()
            texts = [cd.content_text for cd in chunk_data_list]
            embeddings = await self._embedding_service.generate_embeddings(texts)
            emb_ms = round((time.monotonic() - emb_start) * 1000)

            await self._log_step(
                doc_id, "embedding", "success",
                details={"texts_count": len(texts), "latency_ms": emb_ms},
                duration_ms=emb_ms,
            )

            # Step 7: Store chunks with embeddings (bulk insert)
            chunk_objects: list[Chunk] = []
            for cd, emb in zip(chunk_data_list, embeddings):
                chunk_obj = Chunk(
                    document_id=doc_id,
                    chunk_type=cd.chunk_type,
                    content_text=cd.content_text,
                    embedding=emb,
                    metadata_=cd.metadata,
                    embedding_model=self._embedding_service._model,
                    embedding_version="v1",
                    project_title=cd.project_title,
                    technologies=cd.technologies or None,
                    total_cost=cd.total_cost,
                    currency=cd.currency,
                )
                chunk_objects.append(chunk_obj)

            self._db.add_all(chunk_objects)
            await self._db.flush()

            await self._log_step(
                doc_id, "storage", "success",
                details={"chunks_stored": len(chunk_objects)},
            )

            # Step 8: Update document status
            doc.ingestion_status = "completed"
            doc.chunks_count = len(chunk_objects)
            doc.updated_at = datetime.now(UTC)

            total_ms = round((time.monotonic() - start_time) * 1000)
            await self._log_step(
                doc_id, "ingest_complete", "success",
                details={
                    "total_chunks": len(chunk_objects),
                    "processing_time_ms": total_ms,
                },
                duration_ms=total_ms,
            )

            await self._db.commit()

            await logger.ainfo(
                "Quote ingested successfully",
                document_id=str(doc_id),
                chunks_count=len(chunk_objects),
                processing_time_ms=total_ms,
            )

            return IngestResult(
                document_id=doc_id,
                chunks_count=len(chunk_objects),
                processing_time_ms=total_ms,
            )

        except Exception as e:
            await self._db.rollback()

            # Update document status to failed in a new transaction
            result = await self._db.execute(
                select(Document).where(Document.id == doc_id)
            )
            failed_doc = result.scalar_one_or_none()
            if failed_doc:
                failed_doc.ingestion_status = "failed"
                failed_doc.ingestion_error = str(e)[:500]
                failed_doc.updated_at = datetime.now(UTC)

                await self._log_step(
                    doc_id, "ingest_error", "failure",
                    error_message=str(e)[:500],
                )
                await self._db.commit()

            await logger.aerror(
                "Quote ingestion failed",
                document_id=str(doc_id),
                error=str(e),
            )
            raise

    async def get_ingestion_status(
        self, document_id: uuid.UUID
    ) -> IngestStatusResponse | None:
        """Get the ingestion status for a document."""
        result = await self._db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return None

        # Count chunks by type
        type_counts_result = await self._db.execute(
            select(Chunk.chunk_type, func.count())
            .where(Chunk.document_id == document_id)
            .group_by(Chunk.chunk_type)
        )
        type_counts = dict(type_counts_result.all())

        breakdown = ChunksBreakdown(
            project_overview=type_counts.get("project_overview", 0),
            scope_block=type_counts.get("scope_block", 0),
            line_item=type_counts.get("line_item", 0),
            phase=type_counts.get("phase", 0),
            team_conditions=type_counts.get("team_conditions", 0),
        )

        return IngestStatusResponse(
            document_id=doc.id,
            status=doc.ingestion_status,
            project_title=doc.project_title,
            chunks_created=doc.chunks_count,
            breakdown=breakdown,
        )

    async def delete_document(
        self, document_id: uuid.UUID
    ) -> IngestDeleteResponse | None:
        """Delete a document and all its chunks."""
        result = await self._db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return None

        chunks_count = doc.chunks_count

        await self._log_step(
            doc.id, "delete", "success",
            details={"chunks_deleted": chunks_count},
        )

        await self._db.delete(doc)  # CASCADE deletes chunks
        await self._db.commit()

        return IngestDeleteResponse(
            document_id=document_id,
            status="deleted",
            chunks_deleted=chunks_count,
        )
