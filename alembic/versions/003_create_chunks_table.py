"""[LEGACY] Migración del dominio rag-estimation-service. Conservada para integridad de la cadena down_revision.

Create chunks table.

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:02.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chunks",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"), nullable=False,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column("chunk_type", sa.VARCHAR(30), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"), nullable=True,
        ),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("embedding_version", sa.Text(), nullable=True),
        sa.Column("project_title", sa.Text(), nullable=True),
        sa.Column("technologies", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "total_cost", sa.Numeric(precision=12, scale=2), nullable=True,
        ),
        sa.Column("currency", sa.VARCHAR(3), nullable=True),
        sa.CheckConstraint(
            "chunk_type IN ('project_overview', 'scope_block', "
            "'line_item', 'phase', 'team_conditions')",
            name="ck_chunks_chunk_type",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["rag.documents.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="rag",
    )

    op.create_index(
        "idx_chunks_chunk_type", "chunks",
        ["chunk_type"], schema="rag",
    )
    op.create_index(
        "idx_chunks_document_id", "chunks",
        ["document_id"], schema="rag",
    )
    op.create_index(
        "idx_chunks_technologies", "chunks", ["technologies"],
        schema="rag", postgresql_using="gin",
    )

    # HNSW index for vector similarity search
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON rag.chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )

    # GIN index on metadata with jsonb_path_ops
    op.execute(
        "CREATE INDEX idx_chunks_metadata ON rag.chunks "
        "USING gin (metadata jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS rag.idx_chunks_metadata")
    op.execute("DROP INDEX IF EXISTS rag.idx_chunks_embedding")
    op.drop_index(
        "idx_chunks_technologies", table_name="chunks", schema="rag",
    )
    op.drop_index(
        "idx_chunks_document_id", table_name="chunks", schema="rag",
    )
    op.drop_index(
        "idx_chunks_chunk_type", table_name="chunks", schema="rag",
    )
    op.drop_table("chunks", schema="rag")
