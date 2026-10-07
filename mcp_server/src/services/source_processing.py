"""Turn an immutable source revision into accepted academic facts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.db.schema import (
    AcademicItem, AcademicItemChange, SourceDocument, SourceItemLink, SourceConnection, GmailIngestion,
    SourceProcessingRun, SourceRevision,
)
from src.ingestion.extraction import NormalizedCandidate, extract_academic_candidates


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    academic_item_ids: list[UUID]
    review_count: int = 0


@dataclass(frozen=True)
class SourceCandidateView:
    id: UUID
    source_revision_id: UUID
    academic_item_id: UUID | None
    evidence: dict
    review_reasons: list[str]
    date_facts: dict


async def list_latest_source_candidates(document_id: UUID) -> list[SourceCandidateView] | None:
    """Read at most the latest revision's twelve extracted candidates."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to read source candidates.")
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
    engine = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    try:
        async with AsyncSession(engine) as session:
            document = await session.get(SourceDocument, document_id)
            if document is None or document.source_type not in {"text", "html", "pdf", "gmail"}:
                return None
            latest_id = await session.scalar(
                select(SourceRevision.id).where(SourceRevision.source_document_id == document_id)
                .order_by(SourceRevision.revision_no.desc()).limit(1)
            )
            rows = (await session.scalars(
                select(SourceItemLink).where(
                    SourceItemLink.source_document_id == document_id,
                    SourceItemLink.source_revision_id == latest_id,
                ).order_by(SourceItemLink.id).limit(12)
            )).all()
            return [SourceCandidateView(
                id=link.id, source_revision_id=link.source_revision_id,
                academic_item_id=link.academic_item_id, evidence=link.evidence,
                review_reasons=link.review_reasons, date_facts=link.date_facts,
            ) for link in rows]
    finally:
        await engine.dispose()


def _source_key(candidate: NormalizedCandidate) -> str:
    label = candidate.identity or candidate.title
    normalized = re.sub(r"\s+", " ", label.casefold()).strip()
    return sha256(f"{candidate.item_type}:{normalized}".encode("utf-8")).hexdigest()


def _fields(candidate: NormalizedCandidate) -> dict:
    return {
        "item_type": candidate.item_type,
        "title": candidate.title,
        "details": candidate.details,
        "starts_at": candidate.starts_at,
        "due_at": candidate.due_at,
        "grade_weight_percent": candidate.grade_weight_percent,
        "late_penalty": candidate.late_penalty,
        "review_state": (
            "conflicting" if any("conflict" in reason.casefold() for reason in candidate.review_reasons)
            else "uncertain" if candidate.review_reasons else "verified"
        ),
    }


def _json_values(values: dict) -> dict:
    return {key: value.isoformat() if isinstance(value, datetime) else
            str(value) if value is not None and key == "grade_weight_percent" else value
            for key, value in values.items()}


async def _record_failure(engine, revision_id: UUID, error_code: str, started_at: datetime) -> None:
    async with AsyncSession(engine) as session:
        async with session.begin():
            session.add(SourceProcessingRun(
                id=uuid4(), source_revision_id=revision_id, status="failed",
                error_code=error_code, item_count=0, started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            ))


async def _source_authorized(session: AsyncSession, document: SourceDocument, revision_id: UUID) -> bool:
    if document.source_type != "gmail":
        return True
    connection = await session.get(SourceConnection, document.connection_id)
    receipt = await session.get(GmailIngestion, (document.connection_id, document.external_id))
    return bool(connection and connection.status == "connected" and receipt
                and receipt.source_revision_id == revision_id
                and receipt.sender in connection.allowed_senders)


