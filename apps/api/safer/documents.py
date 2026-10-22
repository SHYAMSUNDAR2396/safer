import base64
import hashlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from safer import filecheck
from safer.errors import Problem
from safer.instruments import assigned_case, scoped_instrument
from safer.models import Document, Obligation
from safer.scanning import scan_states
from safer.security import DB, Actor, Writer, audit

router = APIRouter(prefix="/api/v1")
MAX_DOCUMENTS = 20
LABELS = {
    "fdr_certificate": "FDR certificate",
    "bank_letter": "Bank covering letter",
    "other": "Other supporting document",
}
Kind = Literal["fdr_certificate", "bank_letter", "other"]


def current_ids(docs) -> set:
    """The latest non-failed upload of each required kind is current; every 'other' file is."""
    latest = {}
    for doc in docs:  # oldest first
        if doc.status != "failed":
            latest[doc.kind if doc.kind != "other" else doc.id] = doc.id
    return set(latest.values())


def instrument_documents(db, item):
    docs = db.scalars(
        select(Document)
        .where(Document.instrument_id == item.id, Document.institution_id == item.institution_id)
        .order_by(Document.created_at, Document.id)
    ).all()
    return docs, scan_states(db, docs), current_ids(docs)


def requirement_view(db, item, docs, states, current) -> list[dict]:
    required = db.get(Obligation, item.obligation_id).required_documents
    result = []
    for kind in required:
        doc = next((d for d in docs if d.id in current and d.kind == kind), None)
        result.append(
            {
                "kind": kind,
                "label": LABELS[kind],
                "document_id": str(doc.id) if doc else None,
                "satisfied": bool(doc and states[doc.id] == "clean"),
            }
        )
    return result


def submission_documents(db, item) -> list[dict]:
    """Snapshot references for submission; call with the instrument row locked."""
    docs, states, current = instrument_documents(db, item)
    requirements = requirement_view(db, item, docs, states, current)
    missing = [r["label"] for r in requirements if not r["satisfied"]]
    if missing:
        raise Problem(
            409,
            "documents_required",
            "Upload these documents and wait for a clean scan before submitting: "
            + ", ".join(missing)
            + ".",
        )
    chosen = [r["document_id"] for r in requirements]
    chosen += [
        str(d.id) for d in docs if d.kind == "other" and d.id in current and states[d.id] == "clean"
    ]
    by_id = {str(d.id): d for d in docs}
    return [
        {
            "id": id,
            "kind": by_id[id].kind,
            "filename": by_id[id].filename,
            "sha256": by_id[id].sha256,
            "object_version": by_id[id].object_version,
        }
        for id in chosen
    ]


async def bounded_body(request: Request) -> bytes:
    too_large = Problem(413, "file_too_large", "Files must be 10 MB or smaller.")
    try:
        if int(request.headers.get("content-length", 0)) > filecheck.MAX_BYTES:
            raise too_large
    except ValueError:
        raise Problem(400, "invalid_length", "Invalid upload length.") from None
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > filecheck.MAX_BYTES:
            raise too_large
    return bytes(body)


def display_name(raw: str) -> str:
    name = PurePosixPath(raw.replace("\\", "/")).name.strip()
    if not name or re.search(r"[\x00-\x1f\x7f]", name):
        raise Problem(422, "invalid_filename", "Give the file a plain name.")
    return name


