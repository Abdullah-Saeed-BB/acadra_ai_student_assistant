"""Pydantic schemas and enums for MCP tool inputs and structured models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from src.connectors.gmail import normalize_allowed_senders


# --- Enums (Section 5.2) ---

class ItemType(str, Enum):
    ASSIGNMENT = "assignment"
    ANNOUNCEMENT = "announcement"
    READING = "reading"
    EVENT = "event"


class ReviewState(str, Enum):
    VERIFIED = "verified"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class SourceType(str, Enum):
    TEXT = "text"
    HTML = "html"
    PDF = "pdf"
    GMAIL = "gmail"


class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


class ChangeKind(str, Enum):
    CREATED = "created"
    EDITED = "edited"


class ReviewAction(str, Enum):
    CONFIRM = "confirm"
    REJECT = "reject"
    CORRECT = "correct"


# --- Academic Item Schemas ---

class ListAcademicItemsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_type: ItemType | None = None
    course_id: UUID | None = None
    review_state: ReviewState | None = None
    due_from: AwareDatetime | None = Field(default=None, description="Inclusive lower bound (timezone-aware)")
    due_before: AwareDatetime | None = Field(default=None, description="Exclusive upper bound (timezone-aware)")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)

    @model_validator(mode="after")
    def validate_range(self) -> ListAcademicItemsInput:
        if self.due_from is not None and self.due_before is not None:
            if self.due_from >= self.due_before:
                raise ValueError("due_from must be earlier than due_before")
        return self


class ReviewAcademicItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: UUID
    action: ReviewAction
    fields: dict[str, Any] | None = Field(
        default=None,
        description="Updated fields when action is 'correct' (allowlisted: title, details, starts_at, due_at, grade_weight_percent, late_penalty, course_id)",
    )
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_action_fields(self) -> ReviewAcademicItemInput:
        if self.action == ReviewAction.CORRECT and not self.fields:
            raise ValueError("fields dictionary is required when action is 'correct'")
        return self


class CorrectionFields(BaseModel):
    """Allowlisted academic fields a student correction may change.

    Parsing coerces ISO-8601 strings into aware datetimes and UUID strings into
    UUIDs before the service writes them, so a valid JSON payload is accepted.
    Use ``model_dump(exclude_unset=True)`` to apply only the fields provided.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=500)
    details: str | None = Field(default=None, max_length=5000)
    starts_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    grade_weight_percent: float | None = Field(default=None, ge=0, le=100)
    late_penalty: str | None = Field(default=None, max_length=500)
    course_id: UUID | None = None


# --- Changes Schemas ---

class GetChangesSinceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    since: AwareDatetime | None = Field(default=None, description="Changes after this instant (timezone-aware)")
    item_type: ItemType | None = None
    course_id: UUID | None = None
    change_kind: ChangeKind | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


# --- Sources Schemas ---

class ListSourcesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_type: SourceType | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


# --- Courses Schemas ---

class ListCoursesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


# --- Tasks & Planning Schemas ---

class ListTasksInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: TaskStatus | None = None
    selected_day: date | None = Field(default=None, description="Exact YYYY-MM-DD match")
    selected_from: date | None = Field(default=None, description="Inclusive start date")
    selected_to: date | None = Field(default=None, description="Inclusive end date")
    has_selected_day: bool | None = Field(default=None, description="False returns the Backlog")
    parent_task_id: UUID | None = None
    academic_item_id: UUID | None = None
    course_id: UUID | None = None
    tag: str | None = Field(default=None, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)

    @model_validator(mode="after")
    def validate_date_range(self) -> ListTasksInput:
        if self.selected_from is not None and self.selected_to is not None:
            if self.selected_from > self.selected_to:
                raise ValueError("selected_from must be less than or equal to selected_to")
        return self


class CreateTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=2000)
    selected_day: date | None = Field(default=None, description="Day to schedule, or omit for backlog")
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    tags: list[str] = Field(default_factory=list, max_length=10)
    academic_item_id: UUID | None = None
    course_id: UUID | None = None
    parent_task_id: UUID | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        for tag in tags:
            if len(tag) > 50:
                raise ValueError("Tag length must not exceed 50 characters")
        return tags


class UpdateTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_id: UUID
    title: str | None = Field(default=None, min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None
    selected_day: date | None = None
    clear_selected_day: bool = False
    list_position: int | None = Field(default=None, ge=0)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    tags: list[str] | None = Field(default=None, max_length=10)
    parent_task_id: UUID | None = None


class StepItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    selected_day: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)


class SplitTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_id: UUID
    steps: list[StepItem] = Field(min_length=1, max_length=20)
    replace_existing: bool = False


class GetTodayPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    day: date | None = Field(default=None, description="Defaults to today")
    timezone: str | None = Field(default=None, description="IANA timezone name, e.g. 'America/New_York'")
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


class GetUpcomingPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    days: int = Field(default=7, ge=7, le=14)
    start_day: date | None = None
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


class GetBacklogInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


class GetPlanBoardInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    start_day: date | None = None
    days: int = Field(default=7, ge=1, le=14)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


# --- Preferences Schemas ---

class SetPreferencesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_daily_minutes: int | None = Field(default=None, ge=1, le=1440)
    focus_task_count: int | None = Field(default=None, ge=1, le=20)


# --- Operator Schemas ---

class SetGmailSendersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_senders: list[str] = Field(min_length=1, max_length=50)

    @field_validator("allowed_senders")
    @classmethod
    def normalize_senders(cls, values: list[str]) -> list[str]:
        return normalize_allowed_senders(values)
