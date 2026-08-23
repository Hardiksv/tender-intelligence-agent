"""merge_depots_and_emd_breakdown_heads

Revision ID: e6520ffb1d69
Revises: ('42330befd521', 'a1b2c3d4e5f6')
Create Date: 2026-08-22 15:29:46.181550

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e6520ffb1d69'
down_revision: str | None = ('42330befd521', 'a1b2c3d4e5f6')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
