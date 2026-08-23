"""Add minimum depots required to eligibility

Revision ID: 42330befd521
Revises: 5760beb5b967
Create Date: 2026-08-15 16:50:18.596868

"""
from collections.abc import Sequence
from typing import Union

import pgvector
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '42330befd521'
down_revision: str | None = '5760beb5b967'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('tender_eligibility', sa.Column('minimum_depots_required', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('tender_eligibility', 'minimum_depots_required')
