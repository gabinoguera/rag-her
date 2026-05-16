"""[LEGACY] Migración del dominio rag-estimation-service. Conservada para integridad de la cadena down_revision.

Create search_logs table.

Revision ID: 005
Revises: 004
Create Date: 2025-01-01 00:00:04.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_logs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"), nullable=False,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_embedding", Vector(1536), nullable=True),
        sa.Column(
            "chunk_types_filter", postgresql.ARRAY(sa.Text()), nullable=True,
        ),
        sa.Column(
            "technologies_filter", postgresql.ARRAY(sa.Text()), nullable=True,
        ),
        sa.Column("results_count", sa.Integer(), nullable=True),
        sa.Column("top_score", sa.Float(), nullable=True),
        sa.Column("avg_score", sa.Float(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("feedback_score", sa.SmallInteger(), nullable=True),
        sa.Column("feedback_notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "feedback_score BETWEEN 1 AND 5",
            name="ck_search_logs_feedback_score",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="rag",
    )


def downgrade() -> None:
    op.drop_table("search_logs", schema="rag")
