"""Initial schema

Revision ID: 73c8a9ac2af1
Revises: None
Create Date: 2026-08-15 14:16:29.012428

"""
from collections.abc import Sequence
from typing import Union

import pgvector
import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '73c8a9ac2af1'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    op.create_table('company_profiles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('fleet_size', sa.Integer(), nullable=False),
    sa.Column('annual_turnover', sa.Numeric(precision=15, scale=2), nullable=False),
    sa.Column('years_experience', sa.Integer(), nullable=False),
    sa.Column('past_contract_sizes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('preferred_geographies', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ingestion_jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'LANGUAGE_UNSUPPORTED', name='ingestionstatusenum'), nullable=False),
    sa.Column('total_documents', sa.Integer(), nullable=False),
    sa.Column('completed_documents', sa.Integer(), nullable=False),
    sa.Column('failed_documents', sa.Integer(), nullable=False),
    sa.Column('current_document', sa.String(length=255), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingestion_jobs_status'), 'ingestion_jobs', ['status'], unique=False)
    op.create_table('tenders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('issuing_authority', sa.String(length=300), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('submission_deadline', sa.DateTime(timezone=True), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=False),
    sa.Column('emd_amount', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('document_fee', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('scope_summary', sa.Text(), nullable=True),
    sa.Column('source_url', sa.String(length=1000), nullable=True),
    sa.Column('source_name', sa.String(length=200), nullable=True),
    sa.Column('raw_document_path', sa.String(length=1000), nullable=False),
    sa.Column('document_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenders_document_hash'), 'tenders', ['document_hash'], unique=True)
    op.create_table('documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tender_id', sa.UUID(), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('source_url', sa.String(length=1000), nullable=True),
    sa.Column('page_count', sa.Integer(), nullable=False),
    sa.Column('document_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('screening_results',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tender_id', sa.UUID(), nullable=False),
    sa.Column('verdict', sa.Enum('GO', 'NO_GO', 'REVIEW', name='screeningverdictenum'), nullable=False),
    sa.Column('reasoning', sa.Text(), nullable=False),
    sa.Column('criteria_results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('screened_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tender_eligibility',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tender_id', sa.UUID(), nullable=False),
    sa.Column('minimum_fleet_size', sa.Integer(), nullable=True),
    sa.Column('minimum_annual_turnover', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('minimum_experience_years', sa.Integer(), nullable=True),
    sa.Column('minimum_past_contract_value', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('required_geographies', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('other_requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tender_id')
    )
    op.create_table('document_chunks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tender_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('chunk_text', sa.Text(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
    sa.Column('chunk_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_tender_id'), 'document_chunks', ['tender_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_chunks_tender_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_table('tender_eligibility')
    op.drop_table('screening_results')
    op.drop_table('documents')
    op.drop_index(op.f('ix_tenders_document_hash'), table_name='tenders')
    op.drop_table('tenders')
    op.drop_index(op.f('ix_ingestion_jobs_status'), table_name='ingestion_jobs')
    op.drop_table('ingestion_jobs')
    op.drop_table('company_profiles')
