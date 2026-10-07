"""Migration 001: Gmail retry receipts and source identity uniqueness.

Run with python -m db.migrate_gmail_ingestion. Existing data is preserved.
Re-running is safe; duplicate identities stop the migration for review.
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError

from src.db.schema import GmailIngestion, SourceDocument, SourceRevision
from src.services.gmail_connection import _engine


async def migrate(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: GmailIngestion.__table__.create(sync, checkfirst=True))
        for table in (SourceDocument.__table__, SourceRevision.__table__):
            for index in table.indexes:
                if index.name in {"uq_source_provider_identity", "uq_source_revision_number"}:
                    await connection.run_sync(lambda sync, index=index: index.create(sync, checkfirst=True))


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    engine = _engine()
    try:
        await migrate(engine)
    except IntegrityError:
        raise SystemExit("Migration 001 stopped: duplicate source identities or revision numbers need review.") from None
    finally:
        await engine.dispose()
    print("Migration 001 applied: Gmail ingestion receipts and uniqueness indexes are ready.")


if __name__ == "__main__":
    asyncio.run(main())
