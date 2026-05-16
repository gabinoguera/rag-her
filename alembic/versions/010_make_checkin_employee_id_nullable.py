"""Make her.check_ins.employee_id nullable.

Revision ID: 010
Revises: 009
Create Date: 2026-05-16 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("check_ins", "employee_id", nullable=True, schema="her")


def downgrade() -> None:
    op.alter_column("check_ins", "employee_id", nullable=False, schema="her")
