"""[LEGACY] Migración del dominio rag-estimation-service. Conservada para integridad de la cadena down_revision.

Create documents table.

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:01.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"), nullable=False,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("raw_json", postgresql.JSONB(), nullable=True),
        sa.Column("project_title", sa.Text(), nullable=False),
        sa.Column("project_subtitle", sa.Text(), nullable=True),
        sa.Column(
            "total_budget", sa.Numeric(precision=12, scale=2), nullable=True,
        ),
        sa.Column(
            "currency", sa.VARCHAR(3),
            server_default=sa.text("'EUR'"), nullable=False,
        ),
        sa.Column("total_duration_weeks", sa.Integer(), nullable=True),
        sa.Column("team_size", sa.Integer(), nullable=True),
        sa.Column("technologies", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("client_company_hash", sa.Text(), nullable=True),
        sa.Column("client_sector", sa.Text(), nullable=True),
        sa.Column(
            "ingestion_status", sa.VARCHAR(20),
            server_default=sa.text("'pending'"), nullable=False,
        ),
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        sa.Column(
            "chunks_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("ingested_by", sa.Text(), nullable=True),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True,
        ),
        sa.CheckConstraint(
            "ingestion_status IN ('pending', 'processing', "
            "'completed', 'failed')",
            name="ck_documents_ingestion_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="rag",
    )

    op.create_index(
        "idx_documents_status", "documents",
        ["ingestion_status"], schema="rag",
    )
    op.create_index(
        "idx_documents_technologies", "documents", ["technologies"],
        schema="rag", postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX idx_documents_project_title ON rag.documents "
        "USING gin (project_title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS rag.idx_documents_project_title")
    op.drop_index(
        "idx_documents_technologies",
        table_name="documents", schema="rag",
    )
    op.drop_index(
        "idx_documents_status",
        table_name="documents", schema="rag",
    )
    op.drop_table("documents", schema="rag")
