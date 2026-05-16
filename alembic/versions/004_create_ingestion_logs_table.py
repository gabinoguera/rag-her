"""[LEGACY] Migración del dominio rag-estimation-service. Conservada para integridad de la cadena down_revision.

Create ingestion_logs table.

Revision ID: 004
Revises: 003
Create Date: 2025-01-01 00:00:03.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_logs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"), nullable=False,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.VARCHAR(30), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('ingest_start', 'validation', 'chunking', 'embedding', "
            "'storage', 'ingest_complete', 'ingest_error', 'delete')",
            name="ck_ingestion_logs_action",
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failure', 'warning')",
            name="ck_ingestion_logs_status",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["rag.documents.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="rag",
    )

    op.create_index(
        "idx_ingestion_logs_document_id", "ingestion_logs",
        ["document_id"], schema="rag",
    )
    op.create_index(
        "idx_ingestion_logs_action_status", "ingestion_logs",
        ["action", "status"], schema="rag",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_ingestion_logs_action_status",
        table_name="ingestion_logs", schema="rag",
    )
    op.drop_index(
        "idx_ingestion_logs_document_id",
        table_name="ingestion_logs", schema="rag",
    )
    op.drop_table("ingestion_logs", schema="rag")