async def process_source_revision(revision_id: UUID) -> ProcessingResult:
    """Extract outside the transaction; atomically publish the resulting facts."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to process source text.")
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
    engine = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    started_at = datetime.now(timezone.utc)
    try:
        async with AsyncSession(engine) as session:
            revision = await session.get(SourceRevision, revision_id)
            if revision is None:
                raise ValueError("Source revision was not found.")
            document = await session.get(SourceDocument, revision.source_document_id)
            if document is None or document.source_type not in {"text", "html", "pdf", "gmail"}:
                raise ValueError("Supported source was not found.")
            if not await _source_authorized(session, document, revision_id):
                return ProcessingResult("scope_changed", [])
            successful = await session.scalar(
                select(SourceProcessingRun.id).where(
                    SourceProcessingRun.source_revision_id == revision_id,
                    SourceProcessingRun.status == "processed",
                ).limit(1)
            )
            if successful:
                ids = list((await session.scalars(
                    select(SourceItemLink.academic_item_id).where(
                        SourceItemLink.source_document_id == document.id,
                        SourceItemLink.source_revision_id == revision_id,
                        SourceItemLink.academic_item_id.is_not(None),
                    )
                )).all())
                return ProcessingResult("already_processed", ids)
            clean_text, title, document_id = revision.clean_text, document.title or "Pasted text", document.id

        if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "API_KEY":
            return ProcessingResult("pending_configuration", [])

        try:
            candidates = await extract_academic_candidates(clean_text, title)
        except Exception:
            await _record_failure(engine, revision_id, "extraction_failed", started_at)
            return ProcessingResult("failed", [])

        async with AsyncSession(engine) as session:
            async with session.begin():
                # Use the same account -> document lock order as Gmail intake.
                # Scope changes cannot race the final authorization and commit.
                if document.source_type == "gmail":
                    await session.scalar(select(SourceConnection).where(
                        SourceConnection.id == document.connection_id,
                    ).with_for_update())
                document = await session.scalar(
                    select(SourceDocument).where(SourceDocument.id == document_id).with_for_update()
                )
                latest_id = await session.scalar(
                    select(SourceRevision.id).where(SourceRevision.source_document_id == document_id)
                    .order_by(SourceRevision.revision_no.desc()).limit(1)
                )
                if latest_id != revision_id:
                    return ProcessingResult("superseded", [])
                if not await _source_authorized(session, document, revision_id):
                    return ProcessingResult("scope_changed", [])
                successful = await session.scalar(
                    select(SourceProcessingRun.id).where(
                        SourceProcessingRun.source_revision_id == revision_id,
                        SourceProcessingRun.status == "processed",
                    ).limit(1)
                )
                if successful:
                    return ProcessingResult("already_processed", [])
                result = await _persist_candidates(
                    session, document_id, revision_id, candidates,
                    conservative_identity=document.source_type == "gmail",
                )
                session.add(SourceProcessingRun(
                    id=uuid4(), source_revision_id=revision_id, status="processed",
                    error_code=None, item_count=len(result.academic_item_ids),
                    started_at=started_at, finished_at=datetime.now(timezone.utc),
                ))
                return result
    finally:
        await engine.dispose()


async def _persist_candidates(
    session: AsyncSession, document_id: UUID, revision_id: UUID,
    candidates: list[NormalizedCandidate],
    *, conservative_identity: bool = False,
) -> ProcessingResult:
    """Called inside the document lock and caller's transaction."""
    now = datetime.now(timezone.utc)
    keys = [_source_key(candidate) for candidate in candidates]
    duplicates = Counter(keys)
    existing = {
        link.source_key: link for link in (await session.scalars(
            select(SourceItemLink).where(SourceItemLink.source_document_id == document_id)
        )).all()
    }
    had_prior_items = any(link.academic_item_id and link.source_revision_id != revision_id
                          for link in existing.values())
    item_ids: list[UUID] = []
    review_count = 0
    for index, candidate in enumerate(candidates):
        base_key = keys[index]
        duplicate = duplicates[base_key] > 1
        key = f"{base_key}:duplicate:{index}" if duplicate else base_key
        reasons = list(candidate.review_reasons)
        if duplicate:
            reasons.append("Identity collides with another item in this source")
        publishable = candidate.publishable and not duplicate
        link = existing.get(key)
        if conservative_identity and had_prior_items and (link is None or link.academic_item_id is None):
            publishable = False
            reasons.append("Changed source item identity needs review before creating or replacing a fact")
        prior_evidence = dict(link.evidence) if link else {}
        prior_dates = dict(link.date_facts) if link else {}
        prior_revision_id = link.source_revision_id if link else None
        prior_item = await session.get(AcademicItem, link.academic_item_id) if link and link.academic_item_id else None
        evidence = dict(candidate.evidence)
        for field, quote in candidate.evidence.items():
            if quote:
                evidence[f"{field}_revision_id"] = str(revision_id)
        date_facts = {
            field: {**fact, "revision_id": str(revision_id) if fact["value"] else None}
            for field, fact in candidate.date_facts.items()
        }
        if prior_item is not None:
            for field in ("details", "starts_at", "due_at", "grade_weight_percent", "late_penalty"):
                if getattr(prior_item, field) is not None and getattr(candidate, field) is None:
                    evidence[field] = prior_evidence.get(field)
                    evidence[f"{field}_revision_id"] = prior_evidence.get(
                        f"{field}_revision_id", str(prior_revision_id)
                    )
                    if field in date_facts:
                        if date_facts[field]["value"]:
                            date_facts[f"proposed_{field}"] = date_facts[field]
                        date_facts[field] = prior_dates.get(field, {
                            "value": getattr(prior_item, field).isoformat(),
                            "precision": "datetime", "wording": prior_evidence.get(field),
                            "revision_id": str(prior_revision_id),
                        })
                    reasons.append(f"{field}: last accepted value retained pending review")
        if reasons or not publishable:
            review_count += 1
        if link is None:
            link = SourceItemLink(
                id=uuid4(), source_document_id=document_id, source_key=key,
                academic_item_id=None, source_revision_id=revision_id,
                evidence=evidence, review_reasons=reasons,
                date_facts=date_facts,
            )
            session.add(link)
            existing[key] = link
        else:
            link.source_revision_id = revision_id
            link.evidence = evidence
            link.review_reasons = reasons
            link.date_facts = date_facts

        if not publishable:
            if prior_item is not None:
                state = "conflicting" if any("conflict" in reason.casefold() for reason in reasons) else "uncertain"
                if prior_item.review_state != state:
                    before_state = prior_item.review_state
                    prior_item.review_state = state
                    prior_item.updated_at = now
                    session.add(AcademicItemChange(
                        id=uuid4(), academic_item_id=prior_item.id, source_revision_id=revision_id,
                        origin="source_extraction", change_kind="edited",
                        before_values={"review_state": before_state},
                        after_values={"review_state": state}, recorded_at=now,
                    ))
            continue
        values = _fields(candidate)
        if reasons:
            values["review_state"] = "conflicting" if any(
                "conflict" in reason.casefold() for reason in reasons
            ) else "uncertain"
        item = prior_item
        if item is None:
            item = AcademicItem(
                id=uuid4(), course_id=None, source_revision_id=revision_id,
                created_at=now, updated_at=now, **values,
            )
            session.add(item)
            link.academic_item_id = item.id
            session.add(AcademicItemChange(
                id=uuid4(), academic_item_id=item.id, source_revision_id=revision_id,
                origin="source_extraction", change_kind="created", before_values=None,
                after_values=_json_values(values), recorded_at=now,
            ))
        else:
            before = {}
            after = {}
            for field, value in values.items():
                old = getattr(item, field)
                # A missing or uncertain new value cannot erase a previously accepted fact.
                if old is not None and value is None:
                    continue
                if old != value:
                    before[field] = old
                    after[field] = value
                    setattr(item, field, value)
            item.source_revision_id = revision_id
            if after:
                item.updated_at = now
                session.add(AcademicItemChange(
                    id=uuid4(), academic_item_id=item.id, source_revision_id=revision_id,
                    origin="source_extraction", change_kind="edited",
                    before_values=_json_values(before), after_values=_json_values(after),
                    recorded_at=now,
                ))
        item_ids.append(item.id)
    await session.flush()
    return ProcessingResult("processed", item_ids, review_count)
