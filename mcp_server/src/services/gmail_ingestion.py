"""Persist Gmail sources and drain durable extraction work without losing mail."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.schema import GmailIngestion, SourceConnection, SourceDocument, SourceRevision
from src.ingestion.gmail_source import EmailIntakeError, message_headers, prepare_gmail_source
from src.services.gmail_connection import _engine
from src.services.source_processing import ProcessingResult, process_source_revision

PROCESSING_TIMEOUT_SECONDS = 120
RETRY_STATUSES = ("pending", "failed", "pending_configuration", "processing", "blocked")


@dataclass(frozen=True)
class GmailIntakeResult:
    message_id: str
    status: str
    source_document_id: UUID | None = None
    source_revision_id: UUID | None = None
    created_revision: bool = False


@dataclass(frozen=True)
class GmailProcessingOutcome:
    message_id: str
    source_revision_id: UUID
    status: str
    academic_item_ids: list[UUID]
    review_count: int


async def ingest_gmail_message(connection_id: UUID, message_id: str, payload: dict) -> GmailIntakeResult:
    engine = _engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                return await _ingest_in_transaction(session, connection_id, message_id, payload)
    finally:
        await engine.dispose()


async def _ingest_in_transaction(
    session: AsyncSession, connection_id: UUID, message_id: str, payload: dict,
) -> GmailIntakeResult:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", message_id):
        raise ValueError("Invalid Gmail message identity.")
    # Serialize source creation for this account, including the first delivery.
    connection = await session.scalar(select(SourceConnection).where(
        SourceConnection.id == connection_id, SourceConnection.source_type == "gmail",
    ).with_for_update())
    if connection is None or connection.status != "connected":
        raise PermissionError("Gmail connection is unavailable.")
    now = datetime.now(timezone.utc)
    receipt = await session.get(GmailIngestion, (connection_id, message_id))
    sender = ""
    try:
        external_id, sender, _ = message_headers(payload)
        if external_id != message_id:
            raise EmailIntakeError("message_identity_mismatch")
        if sender not in connection.allowed_senders:
            return GmailIntakeResult(message_id, "skipped_sender")
        envelope = prepare_gmail_source(connection_id, payload, observed_at=now)
    except EmailIntakeError as exc:
        if receipt is None:
            receipt = GmailIngestion(
                connection_id=connection_id, message_id=message_id, source_revision_id=None,
                sender=sender, attempt_count=0,
            )
            session.add(receipt)
        # A malformed re-fetch cannot erase a previously saved valid revision.
        if receipt.source_revision_id is None:
            receipt.status = "rejected"
            receipt.error_code = exc.code
            receipt.next_attempt_at = now
        receipt.observed_at = now
        await session.flush()
        return GmailIntakeResult(message_id, "rejected", source_revision_id=receipt.source_revision_id)

    document = await session.scalar(select(SourceDocument).where(
        SourceDocument.connection_id == connection_id,
        SourceDocument.source_type == "gmail", SourceDocument.external_id == message_id,
    ).with_for_update())
    if document is None:
        document = SourceDocument(
            id=uuid4(), connection_id=connection_id, source_type="gmail", external_id=message_id,
            original_ref=envelope.original_ref, title=envelope.title, course_hint=None,
            source_updated_at=envelope.source_updated_at, last_seen_at=now,
        )
        session.add(document)
        await session.flush()
    else:
        document.last_seen_at = now
        document.title = envelope.title
        document.source_updated_at = envelope.source_updated_at
    latest = await session.scalar(select(SourceRevision).where(
        SourceRevision.source_document_id == document.id,
    ).order_by(SourceRevision.revision_no.desc()).limit(1))
    content_hash = sha256(envelope.clean_text.encode("utf-8")).hexdigest()
    created = latest is None or latest.content_hash != content_hash
    if created:
        latest = SourceRevision(
            id=uuid4(), source_document_id=document.id,
            revision_no=1 if latest is None else latest.revision_no + 1,
            content_hash=content_hash, raw_content=None, clean_text=envelope.clean_text,
            source_updated_at=envelope.source_updated_at, observed_at=now,
        )
        session.add(latest)
        await session.flush()
    if receipt is None:
        receipt = GmailIngestion(connection_id=connection_id, message_id=message_id)
        session.add(receipt)
    if receipt.source_revision_id != latest.id:
        receipt.source_revision_id = latest.id
        receipt.status = "pending"
        receipt.error_code = None
        receipt.attempt_count = 0
        receipt.next_attempt_at = now
    receipt.sender = sender
    receipt.observed_at = now
    await session.flush()
    return GmailIntakeResult(message_id, receipt.status, document.id, latest.id, created)


async def process_pending_gmail(
    connection_id: UUID, *, limit: int = 10, processor=process_source_revision,
) -> list[GmailProcessingOutcome]:
    """Claim short leases; publish through the shared service; retry safe failures."""
    if not 1 <= limit <= 50:
        raise ValueError("Processing batch must contain 1–50 messages.")
    engine = _engine()
    outcomes: list[GmailProcessingOutcome] = []
    try:
        # Claim one at a time so later messages do not outlive a lease while waiting.
        for _ in range(limit):
            async with AsyncSession(engine, expire_on_commit=False) as session:
                async with session.begin():
                    connection = await session.get(SourceConnection, connection_id)
                    if connection is None or connection.status != "connected" or not connection.allowed_senders:
                        break
                    now = datetime.now(timezone.utc)
                    receipt = await session.scalar(select(GmailIngestion).where(
                        GmailIngestion.connection_id == connection_id,
                        GmailIngestion.sender.in_(connection.allowed_senders),
                        GmailIngestion.source_revision_id.is_not(None),
                        GmailIngestion.status.in_(RETRY_STATUSES),
                        GmailIngestion.next_attempt_at <= now,
                    ).order_by(GmailIngestion.next_attempt_at, GmailIngestion.message_id)
                        .limit(1).with_for_update(skip_locked=True))
                    if receipt is None:
                        break
                    receipt.status = "processing"
                    receipt.attempt_count += 1
                    receipt.next_attempt_at = now + timedelta(seconds=PROCESSING_TIMEOUT_SECONDS + 60)
                    message_id, revision_id, attempt = receipt.message_id, receipt.source_revision_id, receipt.attempt_count
            error_code = None
            try:
                result = await asyncio.wait_for(processor(revision_id), timeout=PROCESSING_TIMEOUT_SECONDS)
            except TimeoutError:
                result, error_code = ProcessingResult("failed", []), "processing_timeout"
            except Exception:
                result, error_code = ProcessingResult("failed", []), "processing_failed"
            async with AsyncSession(engine) as session:
                async with session.begin():
                    receipt = await session.get(GmailIngestion, (connection_id, message_id), with_for_update=True)
                    if receipt.source_revision_id != revision_id or receipt.attempt_count != attempt:
                        continue
                    now = datetime.now(timezone.utc)
                    if result.status in {"processed", "already_processed", "superseded"}:
                        receipt.status = "processed" if result.status != "superseded" else "superseded"
                        receipt.error_code = None
                    elif result.status == "pending_configuration":
                        receipt.status, receipt.error_code = "pending_configuration", "extraction_not_configured"
                        receipt.attempt_count = max(0, attempt - 1)
                        receipt.next_attempt_at = now + timedelta(seconds=60)
                    elif result.status == "scope_changed":
                        receipt.status, receipt.error_code = "blocked", "sender_scope_changed"
                        receipt.next_attempt_at = now + timedelta(seconds=60)
                    else:
                        receipt.status, receipt.error_code = "failed", error_code or "extraction_failed"
                        receipt.next_attempt_at = now + timedelta(seconds=min(3600, 60 * 2 ** min(attempt, 6)))
            outcomes.append(GmailProcessingOutcome(
                message_id, revision_id, result.status, result.academic_item_ids, result.review_count,
            ))
    finally:
        await engine.dispose()
    return outcomes
