"""Create the PostgreSQL database and tables declared in src.db.schema."""

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.schema import Base


async def create_database_if_missing(url: URL) -> None:
    """CREATE DATABASE requires a connection to another database and autocommit."""
    maintenance_engine = create_async_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with maintenance_engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                quoted_name = maintenance_engine.sync_engine.dialect.identifier_preparer.quote_identifier(
                    url.database
                )
                await connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
                print(f"Database {url.database!r} created.")
    finally:
        await maintenance_engine.dispose()


async def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be set to a PostgreSQL connection URL.")

    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise SystemExit("DATABASE_URL must use postgresql:// or postgresql+asyncpg://.")
    url = url.set(drivername="postgresql+asyncpg")
    if not url.database:
        raise SystemExit("DATABASE_URL must include a database name.")

    await create_database_if_missing(url)

    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

    print("Database tables created (existing tables left unchanged).")


if __name__ == "__main__":
    asyncio.run(main())
