"""Student planning preferences service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from src.db.schema import PlanningPreferences
from src.db.session import get_session


@dataclass(frozen=True)
class PreferencesView:
    preferred_daily_minutes: int | None
    focus_task_count: int | None
    updated_at: datetime | None


async def get_preferences(scope: str = "default") -> PreferencesView:
    """Retrieve the student's planning preferences for the given scope."""
    async with get_session() as session:
        pref = await session.scalar(
            select(PlanningPreferences).where(PlanningPreferences.scope == scope).limit(1)
        )
        if pref is None:
            return PreferencesView(
                preferred_daily_minutes=None,
                focus_task_count=None,
                updated_at=None,
            )
        return PreferencesView(
            preferred_daily_minutes=pref.preferred_daily_minutes,
            focus_task_count=pref.focus_task_count,
            updated_at=pref.updated_at,
        )


async def set_preferences(
    preferred_daily_minutes: int | None = None,
    focus_task_count: int | None = None,
    scope: str = "default",
    clear_preferred_daily_minutes: bool = False,
    clear_focus_task_count: bool = False,
) -> PreferencesView:
    """Upsert planning defaults for the single student scope.

    A non-null value replaces the stored default. A null value only clears
    the field when its matching ``clear_*`` flag is sent, so a caller can
    distinguish "leave this field alone" from "remove this default".
    """
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            pref = await session.scalar(
                select(PlanningPreferences).where(PlanningPreferences.scope == scope).with_for_update().limit(1)
            )
            now = datetime.now(timezone.utc)
            if pref is None:
                pref = PlanningPreferences(
                    id=uuid4(),
                    scope=scope,
                    preferred_daily_minutes=None if clear_preferred_daily_minutes else preferred_daily_minutes,
                    focus_task_count=None if clear_focus_task_count else focus_task_count,
                    updated_at=now,
                )
                session.add(pref)
            else:
                if clear_preferred_daily_minutes:
                    pref.preferred_daily_minutes = None
                elif preferred_daily_minutes is not None:
                    pref.preferred_daily_minutes = preferred_daily_minutes
                if clear_focus_task_count:
                    pref.focus_task_count = None
                elif focus_task_count is not None:
                    pref.focus_task_count = focus_task_count
                pref.updated_at = now

            await session.flush()

        return PreferencesView(
            preferred_daily_minutes=pref.preferred_daily_minutes,
            focus_task_count=pref.focus_task_count,
            updated_at=pref.updated_at,
        )
