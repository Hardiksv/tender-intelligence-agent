"""Add parent child and latest value fields

Revision ID: 5760beb5b967
Revises: 73c8a9ac2af1
Create Date: 2026-08-15 16:10:24.722718

"""
from collections.abc import Sequence
from typing import Union

import pgvector
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '5760beb5b967'
down_revision: str | None = '73c8a9ac2af1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('document_type', sa.String(length=50), nullable=False, server_default='ORIGINAL_RFP'))
    op.add_column('documents', sa.Column('amendment_number', sa.String(length=50), nullable=True))
    op.add_column('tenders', sa.Column('tender_ref', sa.String(length=200), nullable=True))
    op.add_column('tenders', sa.Column('original_bus_quantity', sa.Integer(), nullable=True))
    op.add_column('tenders', sa.Column('latest_bus_quantity', sa.Integer(), nullable=True))
    op.add_column('tenders', sa.Column('latest_quantity_source', sa.String(length=300), nullable=True))
    op.add_column('tenders', sa.Column('original_deadline', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tenders', sa.Column('latest_deadline', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tenders', sa.Column('latest_deadline_source', sa.String(length=300), nullable=True))
    op.add_column('tenders', sa.Column('original_emd_amount', sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column('tenders', sa.Column('latest_emd_amount', sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column('tenders', sa.Column('latest_emd_source', sa.String(length=300), nullable=True))
    op.add_column('tenders', sa.Column('extraction_provenance', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index(op.f('ix_tenders_tender_ref'), 'tenders', ['tender_ref'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tenders_tender_ref'), table_name='tenders')
    op.drop_column('tenders', 'extraction_provenance')
    op.drop_column('tenders', 'latest_emd_source')
    op.drop_column('tenders', 'latest_emd_amount')
    op.drop_column('tenders', 'original_emd_amount')
    op.drop_column('tenders', 'latest_deadline_source')
    op.drop_column('tenders', 'latest_deadline')
    op.drop_column('tenders', 'original_deadline')
    op.drop_column('tenders', 'latest_quantity_source')
    op.drop_column('tenders', 'latest_bus_quantity')
    op.drop_column('tenders', 'original_bus_quantity')
    op.drop_column('tenders', 'tender_ref')
    op.drop_column('documents', 'amendment_number')
    op.drop_column('documents', 'document_type')
