"""JSON contracts for the web-facing REST API."""

from datetime import date, datetime
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


class TaskResponse(BaseModel):
    id: UUID
    title: str
    details: str | None
    status: Literal["todo", "in_progress", "done"]
    selected_day: date | None
    list_position: int
    estimated_minutes: int | None
    tags: list[str]
    academic_item_id: UUID | None
    course_id: UUID | None
    parent_task_id: UUID | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskListQuery(BaseModel):
    """Bounded filters for reading planned tasks."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["todo", "in_progress", "done"] | None = None
    selected_day: date | None = None
    selected_from: date | None = None
    selected_to: date | None = None
    has_selected_day: bool | None = None
    parent_task_id: UUID | None = None
    academic_item_id: UUID | None = None
    course_id: UUID | None = None
    tag: str | None = Field(default=None, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_selected_range(self) -> "TaskListQuery":
        if self.selected_from is not None and self.selected_to is not None:
            if self.selected_from > self.selected_to:
                raise ValueError("selected_from must be on or before selected_to")
        return self


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class TaskCreateRequest(BaseModel):
    """Fields accepted when creating a task or step."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=2000)
    selected_day: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    tags: list[str] = Field(default_factory=list, max_length=10)
    academic_item_id: UUID | None = None
    course_id: UUID | None = None
    parent_task_id: UUID | None = None

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, tags: list[str]) -> list[str]:
        for tag in tags:
            if not tag.strip():
                raise ValueError("Tags must not be blank")
            if len(tag) > 50:
                raise ValueError("Tag length must not exceed 50 characters")
        return tags


class TaskUpdateRequest(BaseModel):
    """Partial task update.

    Link fields (``academic_item_id``/``course_id``) may be set to a UUID or
    sent as ``null`` to unlink; the matching ``clear_*`` flags do the same
    explicitly. ``selected_day`` may be sent as ``null`` or cleared with
    ``clear_selected_day`` to move a task to the Backlog. ``estimated_minutes``
    is cleared with ``clear_estimated_minutes`` because ``null`` means
    "leave unchanged".
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=2000)
    status: Literal["todo", "in_progress", "done"] | None = None
    selected_day: date | None = None
    clear_selected_day: bool = False
    list_position: int | None = Field(default=None, ge=0)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    clear_estimated_minutes: bool = False
    tags: list[str] | None = Field(default=None, max_length=10)
    parent_task_id: UUID | None = None
    academic_item_id: UUID | None = None
    clear_academic_item: bool = False
    course_id: UUID | None = None
    clear_course: bool = False

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return tags
        for tag in tags:
            if not tag.strip():
                raise ValueError("Tags must not be blank")
            if len(tag) > 50:
                raise ValueError("Tag length must not exceed 50 characters")
        return tags


class TaskDeleteResponse(BaseModel):
    """Confirmation for a removed task, including any links it had."""

    id: UUID
    title: str
    deleted_steps: int
    academic_item_id: UUID | None
    course_id: UUID | None


class TaskReorderRequest(BaseModel):
    """A new list order for the tasks that share one selected day.

    ``task_ids`` is the complete, ordered list of the tasks to rewrite, and
    ``selected_day`` names the list being reordered (``null`` for the Backlog).
    """

    model_config = ConfigDict(extra="forbid")

    task_ids: list[UUID] = Field(min_length=1, max_length=200)
    selected_day: date | None = None

    @field_validator("task_ids")
    @classmethod
    def unique_task_ids(cls, task_ids: list[UUID]) -> list[UUID]:
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("task_ids must not repeat a task")
        return task_ids


class TaskReorderResponse(BaseModel):
    selected_day: date | None
    tasks: list[TaskResponse]


class TaskDetailResponse(TaskResponse):
    steps: list[TaskResponse]
    progress: dict[str, int]
    academic_item: dict[str, str | None] | None
    course: dict[str, str | None] | None


class TodayPlanQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date | None = None


class TodayPlanResponse(BaseModel):
    day: date
    total_estimated_minutes: int
    tasks: list[TaskResponse]


class DayPlanGroupResponse(BaseModel):
    day: date
    total_estimated_minutes: int
    tasks: list[TaskResponse]


class UpcomingPlanQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int = Field(default=7, ge=7, le=14)
    start_day: date | None = None


class UpcomingPlanResponse(BaseModel):
    start_day: date
    end_day: date
    days: list[DayPlanGroupResponse]


class BacklogQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class BacklogResponse(BaseModel):
    tasks: list[TaskResponse]
    total_estimated_minutes: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class CourseListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CourseResponse(BaseModel):
    id: UUID
    code: str | None
    name: str
    term: str | None
    item_count: int
    created_at: datetime


class CourseListResponse(BaseModel):
    items: list[CourseResponse]
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None
