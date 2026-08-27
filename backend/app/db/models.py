import enum
import uuid
from datetime import UTC, datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            try:
                return uuid.UUID(str(value))
            except Exception:
                return value
        return value

class JSONType(TypeDecorator):
    """Platform-independent JSON type."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_JSONB)
        return dialect.type_descriptor(JSON)

class VectorType(TypeDecorator):
    """Platform-independent Vector type."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(settings.EMBEDDING_DIMENSION))
            except Exception:
                return dialect.type_descriptor(JSON)
        return dialect.type_descriptor(JSON)

from app.core.config import settings
from app.db.database import Base


class ScreeningVerdictEnum(str, enum.Enum):
    GO = "GO"
    NO_GO = "NO-GO"
    REVIEW = "REVIEW"


class IngestionStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    LANGUAGE_UNSUPPORTED = "LANGUAGE_UNSUPPORTED"


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tender_ref = Column(String(200), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    issuing_authority = Column(String(300), nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    category = Column(String(100), default="bus_operations", nullable=False)

    original_bus_quantity = Column(Integer, nullable=True)
    latest_bus_quantity = Column(Integer, nullable=True)
    latest_quantity_source = Column(String(300), nullable=True)

    submission_deadline = Column(DateTime(timezone=True), nullable=False)
    original_deadline = Column(DateTime(timezone=True), nullable=True)
    latest_deadline = Column(DateTime(timezone=True), nullable=True)
    latest_deadline_source = Column(String(300), nullable=True)
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)

    emd_amount = Column(Numeric(15, 2), nullable=True)
    original_emd_amount = Column(Numeric(15, 2), nullable=True)
    latest_emd_amount = Column(Numeric(15, 2), nullable=True)
    latest_emd_source = Column(String(300), nullable=True)
    emd_breakdown = Column(JSONType, nullable=True)

    document_fee = Column(Numeric(15, 2), nullable=True)
    scope_summary = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    source_name = Column(String(200), nullable=True)
    raw_document_path = Column(String(1000), nullable=False)
    document_hash = Column(String(64), unique=True, nullable=False, index=True)

    extraction_provenance = Column(JSONType, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    eligibility = relationship("TenderEligibility", back_populates="tender", uselist=False, cascade="all, delete-orphan")
    screening_results = relationship("ScreeningResult", back_populates="tender", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="tender", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="tender", cascade="all, delete-orphan")


class TenderEligibility(Base):
    __tablename__ = "tender_eligibility"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tender_id = Column(GUID, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, unique=True)
    minimum_fleet_size = Column(Integer, nullable=True)
    minimum_annual_turnover = Column(Numeric(15, 2), nullable=True)
    minimum_experience_years = Column(Integer, nullable=True)
    minimum_past_contract_value = Column(Numeric(15, 2), nullable=True)
    minimum_depots_required = Column(Integer, nullable=True)
    required_geographies = Column(JSONType, nullable=True)
    other_requirements = Column(JSONType, nullable=True)

    tender = relationship("Tender", back_populates="eligibility")


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    fleet_size = Column(Integer, nullable=False, default=0)
    annual_turnover = Column(Numeric(15, 2), nullable=False, default=0.0)
    years_experience = Column(Integer, nullable=False, default=0)
    past_contract_sizes = Column(JSONType, nullable=False, default=list)
    preferred_geographies = Column(JSONType, nullable=False, default=list)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)


class ScreeningResult(Base):
    __tablename__ = "screening_results"
    # Structural uniqueness: one active screening result per tender.
    # This makes duplicate rows impossible at the DB level — not just by convention.
    __table_args__ = (UniqueConstraint("tender_id", name="uq_screening_results_tender_id"),)

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tender_id = Column(GUID, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, unique=True)
    verdict = Column(SQLEnum(ScreeningVerdictEnum), nullable=False)
    reasoning = Column(Text, nullable=False)
    criteria_results = Column(JSONType, nullable=False)
    screened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    tender = relationship("Tender", back_populates="screening_results")


class Document(Base):
    __tablename__ = "documents"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tender_id = Column(GUID, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False, default="ORIGINAL_RFP")
    amendment_number = Column(String(50), nullable=True)
    source_url = Column(String(1000), nullable=True)
    page_count = Column(Integer, nullable=False, default=0)
    document_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    tender = relationship("Tender", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tender_id = Column(GUID, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(GUID, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(VectorType, nullable=False)
    chunk_metadata = Column(JSONType, nullable=True)

    tender = relationship("Tender", back_populates="chunks")
    document = relationship("Document", back_populates="chunks")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    status = Column(SQLEnum(IngestionStatusEnum), nullable=False, default=IngestionStatusEnum.PENDING, index=True)
    total_documents = Column(Integer, nullable=False, default=0)
    completed_documents = Column(Integer, nullable=False, default=0)
    failed_documents = Column(Integer, nullable=False, default=0)
    current_document = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
