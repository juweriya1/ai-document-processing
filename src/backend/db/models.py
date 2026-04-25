import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_doc_id():
    return "doc_" + uuid.uuid4().hex[:6]


def generate_user_id():
    return "usr_" + uuid.uuid4().hex[:6]


def generate_field_id():
    return "fld_" + uuid.uuid4().hex[:6]


def generate_line_id():
    return "lin_" + uuid.uuid4().hex[:6]


def generate_correction_id():
    return "cor_" + uuid.uuid4().hex[:6]


def generate_batch_id():
    return "bat_" + uuid.uuid4().hex[:8]


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_user_id)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="enterprise_user")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    insights_layout = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    documents = relationship("Document", back_populates="uploader", foreign_keys="[Document.uploaded_by]")
    corrections = relationship("Correction", back_populates="reviewer")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_doc_id)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="uploaded")
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_reason = Column(Text, nullable=True)
    # Agentic pipeline fields — populated by persist_node / DocumentProcessor.
    traceability_log = Column(JSON, nullable=True)
    fallback_tier = Column(String(32), nullable=True)
    confidence_score = Column(Float, nullable=True)
    # Batch upload support — NULL for legacy single-file uploads.
    batch_id = Column(String, ForeignKey("batches.id"), nullable=True, index=True)

    uploader = relationship("User", back_populates="documents", foreign_keys=[uploaded_by])
    approver = relationship("User", foreign_keys=[approved_by])
    extracted_fields = relationship("ExtractedField", back_populates="document")
    line_items = relationship("LineItem", back_populates="document")
    corrections = relationship("Correction", back_populates="document")
    batch = relationship("Batch", back_populates="documents")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String, primary_key=True, default=generate_batch_id)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    # uploading | processing | completed | partial_failed
    status = Column(String, nullable=False, default="uploading")
    total_documents = Column(Integer, nullable=False, default=0)

    documents = relationship("Document", back_populates="batch")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(String, primary_key=True, default=generate_field_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    field_name = Column(String, nullable=False)
    field_value = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    document = relationship("Document", back_populates="extracted_fields")


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(String, primary_key=True, default=generate_line_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    total = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    document = relationship("Document", back_populates="line_items")


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(String, primary_key=True, default=generate_correction_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    field_id = Column(String, ForeignKey("extracted_fields.id"), nullable=False)
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    document = relationship("Document", back_populates="corrections")
    field = relationship("ExtractedField")
    reviewer = relationship("User", back_populates="corrections")


class AnalyticsSummary(Base):
    __tablename__ = "analytics_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    period = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class SupplierMetric(Base):
    __tablename__ = "supplier_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_name = Column(String, nullable=False)
    total_documents = Column(Integer, default=0)
    avg_confidence = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
