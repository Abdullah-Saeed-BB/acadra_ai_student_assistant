"""Comprehensive integration tests for Study Planner FastMCP server tools and resources."""

import asyncio
from datetime import date, datetime, timedelta, timezone
import json
import unittest
from uuid import UUID, uuid4

from dotenv import load_dotenv

# Load env before importing server
load_dotenv()

from sqlalchemy import delete

from src.db.schema import (
    AcademicItem,
    AcademicItemChange,
    Course,
    SourceDocument,
    SourceItemLink,
    SourceRevision,
    Task,
)
from src.db.session import get_session
from src.server import mcp


def parse_result(res):
    if hasattr(res, "isError"):
        return res.isError, json.loads(res.content[0].text)
    # List of TextContent from success call
    return False, json.loads(res[0].text)


class TestStudyPlannerMCPServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = mcp

    async def test_tool_listing(self):
        tools = await self.server.list_tools()
        names = {t.name for t in tools}
        expected = {
            "study_add_manual_text",
            "study_list_academic_items",
            "study_get_academic_item",
            "study_get_academic_item_evidence",
            "study_review_academic_item",
            "study_get_changes_since",
            "study_list_sources",
            "study_get_source_detail",
            "study_list_source_candidates",
            "study_list_courses",
            "study_get_course",
            "study_list_tasks",
            "study_get_task",
            "study_create_task",
            "study_update_task",
            "study_move_task",
            "study_reorder_tasks",
            "study_complete_task",
            "study_split_task",
            "study_get_today_plan",
            "study_get_upcoming_plan",
            "study_get_backlog",
            "study_get_plan_board",
            "study_get_preferences",
            "study_set_preferences",
            "study_get_gmail_connection",
            "study_set_gmail_senders",
        }
        self.assertTrue(expected.issubset(names), f"Missing tools: {expected - names}")

    async def test_preferences_lifecycle(self):
        # 1. Set preferences
        res = await self.server.call_tool(
            "study_set_preferences",
            {"preferred_daily_minutes": 150, "focus_task_count": 4},
        )
        is_err, data = parse_result(res)
        self.assertFalse(is_err)
        self.assertEqual(data["preferred_daily_minutes"], 150)
        self.assertEqual(data["focus_task_count"], 4)

        # 2. Get preferences
        res_get = await self.server.call_tool("study_get_preferences", {})
        is_err, data_get = parse_result(res_get)
        self.assertFalse(is_err)
        self.assertEqual(data_get["preferred_daily_minutes"], 150)
        self.assertEqual(data_get["focus_task_count"], 4)

        # 3. Read resource
        res_content = await self.server.read_resource("study://preferences")
        data_res = json.loads(res_content[0].content)
        self.assertEqual(data_res["preferred_daily_minutes"], 150)

    async def test_tasks_lifecycle(self):
        today = date.today()
        unique_tag = f"lifecycle-{uuid4().hex[:8]}"

        # 1. Create a dated task
        res_t1 = await self.server.call_tool(
            "study_create_task",
            {
                "title": "Complete Math Assignment 1",
                "details": "Solve exercises 1 to 10",
                "selected_day": today.isoformat(),
                "estimated_minutes": 60,
                "tags": ["math", "homework", unique_tag],
            },
        )
        is_err, t1 = parse_result(res_t1)
        self.assertFalse(is_err)
        t1_id = t1["id"]
        self.assertEqual(t1["title"], "Complete Math Assignment 1")
        self.assertEqual(t1["selected_day"], today.isoformat())
        self.assertEqual(t1["estimated_minutes"], 60)

        # 2. Create a backlog task
        res_t2 = await self.server.call_tool(
            "study_create_task",
            {
                "title": "Read Physics Chapter 3",
                "estimated_minutes": 45,
                "tags": [unique_tag],
            },
        )
        is_err, t2 = parse_result(res_t2)
        self.assertFalse(is_err)
        t2_id = t2["id"]
        self.assertIsNone(t2["selected_day"])

        # 3. List tasks
        res_list = await self.server.call_tool(
            "study_list_tasks",
            {"status": "todo", "tag": unique_tag, "limit": 10},
        )
        is_err, paged = parse_result(res_list)
        self.assertFalse(is_err)
        task_ids = [item["id"] for item in paged["items"]]
        self.assertIn(t1_id, task_ids)
        self.assertIn(t2_id, task_ids)

        # 4. Get single task
        res_get = await self.server.call_tool("study_get_task", {"task_id": t1_id})
        is_err, detail = parse_result(res_get)
        self.assertFalse(is_err)
        self.assertEqual(detail["id"], t1_id)
        self.assertEqual(detail["progress"]["total_steps"], 0)

        # 5. Split task into steps
        res_split = await self.server.call_tool(
            "study_split_task",
            {
                "task_id": t1_id,
                "steps": [
                    {"title": "Step 1: Questions 1-5", "estimated_minutes": 30},
                    {"title": "Step 2: Questions 6-10", "estimated_minutes": 30},
                ],
            },
        )
        is_err, split_data = parse_result(res_split)
        self.assertFalse(is_err)
        self.assertEqual(len(split_data["steps"]), 2)

        # Check steps in get_task
        res_get2 = await self.server.call_tool("study_get_task", {"task_id": t1_id})
        is_err, detail2 = parse_result(res_get2)
        self.assertFalse(is_err)
        self.assertEqual(detail2["progress"]["total_steps"], 2)
        self.assertEqual(detail2["progress"]["unfinished_steps"], 2)

        # 6. Complete task
        res_done = await self.server.call_tool(
            "study_complete_task",
            {"task_id": t1_id, "done": True},
        )
        is_err, t1_done = parse_result(res_done)
        self.assertFalse(is_err)
        self.assertEqual(t1_done["status"], "done")
        self.assertIsNotNone(t1_done["completed_at"])

        # 7. Move backlog task to tomorrow
        tomorrow = today + timedelta(days=1)
        res_move = await self.server.call_tool(
            "study_move_task",
            {"task_id": t2_id, "selected_day": tomorrow.isoformat()},
        )
        is_err, t2_moved = parse_result(res_move)
        self.assertFalse(is_err)
        self.assertEqual(t2_moved["selected_day"], tomorrow.isoformat())

        # 8. Today plan
        res_plan = await self.server.call_tool(
            "study_get_today_plan",
            {"day": today.isoformat()},
        )
        is_err, today_plan = parse_result(res_plan)
        self.assertFalse(is_err)
        self.assertEqual(today_plan["day"], today.isoformat())

        # 9. Upcoming plan
        res_up = await self.server.call_tool(
            "study_get_upcoming_plan",
            {"days": 7, "start_day": today.isoformat()},
        )
        is_err, upcoming = parse_result(res_up)
        self.assertFalse(is_err)
        self.assertEqual(len(upcoming["days"]), 7)

        # 10. Backlog
        res_backlog = await self.server.call_tool("study_get_backlog", {})
        is_err, backlog_data = parse_result(res_backlog)
        self.assertFalse(is_err)

        # 11. Plan board
        res_board = await self.server.call_tool("study_get_plan_board", {"days": 7})
        is_err, board = parse_result(res_board)
        self.assertFalse(is_err)
        self.assertEqual(len(board["columns"]), 7)

        # Cleanup: remove the split steps, then the parents, to keep the suite repeatable.
        async with get_session(expire_on_commit=False) as session:
            async with session.begin():
                await session.execute(delete(Task).where(Task.parent_task_id == UUID(t1_id)))
                await session.execute(delete(Task).where(Task.id.in_([UUID(t1_id), UUID(t2_id)])))

    async def test_courses_and_academic_items(self):
        # 1. Insert test course
        course_id = uuid4()
        now = datetime.now(timezone.utc)
        async with get_session(expire_on_commit=False) as session:
            async with session.begin():
                course = Course(
                    id=course_id,
                    code="CS101",
                    name="Intro to Computer Science",
                    term="Fall 2026",
                    created_at=now,
                )
                session.add(course)
                # Flush the course before its item: without an ORM relationship
                # SQLAlchemy does not order the two inserts by foreign key.
                await session.flush()

                # Add academic item
                item_id = uuid4()
                item = AcademicItem(
                    id=item_id,
                    course_id=course_id,
                    source_revision_id=None,
                    item_type="assignment",
                    title="Project 1: Shell",
                    details="Build a basic shell",
                    starts_at=now,
                    due_at=now + timedelta(days=5),
                    grade_weight_percent=15,
                    late_penalty="10% per day",
                    review_state="uncertain",
                    created_at=now,
                    updated_at=now,
                )
                session.add(item)
                await session.flush()

        # 2. List courses tool
        res_courses = await self.server.call_tool("study_list_courses", {})
        is_err, courses_data = parse_result(res_courses)
        self.assertFalse(is_err)
        found_course = any(c["id"] == str(course_id) for c in courses_data["items"])
        self.assertTrue(found_course)

        # 3. Get single course tool
        res_course = await self.server.call_tool("study_get_course", {"course_id": str(course_id)})
        is_err, course_detail = parse_result(res_course)
        self.assertFalse(is_err)
        self.assertEqual(course_detail["code"], "CS101")
        self.assertEqual(len(course_detail["academic_items"]), 1)

        # 4. List academic items
        res_items = await self.server.call_tool(
            "study_list_academic_items",
            {"course_id": str(course_id)},
        )
        is_err, items_page = parse_result(res_items)
        self.assertFalse(is_err)
        self.assertEqual(len(items_page["items"]), 1)
        self.assertEqual(items_page["items"][0]["id"], str(item_id))

        # 5. Get academic item detail
        res_item = await self.server.call_tool(
            "study_get_academic_item",
            {"item_id": str(item_id)},
        )
        is_err, item_data = parse_result(res_item)
        self.assertFalse(is_err)
        self.assertEqual(item_data["title"], "Project 1: Shell")
        self.assertEqual(item_data["course"]["code"], "CS101")

        # 6. Review academic item (correct)
        res_review = await self.server.call_tool(
            "study_review_academic_item",
            {
                "item_id": str(item_id),
                "action": "correct",
                "fields": {"title": "Project 1: Advanced Shell", "late_penalty": "5% per day"},
                "note": "Updated title per professor announcement",
            },
        )
        is_err, review_data = parse_result(res_review)
        self.assertFalse(is_err)
        self.assertEqual(review_data["item"]["title"], "Project 1: Advanced Shell")
        self.assertEqual(review_data["item"]["review_state"], "verified")
        self.assertIn("change", review_data)
        self.assertEqual(review_data["change"]["origin"], "student_correction")

        # 7. Check change feed
        res_changes = await self.server.call_tool("study_get_changes_since", {})
        is_err, changes_data = parse_result(res_changes)
        self.assertFalse(is_err)
        self.assertGreater(len(changes_data["items"]), 0)

        # Cleanup: changes reference the item, so remove them first.
        async with get_session(expire_on_commit=False) as session:
            async with session.begin():
                await session.execute(delete(AcademicItemChange).where(AcademicItemChange.academic_item_id == item_id))
                await session.execute(delete(AcademicItem).where(AcademicItem.id == item_id))
                await session.execute(delete(Course).where(Course.id == course_id))

    async def test_academic_item_date_bounds(self):
        # Regression: "What's due this week" answers arrive as date-only bounds.
        # The tool must accept them instead of failing schema validation.
        today = date.today()
        res = await self.server.call_tool(
            "study_list_academic_items",
            {"due_from": today.isoformat(), "due_before": (today + timedelta(days=7)).isoformat()},
        )
        is_err, page = parse_result(res)
        self.assertFalse(is_err)
        self.assertIn("items", page)

        # Full date-times with an offset and naive date-times still work.
        for due_from, due_before in (
            ("2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
            ("2026-01-01T00:00:00", "2027-01-01T00:00:00"),
        ):
            res = await self.server.call_tool(
                "study_list_academic_items",
                {"due_from": due_from, "due_before": due_before},
            )
            is_err, _ = parse_result(res)
            self.assertFalse(is_err)

        # Unparseable bounds return a structured invalid_input error, not a crash.
        res = await self.server.call_tool("study_list_academic_items", {"due_from": "next week"})
        is_err, err = parse_result(res)
        self.assertTrue(is_err)
        self.assertEqual(err["error"]["code"], "invalid_input")

        # The change feed accepts a date-only "since" too.
        res = await self.server.call_tool(
            "study_get_changes_since",
            {"since": (today - timedelta(days=1)).isoformat()},
        )
        is_err, _ = parse_result(res)
        self.assertFalse(is_err)

    async def test_error_handling(self):
        # 1. Invalid UUID
        res_bad_id = await self.server.call_tool("study_get_task", {"task_id": "not-a-uuid"})
        is_err, err1 = parse_result(res_bad_id)
        self.assertTrue(is_err)
        self.assertEqual(err1["error"]["code"], "invalid_input")

        # 2. Not found UUID
        random_id = str(uuid4())
        res_not_found = await self.server.call_tool("study_get_task", {"task_id": random_id})
        is_err, err2 = parse_result(res_not_found)
        self.assertTrue(is_err)
        self.assertEqual(err2["error"]["code"], "not_found")

        # 3. Bad foreign key on task creation
        res_bad_fk = await self.server.call_tool(
            "study_create_task",
            {"title": "Step with bad parent", "parent_task_id": random_id},
        )
        is_err, err3 = parse_result(res_bad_fk)
        self.assertTrue(is_err)
        self.assertEqual(err3["error"]["code"], "not_found")

    async def test_sources_and_candidates(self):
        now = datetime.now(timezone.utc)
        doc_id = uuid4()
        rev_id = uuid4()
        item_id = uuid4()

        async with get_session(expire_on_commit=False) as session:
            async with session.begin():
                session.add(SourceDocument(
                    id=doc_id, connection_id=None, source_type="text",
                    external_id=None, original_ref="manual:test", title="Syllabus notes",
                    course_hint="CS101", source_updated_at=None, last_seen_at=now,
                ))
                await session.flush()
                session.add(SourceRevision(
                    id=rev_id, source_document_id=doc_id, revision_no=1, content_hash="abc123",
                    raw_content=None, clean_text="Homework due Friday.", source_updated_at=None,
                    observed_at=now,
                ))
                await session.flush()
                session.add(AcademicItem(
                    id=item_id, course_id=None, source_revision_id=rev_id, item_type="assignment",
                    title="Weekly homework", details="Chapter 4", starts_at=None,
                    due_at=now + timedelta(days=2), grade_weight_percent=None, late_penalty=None,
                    review_state="uncertain", created_at=now, updated_at=now,
                ))
                await session.flush()
                session.add(SourceItemLink(
                    id=uuid4(), source_document_id=doc_id, source_key="item-1",
                    academic_item_id=item_id, source_revision_id=rev_id,
                    evidence={"title": "Weekly homework"}, review_reasons=["due date is a guess"],
                    date_facts={"due_at": {"value": None, "precision": "date", "wording": "Friday"}},
                ))
                session.add(SourceItemLink(
                    id=uuid4(), source_document_id=doc_id, source_key="item-2",
                    academic_item_id=None, source_revision_id=rev_id,
                    evidence={"title": "Maybe a quiz"}, review_reasons=[], date_facts={},
                ))

        # study_list_sources finds the document and flags review candidates.
        res = await self.server.call_tool("study_list_sources", {"source_type": "text"})
        is_err, page = parse_result(res)
        self.assertFalse(is_err)
        mine = [i for i in page["items"] if i["id"] == str(doc_id)]
        self.assertEqual(len(mine), 1)
        self.assertTrue(mine[0]["has_review_candidates"])
        self.assertEqual(mine[0]["latest_revision_no"], 1)

        # study_get_source_detail lists the revision.
        res = await self.server.call_tool("study_get_source_detail", {"source_document_id": str(doc_id)})
        is_err, detail = parse_result(res)
        self.assertFalse(is_err)
        self.assertEqual(len(detail["revisions"]), 1)
        self.assertTrue(detail["has_review_candidates"])

        # Candidates include the withheld item (academic_item_id is null).
        res = await self.server.call_tool("study_list_source_candidates", {"source_document_id": str(doc_id)})
        is_err, cands = parse_result(res)
        self.assertFalse(is_err)
        self.assertEqual(len(cands["candidates"]), 2)
        self.assertTrue(any(c["academic_item_id"] is None for c in cands["candidates"]))

        # Evidence returns review reasons and date wording.
        res = await self.server.call_tool("study_get_academic_item_evidence", {"item_id": str(item_id)})
        is_err, evidence = parse_result(res)
        self.assertFalse(is_err)
        self.assertEqual(evidence["source_document_id"], str(doc_id))
        self.assertIn("due date is a guess", evidence["review_reasons"])

        # The matching resources resolve through the same services.
        content = await self.server.read_resource(f"study://sources/{doc_id}")
        self.assertIn("Syllabus notes", content[0].content)
        content = await self.server.read_resource(f"study://academic-items/{item_id}/evidence")
        self.assertIn("due date is a guess", content[0].content)

        # Cleanup in foreign-key order.
        async with get_session(expire_on_commit=False) as session:
            async with session.begin():
                await session.execute(delete(SourceItemLink).where(SourceItemLink.source_document_id == doc_id))
                await session.execute(delete(AcademicItem).where(AcademicItem.id == item_id))
                await session.execute(delete(SourceRevision).where(SourceRevision.id == rev_id))
                await session.execute(delete(SourceDocument).where(SourceDocument.id == doc_id))

    async def test_task_tag_filter_and_typed_steps(self):
        unique_tag = "edge-tag-" + uuid4().hex[:8]

        res = await self.server.call_tool(
            "study_create_task",
            {"title": "Tagged task", "tags": [unique_tag], "estimated_minutes": 20},
        )
        is_err, task = parse_result(res)
        self.assertFalse(is_err)
        task_id = task["id"]

        # Tag filtering matches the JSON tag array.
        res = await self.server.call_tool("study_list_tasks", {"tag": unique_tag})
        is_err, page = parse_result(res)
        self.assertFalse(is_err)
        self.assertEqual([i["id"] for i in page["items"]], [task_id])

        # Split accepts ISO date strings and coerces them; omitted days inherit the parent.
        res = await self.server.call_tool(
            "study_split_task",
            {
                "task_id": task_id,
                "steps": [
                    {"title": "Step one", "estimated_minutes": 10},
                    {"title": "Step two", "selected_day": "2026-12-01", "estimated_minutes": 10},
                ],
            },
        )
        is_err, split = parse_result(res)
        self.assertFalse(is_err)
        self.assertIsNone(split["steps"][0]["selected_day"])
        self.assertEqual(split["steps"][1]["selected_day"], "2026-12-01")

        # Cleanup: delete children before the parent.
        async with get_session(expire_on_commit=False) as session:
            async with session.begin():
                await session.execute(delete(Task).where(Task.parent_task_id == UUID(task_id)))
                await session.execute(delete(Task).where(Task.id == UUID(task_id)))

    async def test_operator_tools(self):
        res_conn = await self.server.call_tool("study_get_gmail_connection", {})
        is_err, conn = parse_result(res_conn)
        self.assertFalse(is_err)
        self.assertIn("status", conn)

        # 2. Set gmail senders (normalized lowercase)
        res_senders = await self.server.call_tool(
            "study_set_gmail_senders",
            {"allowed_senders": ["Prof.Smith@University.EDU", "TA@COLLEGE.ORG"]},
        )
        is_err, senders_data = parse_result(res_senders)
        self.assertFalse(is_err)
        self.assertEqual(
            senders_data["allowed_senders"],
            ["prof.smith@university.edu", "ta@college.org"],
        )


if __name__ == "__main__":
    unittest.main()
