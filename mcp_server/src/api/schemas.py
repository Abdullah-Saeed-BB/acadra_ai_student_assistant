"""JSON contracts for the web-facing REST API."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
