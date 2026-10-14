"""Migration 002: replace canvas-era planning tables with the task-list schema.

The first planning tables (``tasks`` with effort/remaining columns,
``planning_preferences`` with session/limit/timezone columns, ``study_sessions``,
and ``availability_windows``) came from the original canvas design. The planning
model is now a task list with a selected day, list position, tags, and steps, so
the obsolete tables must be removed before ``tasks`` and ``planning_preferences``
are recreated with their current columns.

Run with ``python -m db.migrate_planning_schema``. Existing rows in the obsolete
planning tables stop the migration for review; academic, source, and change data
are never touched. Re-running is safe.
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.db.schema import Base
from src.services.gmail_connection import _engine


# Tables from the canvas design that are no longer part of the schema. They hold
# no student data in the current system and are dropped when empty.
OBSOLETE_TABLES = ("study_sessions", "availability_windows")


async def _table_exists(engine: AsyncEngine, table: str) -> bool:
    async with engine.connect() as connection:
        found = await connection.scalar(
            text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
        )
        return found is not None


async def _has_column(engine: AsyncEngine, table: str, column: str) -> bool:
    async with engine.connect() as connection:
        found = await connection.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        )
        return found is not None


async def _row_count(engine: AsyncEngine, table: str) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text(f'SELECT count(*) FROM "{table}"')) or 0)


async def migrate(engine: AsyncEngine) -> list[str]:
    """Drop empty legacy planning tables and recreate the current schema."""
    actions: list[str] = []

    # ``selected_day`` identifies the current task-list schema; its absence on an
    # existing ``tasks`` table means the table came from the canvas design.
    if await _table_exists(engine, "tasks") and not await _has_column(engine, "tasks", "selected_day"):
        if await _row_count(engine, "tasks") > 0:
            raise RuntimeError(
                "tasks holds rows in the old canvas shape; export them before migrating."
            )
        actions.append("tasks")

    if (
        await _table_exists(engine, "planning_preferences")
        and not await _has_column(engine, "planning_preferences", "scope")
    ):
        if await _row_count(engine, "planning_preferences") > 0:
            raise RuntimeError(
                "planning_preferences holds rows in the old canvas shape; export them before migrating."
            )
        actions.append("planning_preferences")

    for table in OBSOLETE_TABLES:
        if await _table_exists(engine, table):
            if await _row_count(engine, table) > 0:
                raise RuntimeError(f"{table} holds rows; export them before migrating.")
            actions.append(table)

    async with engine.begin() as connection:
        for table in actions:
            await connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        await connection.run_sync(Base.metadata.create_all)

    return actions


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    engine = _engine()
    try:
        dropped = await migrate(engine)
    finally:
        await engine.dispose()
    if dropped:
        print(f"Migration 002 applied: dropped {', '.join(dropped)} and recreated the planning tables.")
    else:
        print("Migration 002 applied: planning tables already match the current schema.")


if __name__ == "__main__":
    asyncio.run(main())
