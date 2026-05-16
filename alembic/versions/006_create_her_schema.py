"""Create her schema.

Revision ID: 006
Revises: 005
Create Date: 2025-01-01 00:00:05.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS her")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Do not drop the her schema here because alembic stores its version table
    # (her.alembic_version) in this schema. Dropping the schema with CASCADE would
    # destroy the version table before alembic can record the downgrade to revision 005.
    # The schema and any remaining objects are cleaned up by the DBA or test teardown
    # after alembic downgrade completes.
    pass
