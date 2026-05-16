"""Create her.check_in_chunks table with HNSW index.

Revision ID: 009
Revises: 008
Create Date: 2025-01-01 00:00:08.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "check_in_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "checkin_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "question_index",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "question_text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "answer_text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            Vector(768),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["checkin_id"],
            ["her.check_ins.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="her",
    )

    op.create_index(
        "idx_check_in_chunks_checkin_id",
        "check_in_chunks",
        ["checkin_id"],
        schema="her",
    )

    # HNSW index for vector similarity search (cosine distance, 768-dim Gemini embeddings)
    op.execute(
        "CREATE INDEX ON her.check_in_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m=16, ef_construction=200)"
    )


def downgrade() -> None:
    op.drop_index(
        "idx_check_in_chunks_checkin_id",
        table_name="check_in_chunks",
        schema="her",
    )
    op.drop_table("check_in_chunks", schema="her")
