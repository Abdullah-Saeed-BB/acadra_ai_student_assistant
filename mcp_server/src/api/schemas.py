"""JSON contracts for the web-facing REST API."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from src.connectors.gmail import normalize_allowed_senders


class GmailConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_senders: list[str] = Field(min_length=1, max_length=50)

    @field_validator("allowed_senders")
    @classmethod
    def normalize_senders(cls, values: list[str]) -> list[str]:
        return normalize_allowed_senders(values)


class GmailConnectionResponse(BaseModel):
    connection_id: UUID | None
    account_email: str | None
    allowed_senders: list[str]
    status: Literal["not_configured", "not_connected", "connected"]
    oauth_configured: bool


class ManualTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=65536)
    title: str | None = Field(default=None, max_length=200)
    source_document_id: UUID | None = None


class ManualTextResponse(BaseModel):
    source_document_id: UUID
    source_revision_id: UUID
    revision_no: int
    created_revision: bool
    processing_status: Literal["processed", "already_processed", "pending_configuration", "failed", "superseded"]
    academic_item_ids: list[UUID]
    review_count: int


class SourceCandidateResponse(BaseModel):
    id: UUID
    source_revision_id: UUID
    academic_item_id: UUID | None
    evidence: dict[str, str | None]
    review_reasons: list[str]
    date_facts: dict[str, dict[str, str | None]]

    model_config = ConfigDict(from_attributes=True)


class SourceCandidateListResponse(BaseModel):
    candidates: list[SourceCandidateResponse]


class AcademicItemListQuery(BaseModel):
    """Bounded filters for reading saved academic items."""

    model_config = ConfigDict(extra="forbid")

    item_type: Literal["assignment", "announcement", "reading", "event"] | None = None
    course_id: UUID | None = None
    review_state: Literal["verified", "uncertain", "conflicting"] | None = None
    due_from: AwareDatetime | None = None
    due_before: AwareDatetime | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_due_range(self) -> "AcademicItemListQuery":
        if self.due_from is not None and self.due_before is not None:
            if self.due_from >= self.due_before:
                raise ValueError("due_from must be earlier than due_before")
        return self


class AcademicItemResponse(BaseModel):
    id: UUID
    item_type: Literal["assignment", "announcement", "reading", "event"]
    title: str
    details: str | None
    course_id: UUID | None
    source_revision_id: UUID | None
    starts_at: datetime | None
    due_at: datetime | None
    grade_weight_percent: Decimal | None
    late_penalty: str | None
    review_state: Literal["verified", "uncertain", "conflicting"]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AcademicItemEvidenceResponse(BaseModel):
    source_document_id: UUID
    source_revision_id: UUID
    source_title: str | None
    source_type: str
    evidence: dict[str, str | None]
    review_reasons: list[str]
    date_facts: dict[str, dict[str, str | None]]
    original_ref: str | None = None
    source_updated_at: datetime | None = None
    observed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AcademicItemListResponse(BaseModel):
    items: list[AcademicItemResponse]
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None
