"""MCP resource templates and static resources exposing read-only academic context."""

from __future__ import annotations

import json
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from src.services.academic_items import get_academic_item, get_academic_item_evidence
from src.services.changes import get_changes_since
from src.services.courses import get_course, list_courses
from src.services.preferences import get_preferences
from src.services.source_processing import list_latest_source_candidates
from src.services.sources import get_source_detail
from src.services.tasks import get_backlog, get_task, get_today_plan, get_upcoming_plan, list_tasks


def register(mcp: FastMCP) -> None:
    # 1. study://academic-items/{item_id}
    @mcp.resource("study://academic-items/{item_id}", name="academic_item", mime_type="application/json")
    async def resource_academic_item(item_id: str) -> str:
        detail = await get_academic_item(UUID(item_id))
        if detail is None:
            return json.dumps({"error": f"Academic item {item_id} not found"})
        item = detail.item
        return json.dumps({
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
            "course": {
                "id": str(detail.course.id),
                "code": detail.course.code,
                "name": detail.course.name,
            } if detail.course else None,
        }, indent=2)

    # 2. study://academic-items/{item_id}/evidence
    @mcp.resource("study://academic-items/{item_id}/evidence", name="academic_item_evidence", mime_type="application/json")
    async def resource_academic_item_evidence(item_id: str) -> str:
        evidence = await get_academic_item_evidence(UUID(item_id))
        if evidence is None:
            return json.dumps({"error": f"Evidence for item {item_id} not found"})
        return json.dumps({
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
        }, indent=2)

    # 3. study://sources/{source_document_id}
    @mcp.resource("study://sources/{source_document_id}", name="source_detail", mime_type="application/json")
    async def resource_source_detail(source_document_id: str) -> str:
        detail = await get_source_detail(UUID(source_document_id))
        return json.dumps({
            "id": str(detail.id),
            "source_type": detail.source_type,
            "title": detail.title,
            "original_ref": detail.original_ref,
            "course_hint": detail.course_hint,
            "revisions": [
                {
                    "id": str(r.id),
                    "revision_no": r.revision_no,
                    "content_hash": r.content_hash,
                    "observed_at": r.observed_at.isoformat(),
                    "source_updated_at": r.source_updated_at.isoformat() if r.source_updated_at else None,
                }
                for r in detail.revisions
            ],
            "academic_items": detail.academic_items,
            "has_review_candidates": detail.has_review_candidates,
            "last_change_at": detail.last_change_at.isoformat() if detail.last_change_at else None,
        }, indent=2)

    # 4. study://sources/{source_document_id}/candidates
    @mcp.resource("study://sources/{source_document_id}/candidates", name="source_candidates", mime_type="application/json")
    async def resource_source_candidates(source_document_id: str) -> str:
        candidates = await list_latest_source_candidates(UUID(source_document_id))
        if candidates is None:
            return json.dumps({"error": f"Source {source_document_id} not found"})
        return json.dumps([
            {
                "id": str(c.id),
                "source_revision_id": str(c.source_revision_id),
                "academic_item_id": str(c.academic_item_id) if c.academic_item_id else None,
                "evidence": c.evidence,
                "review_reasons": c.review_reasons,
                "date_facts": c.date_facts,
            }
            for c in candidates
        ], indent=2)

    # 5. study://courses
    @mcp.resource("study://courses", name="courses_list", mime_type="application/json")
    async def resource_courses() -> str:
        page = await list_courses(limit=100, offset=0)
        return json.dumps([
            {
                "id": str(c.id),
                "code": c.code,
                "name": c.name,
                "term": c.term,
                "item_count": c.item_count,
            }
            for c in page.items
        ], indent=2)

    # 6. study://courses/{course_id}
    @mcp.resource("study://courses/{course_id}", name="course_detail", mime_type="application/json")
    async def resource_course_detail(course_id: str) -> str:
        course = await get_course(UUID(course_id))
        return json.dumps({
            "id": str(course.id),
            "code": course.code,
            "name": course.name,
            "term": course.term,
            "academic_items": course.academic_items,
        }, indent=2)

    # 7. study://tasks
    @mcp.resource("study://tasks", name="tasks_list", mime_type="application/json")
    async def resource_tasks() -> str:
        page = await list_tasks(limit=100, offset=0)
        return json.dumps([
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "selected_day": t.selected_day.isoformat() if t.selected_day else None,
                "estimated_minutes": t.estimated_minutes,
                "tags": t.tags or [],
            }
            for t in page.items
        ], indent=2)

    # 8. study://tasks/{task_id}
    @mcp.resource("study://tasks/{task_id}", name="task_detail", mime_type="application/json")
    async def resource_task_detail(task_id: str) -> str:
        detail = await get_task(UUID(task_id))
        t = detail.task
        return json.dumps({
            "id": str(t.id),
            "title": t.title,
            "details": t.details,
            "status": t.status,
            "selected_day": t.selected_day.isoformat() if t.selected_day else None,
            "estimated_minutes": t.estimated_minutes,
            "tags": t.tags or [],
            "progress": detail.progress,
            "steps": [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "status": s.status,
                    "selected_day": s.selected_day.isoformat() if s.selected_day else None,
                    "estimated_minutes": s.estimated_minutes,
                }
                for s in detail.steps
            ],
            "academic_item": detail.academic_item,
            "course": detail.course,
        }, indent=2)

    # 9. study://plan/today
    @mcp.resource("study://plan/today", name="today_plan", mime_type="application/json")
    async def resource_today_plan() -> str:
        plan = await get_today_plan()
        return json.dumps({
            "day": plan.day.isoformat(),
            "total_estimated_minutes": plan.total_estimated_minutes,
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "estimated_minutes": t.estimated_minutes,
                }
                for t in plan.tasks
            ],
        }, indent=2)

    # 10. study://plan/upcoming
    @mcp.resource("study://plan/upcoming", name="upcoming_plan", mime_type="application/json")
    async def resource_upcoming_plan() -> str:
        upcoming = await get_upcoming_plan(days=7)
        return json.dumps({
            "start_day": upcoming.start_day.isoformat(),
            "end_day": upcoming.end_day.isoformat(),
            "days": [
                {
                    "day": d.day.isoformat(),
                    "total_estimated_minutes": d.total_estimated_minutes,
                    "task_count": len(d.tasks),
                }
                for d in upcoming.days
            ],
        }, indent=2)

    # 11. study://plan/backlog
    @mcp.resource("study://plan/backlog", name="backlog_plan", mime_type="application/json")
    async def resource_backlog() -> str:
        backlog = await get_backlog(limit=100, offset=0)
        return json.dumps({
            "total_estimated_minutes": backlog.total_estimated_minutes,
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "estimated_minutes": t.estimated_minutes,
                }
                for t in backlog.tasks
            ],
        }, indent=2)

    # 12. study://changes
    @mcp.resource("study://changes", name="recent_changes", mime_type="application/json")
    async def resource_changes() -> str:
        page = await get_changes_since(limit=50)
        return json.dumps([
            {
                "id": str(c.id),
                "academic_item_id": str(c.academic_item_id),
                "title": c.title,
                "change_kind": c.change_kind,
                "origin": c.origin,
                "recorded_at": c.recorded_at.isoformat(),
            }
            for c in page.items
        ], indent=2)

    # 13. study://preferences
    @mcp.resource("study://preferences", name="planning_preferences", mime_type="application/json")
    async def resource_preferences() -> str:
        prefs = await get_preferences(scope="default")
        return json.dumps({
            "preferred_daily_minutes": prefs.preferred_daily_minutes,
            "focus_task_count": prefs.focus_task_count,
            "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
        }, indent=2)
