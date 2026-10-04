"""SQLAlchemy models for source provenance and accepted academic facts."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Metadata shared by all database models."""


class SourceConnection(Base):
    """Local source accounts; credential_ref points to the secret store."""

    __tablename__ = "source_connections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(Text)
    account_label: Mapped[str] = mapped_column(Text)
    external_account_id: Mapped[str | None] = mapped_column(Text)
    credential_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceDocument(Base):
    """Fetched or manually supplied material and its original reference."""

    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_connections.id")
    )
    source_type: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    original_ref: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    course_hint: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceRevision(Base):
    """A source snapshot used for change detection and precise citations."""

    __tablename__ = "source_revisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id")
    )
    revision_no: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(Text)
    raw_content: Mapped[str | None] = mapped_column(Text)
    clean_text: Mapped[str] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Course(Base):
    """Optional course context for normalized academic items."""

    __tablename__ = "courses"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    term: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AcademicItem(Base):
    """Current academic facts, with unknown dates and references left NULL."""

    __tablename__ = "academic_items"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    course_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("courses.id"))
    source_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_revisions.id")
    )
    item_type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grade_weight_percent: Mapped[Decimal | None] = mapped_column(Numeric)
    late_penalty: Mapped[str | None] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AcademicItemChange(Base):
    """Accepted fact changes for the inbox and affected-plan recalculation."""

    __tablename__ = "academic_item_changes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    academic_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("academic_items.id")
    )
    source_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_revisions.id")
    )
    origin: Mapped[str] = mapped_column(Text)
    change_kind: Mapped[str] = mapped_column(Text)
    before_values: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    after_values: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceItemLink(Base):
    """Source-local identity and review evidence for an extracted candidate."""

    __tablename__ = "source_item_links"
    __table_args__ = (UniqueConstraint("source_document_id", "source_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_document_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("source_documents.id"))
    source_key: Mapped[str] = mapped_column(Text)
    academic_item_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("academic_items.id"))
    source_revision_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("source_revisions.id"))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    review_reasons: Mapped[list[str]] = mapped_column(JSON)
    date_facts: Mapped[dict[str, Any]] = mapped_column(JSON)


class SourceProcessingRun(Base):
    """A completed or failed extraction attempt, without private prompt content."""

    __tablename__ = "source_processing_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_revision_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("source_revisions.id"))
    status: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
