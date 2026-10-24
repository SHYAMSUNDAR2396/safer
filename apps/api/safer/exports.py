"""Protected CSV exports of dashboard lists.

Built asynchronously as an outbox job that carries only the export id. Authority is checked
three times: at request, when the job runs (current account and grants decide the scope, which
is then fixed on the export) and at download (owner only, still active, still authorised for
every institution in the file, not expired). Files live in private storage for one hour.
"""

import csv
import hashlib
import io
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from safer.dashboard import drill_rows, scope, visible
from safer.errors import Problem
from safer.models import AuditEvent, Export, User
from safer.security import DB, Actor

router = APIRouter(prefix="/api/v1")
TTL = timedelta(hours=1)
FORMULA = ("=", "+", "-", "@", "\t", "\r")
HEADER = ["FDR reference", "Bank", "Institution", "Principal (INR)", "Maturity date", "Status"]


def safe_cell(value) -> str:
    """Neutralise spreadsheet formula injection (OWASP CSV injection guidance)."""
    text = str(value)
    return "'" + text if text.startswith(FORMULA) else text


class ExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: Annotated[str, StringConstraints(max_length=40)]


class ExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_id: UUID


def record(db: Session, request_id: str, user: User, action: str, export: Export):
    db.add(
        AuditEvent(
            institution_id=user.institution_id,
            actor_id=user.id,
            action=action,
            request_id=request_id,
            detail={"export_id": str(export.id), "metric": export.metric},
        )
    )


def view(e: Export) -> dict:
    expired = bool(e.expires_at and e.expires_at <= datetime.now(UTC))
    return {
        "id": str(e.id),
        "metric": e.metric,
        "status": "expired" if e.status == "ready" and expired else e.status,
        "row_count": e.row_count,
        "error": e.error,
        "created_at": e.created_at.isoformat(),
        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
    }


def build(db: Session, ctx, payload: ExportPayload, final: bool):
    """Job handler. Idempotent: only a queued export is built."""
    from safer.jobs import Retry

    e = db.scalar(
        select(Export)
        .where(Export.id == payload.export_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not e or e.status != "queued":
        db.rollback()
        return
    user = db.scalar(select(User).where(User.id == e.user_id, User.active.is_(True)))
    ids = scope(db, user) if user else []
    result = drill_rows(db, user, e.metric, ids) if user and ids else None
    if not result:
        e.status, e.error = "failed", "The account no longer has authority for this export."
        db.commit()
        return
    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_ALL)
    writer.writerow(HEADER)
    for r in result[1]:
        writer.writerow(
            safe_cell(v)
            for v in (
                r["bank_reference"],
                r["bank_name"],
                r["institution"],
                r["principal_amount"],
                r["maturity_date"],
                r["status"],
            )
        )
    data = out.getvalue().encode()
    key = f"exports/{e.id}/{uuid4()}.csv"
    try:
        put = ctx.s3.put_object(
            Bucket=ctx.settings.s3_bucket, Key=key, Body=data, ContentType="text/csv"
        )
    except (BotoCoreError, ClientError):
        db.rollback()
        if final:
            e.status, e.error = "failed", "Storage was unavailable."
            db.commit()
            return
        raise Retry("storage unavailable")
    e.status, e.institution_ids, e.row_count = "ready", ids, len(result[1])
    e.object_key, e.object_version = key, put["VersionId"]
    e.sha256 = hashlib.sha256(data).hexdigest()
    e.ready_at = datetime.now(UTC)
    e.expires_at = e.ready_at + TTL
    record(db, str(uuid4()), user, "export.built", e)
    db.commit()


def purge(db: Session, s3, settings) -> int:
    """Delete stored files of expired exports (relay runs this every minute)."""
    due = db.scalars(
        select(Export).where(
            Export.expires_at <= func.now(),
            Export.purged_at.is_(None),
            Export.object_key.isnot(None),
        )
    ).all()
    for e in due:
        versions = s3.list_object_versions(Bucket=settings.s3_bucket, Prefix=e.object_key)
        for v in versions.get("Versions", []) + versions.get("DeleteMarkers", []):
            s3.delete_object(Bucket=settings.s3_bucket, Key=v["Key"], VersionId=v["VersionId"])
        e.purged_at = datetime.now(UTC)
    db.commit()
    return len(due)


@router.post("/exports", status_code=202)
def request_export(data: ExportInput, request: Request, user: Actor, db: DB):
    from safer.jobs import enqueue

    if user.role == "admin":
        raise Problem(403, "no_scope", "Administrators hold no case data to export.")
    if data.metric not in {d[0] for d in visible(user)}:
        raise Problem(422, "invalid_metric", "Choose a dashboard list you can see.")
    e = Export(user_id=user.id, metric=data.metric)
    db.add(e)
    db.flush()
    enqueue(db, "build_export", {"export_id": str(e.id)}, f"build_export:{e.id}")
    record(db, request.state.request_id, user, "export.requested", e)
    db.commit()
    return view(e)


@router.get("/exports")
def mine(user: Actor, db: DB):
    rows = db.scalars(
        select(Export).where(Export.user_id == user.id).order_by(Export.created_at.desc()).limit(20)
    ).all()
    return {"items": [view(e) for e in rows]}


@router.get("/exports/{id}/download")
def download(id: UUID, request: Request, user: Actor, db: DB):
    e = db.scalar(select(Export).where(Export.id == id, Export.user_id == user.id))
    if not e:
        raise Problem(404, "not_found", "Export not found.")
    if e.status != "ready":
        raise Problem(409, "not_ready", "This export is not ready.")
    if e.purged_at or e.expires_at <= datetime.now(UTC):
        raise Problem(410, "expired", "This export has expired. Request a new one.")
    if not set(e.institution_ids) <= set(scope(db, user)):
        raise Problem(403, "authority_changed", "Your access changed since this export was built.")
    try:
        obj = request.app.state.s3.get_object(
            Bucket=request.app.state.settings.s3_bucket,
            Key=e.object_key,
            VersionId=e.object_version,
        )
        data = obj["Body"].read()
    except (BotoCoreError, ClientError):
        raise Problem(503, "storage_unavailable", "The export could not be retrieved.")
    if hashlib.sha256(data).hexdigest() != e.sha256:
        raise Problem(409, "integrity_failed", "The stored export failed its integrity check.")
    record(db, request.state.request_id, user, "export.downloaded", e)
    db.commit()
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="safer-{e.metric}-{e.id.hex[:8]}.csv"'
        },
    )