def document_view(doc: Document, scan_status: str | None, current: bool = True) -> dict:
    return {
        "id": str(doc.id),
        "kind": doc.kind,
        "current": current,
        "filename": doc.filename,
        "media_type": doc.media_type,
        "size_bytes": doc.size_bytes,
        "page_count": doc.page_count,
        "sha256": doc.sha256,
        "status": doc.status,
        "scan_status": scan_status,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/instruments/{id}/documents")
def list_documents(id: UUID, user: Actor, db: DB):
    item = scoped_instrument(db, user, id)
    docs, states, current = instrument_documents(db, item)
    return {
        "items": [document_view(d, states[d.id], d.id in current) for d in docs],
        "requirements": requirement_view(db, item, docs, states, current),
    }


@router.post(
    "/instruments/{id}/documents",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in filecheck.SIGNATURES.values()
            },
        }
    },
)
def upload_document(
    id: UUID,
    request: Request,
    user: Writer,
    db: DB,
    filename: Annotated[str, Query(max_length=200)],
    kind: Kind,
    # Declared after Writer so unauthenticated bodies are never read.
    body: Annotated[bytes, Depends(bounded_body)],
):
    scoped_instrument(db, user, id)
    name = display_name(filename)
    declared = request.headers.get("content-type", "").split(";")[0].strip().lower()
    media = filecheck.sniff(body)
    if not media or media != declared:
        raise Problem(
            415, "unsupported_type", "Upload a PDF, JPEG or PNG whose content matches its type."
        )
    facts = filecheck.check(body)
    if "reason" in facts:
        reason = facts["reason"]
        if reason == "unreadable":
            reason = "The file could not be read as a valid PDF, JPEG or PNG."
        raise Problem(422, "file_rejected", reason)
    digest = hashlib.sha256(body).digest()

    # 1. Commit pending metadata first, so an interrupted upload is always discoverable.
    item = scoped_instrument(db, user, id, lock=True)
    if item.status != "draft":
        raise Problem(409, "already_submitted", "Submitted records cannot take new documents.")
    active = db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.instrument_id == id, Document.status != "failed")
    )
    if active >= MAX_DOCUMENTS:
        raise Problem(409, "document_limit", f"A record may hold {MAX_DOCUMENTS} documents.")
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        institution_id=user.institution_id,
        instrument_id=id,
        filename=name,
        kind=kind,
        media_type=media,
        size_bytes=len(body),
        sha256=digest.hex(),
        page_count=facts["page_count"],
        object_key=f"{user.institution_id}/{id}/{doc_id}",
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()

    # 2. Store bytes; the store verifies the SHA-256 and returns the immutable version id.
    try:
        put = request.app.state.s3.put_object(
            Bucket=request.app.state.settings.s3_bucket,
            Key=doc.object_key,
            Body=body,
            ContentType=media,
            ChecksumSHA256=base64.b64encode(digest).decode(),
        )
    except (BotoCoreError, ClientError):
        doc.status = "failed"
        db.commit()
        raise Problem(503, "storage_unavailable", "The file could not be stored. Try again.")

    # 3. Bind the record to that exact version, still only if the record is a draft.
    item = scoped_instrument(db, user, id, lock=True)
    if item.status != "draft":
        doc.status = "failed"
        db.commit()
        raise Problem(409, "already_submitted", "Submitted records cannot take new documents.")
    doc.status, doc.object_version = "quarantined", put["VersionId"]
    audit(
        db,
        request,
        user,
        "document.uploaded",
        item,
        {"document_id": str(doc.id), "sha256": doc.sha256, "object_version": doc.object_version},
    )
    db.commit()
    return document_view(doc, "pending")


@router.get("/documents/{id}/download")
def download_document(id: UUID, request: Request, user: Actor, db: DB):
    doc = db.get(Document, id)
    if not doc:
        raise Problem(404, "not_found", "Document not found.")
    if user.role == "reviewer":
        item = assigned_case(db, user, doc.instrument_id)
    else:
        item = scoped_instrument(db, user, doc.instrument_id)
    if scan_states(db, [doc])[doc.id] != "clean":
        raise Problem(
            409, "not_available", "Only files that malware scanning marked clean can be opened."
        )
    try:
        obj = request.app.state.s3.get_object(
            Bucket=request.app.state.settings.s3_bucket,
            Key=doc.object_key,
            VersionId=doc.object_version,
        )
        data = obj["Body"].read(filecheck.MAX_BYTES + 1)
    except (BotoCoreError, ClientError):
        raise Problem(503, "storage_unavailable", "The file could not be retrieved. Try again.")
    if hashlib.sha256(data).hexdigest() != doc.sha256:
        raise Problem(409, "integrity_failed", "The stored file failed its integrity check.")
    audit(db, request, user, "document.downloaded", item, {"document_id": str(doc.id)})
    db.commit()
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", doc.filename)
    return Response(
        data,
        media_type=doc.media_type,
        headers={
            # Attachment-only: the portal never renders uploaded content inline.
            "Content-Disposition": f'attachment; filename="{fallback}"; '
            f"filename*=UTF-8''{quote(doc.filename)}",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


def reconcile(db: Session, s3, bucket: str, grace=timedelta(minutes=15)) -> dict:
    """Fail stale pending uploads; delete stored versions no quarantined record is bound to."""
    cutoff = datetime.now(UTC) - grace
    stale = db.scalars(
        select(Document)
        .where(Document.status == "pending", Document.created_at < cutoff)
        .with_for_update(skip_locked=True)
    ).all()
    for doc in stale:
        doc.status = "failed"
    db.commit()
    bound = set(
        db.execute(
            select(Document.object_key, Document.object_version).where(
                Document.status == "quarantined"
            )
        ).tuples()
    )
    removed = 0
    # ponytail: full bucket listing per run; fine for the demo, use inventory/prefix shards at scale.
    for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
        for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
            if (v["Key"], v["VersionId"]) not in bound and v["LastModified"] < cutoff:
                s3.delete_object(Bucket=bucket, Key=v["Key"], VersionId=v["VersionId"])
                removed += 1
    return {"failed": len(stale), "removed": removed}


if __name__ == "__main__":
    from sqlalchemy import create_engine

    from safer.config import Settings
    from safer.storage import client

    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    with Session(engine) as session:
        print(reconcile(session, client(settings), settings.s3_bucket))
    engine.dispose()
