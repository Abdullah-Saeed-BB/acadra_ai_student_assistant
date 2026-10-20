"""MCP tools for academic items and fact review."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from src.errors import handle_tool_errors, InvalidInputError, NotFoundError
from src.mcp.responses import format_read_response, paginate_response
from src.mcp.schemas import CorrectionFields
from src.mcp.time_parsing import parse_datetime_bound
from src.services.academic_items import (
    AcademicItemFilters,
    get_academic_item,
    get_academic_item_evidence,
    list_academic_items,
    review_academic_item,
)


def _review_message(action: str, changed: bool) -> str:
    if action == "confirm":
        state = "Review state set to verified." if changed else "Review state was already verified."
    elif action == "reject":
        state = "Review state set to uncertain." if changed else "Review state was already uncertain."
    else:
        state = "Academic item fields updated." if changed else "No fields changed."
    return f"{state} The item still exists; this tool does not delete or merge it."


def _serialize_item(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "item_type": item.item_type,
        "title": item.title,
        "details": item.details,
        "course_id": str(item.course_id) if item.course_id else None,
        "source_revision_id": str(item.source_revision_id) if item.source_revision_id else None,
        "starts_at": item.starts_at.isoformat() if item.starts_at else None,
        "due_at": item.due_at.isoformat() if item.due_at else None,
        "grade_weight_percent": float(item.grade_weight_percent) if item.grade_weight_percent is not None else None,
        "late_penalty": item.late_penalty,
        "review_state": item.review_state,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_list_academic_items",
        description=(
            "Read saved academic records with filters and pagination. Ordered by due date (undated last), "
            "then creation date. This is the recent-items data behind the Acadra Inbox page; pair it with "
            "study_get_changes_since when the user asks about their inbox."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_list_academic_items(
        item_type: Annotated[Literal["assignment", "announcement", "reading", "event"] | None, Field(default=None, description="Optional type filter")] = None,
        course_id: Annotated[str | None, Field(default=None, description="Optional course UUID filter")] = None,
        review_state: Annotated[Literal["verified", "uncertain", "conflicting"] | None, Field(default=None, description="Optional review status")] = None,
        due_from: Annotated[str | None, Field(default=None, description="Inclusive lower bound: ISO 8601 date-time with UTC offset (e.g. 2026-10-15T09:00:00Z) or date-only YYYY-MM-DD (interpreted as UTC midnight)")] = None,
        due_before: Annotated[str | None, Field(default=None, description="Exclusive upper bound; same formats as due_from")] = None,
        limit: Annotated[int, Field(default=20, ge=1, le=100, description="Page limit (1-100)")] = 20,
        offset: Annotated[int, Field(default=0, ge=0, description="Page offset")] = 0,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        parsed_course_id = UUID(course_id) if course_id else None
        parsed_due_from = parse_datetime_bound(due_from, param_name="due_from") if due_from else None
        parsed_due_before = parse_datetime_bound(due_before, param_name="due_before") if due_before else None
        if parsed_due_from and parsed_due_before and parsed_due_from >= parsed_due_before:
            raise InvalidInputError("due_from must be earlier than due_before")

        filters = AcademicItemFilters(
            item_type=item_type,
            course_id=parsed_course_id,
            review_state=review_state,
            due_from=parsed_due_from,
            due_before=parsed_due_before,
            limit=limit,
            offset=offset,
        )
        page = await list_academic_items(filters)
        serialized_items = [_serialize_item(item) for item in page.items]
        paged = paginate_response(serialized_items, limit=limit, offset=offset, has_more=page.has_more)

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"- **{i['title']}** ({i['item_type']}) — Due: {i['due_at'] or 'No date'} [{i['review_state']}]" for i in serialized_items]
            markdown_summary = f"### Academic Items ({len(serialized_items)})\n" + "\n".join(lines)

        return format_read_response(paged, response_format=response_format, markdown_summary=markdown_summary)

    @mcp.tool(
        name="study_get_academic_item",
        description="Retrieve an academic item's full fields, linked course information, and source revision ID.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_academic_item(
        item_id: Annotated[str, Field(description="Academic item UUID")],
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(item_id)
        except ValueError:
            raise InvalidInputError("item_id must be a valid UUID.") from None

        detail = await get_academic_item(parsed_id)
        if detail is None:
            raise NotFoundError(f"Academic item {item_id} was not found.", hint="Call study_list_academic_items to get a valid item_id.")

        res = _serialize_item(detail.item)
        res["course"] = {
            "id": str(detail.course.id),
            "code": detail.course.code,
            "name": detail.course.name,
            "term": detail.course.term,
        } if detail.course else None
        return res

    @mcp.tool(
        name="study_get_academic_item_evidence",
        description="Retrieve source provenance, excerpts, review reasons, and date wording for an academic item.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_academic_item_evidence(
        item_id: Annotated[str, Field(description="Academic item UUID")],
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(item_id)
        except ValueError:
            raise InvalidInputError("item_id must be a valid UUID.") from None

        evidence = await get_academic_item_evidence(parsed_id)
        if evidence is None:
            raise NotFoundError(f"Evidence for academic item {item_id} was not found.")

        return {
            "source_document_id": str(evidence.source_document_id),
            "source_revision_id": str(evidence.source_revision_id),
            "source_title": evidence.source_title,
            "source_type": evidence.source_type,
            "evidence": evidence.evidence,
            "review_reasons": evidence.review_reasons,
            "date_facts": evidence.date_facts,
            "original_ref": evidence.original_ref,
            "source_updated_at": evidence.source_updated_at.isoformat() if evidence.source_updated_at else None,
            "observed_at": evidence.observed_at.isoformat() if evidence.observed_at else None,
        }

    @mcp.tool(
        name="study_review_academic_item",
        description=(
            "Change an academic item's review state or correct its extracted fields. "
            "Action 'confirm' marks it verified, 'reject' marks it uncertain, and 'correct' updates "
            "allowlisted fields (title, details, starts_at, due_at, grade_weight_percent, late_penalty, "
            "course_id) and records an immutable change event. This tool never deletes, merges, hides, "
            "or removes an item, and it must not be used to satisfy a delete or merge request."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_review_academic_item(
        item_id: Annotated[str, Field(description="Academic item UUID")],
        action: Annotated[Literal["confirm", "reject", "correct"], Field(description="Review action to perform")],
        fields: Annotated[dict[str, Any] | None, Field(default=None, description="Allowlisted fields to update when action is 'correct'")] = None,
        note: Annotated[str | None, Field(default=None, max_length=500, description="Optional note recorded with the change")] = None,
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(item_id)
        except ValueError:
            raise InvalidInputError("item_id must be a valid UUID.") from None

        parsed_fields: dict[str, Any] | None = None
        if fields is not None:
            # Coerce ISO-8601 date strings and UUID strings before the service writes them.
            parsed_fields = CorrectionFields.model_validate(fields).model_dump(exclude_unset=True)

        item, change, changed = await review_academic_item(parsed_id, action=action, fields=parsed_fields, note=note)
        res = {
            "item": _serialize_item(item),
            "action": action,
            "changed": changed,
            "message": _review_message(action, changed),
        }
        if change:
            res["change"] = {
                "id": str(change.id),
                "origin": change.origin,
                "change_kind": change.change_kind,
                "before_values": change.before_values,
                "after_values": change.after_values,
                "recorded_at": change.recorded_at.isoformat(),
            }
        return res
