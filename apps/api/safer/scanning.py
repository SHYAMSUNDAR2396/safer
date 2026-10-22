"""Trusted scan orchestration.

This worker holds storage and database credentials; clamd, which parses the untrusted bytes,
holds none and has no internet, storage or database route (see compose.yaml). Only this
worker records results, each bound to the exact object version and the SHA-256 it scanned.
"""

import hashlib
import json
import socket
import struct
import sys
import time
from collections import Counter
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from safer.filecheck import MAX_BYTES
from safer.models import AuditEvent, Document, DocumentScan, Instrument

MAX_ATTEMPTS = 3
TERMINAL = ("clean", "infected", "mismatch")


def _clamd(settings, command: bytes, payload: bytes | None = None) -> str:
    with socket.create_connection((settings.clamd_host, settings.clamd_port), timeout=60) as s:
        s.sendall(command)
        if payload is not None:
            for i in range(0, len(payload), 65536):
                chunk = payload[i : i + 65536]
                s.sendall(struct.pack(">I", len(chunk)) + chunk)
            s.sendall(struct.pack(">I", 0))
        reply = b""
        while not reply.endswith(b"\0") and len(reply) < 1024:
            data = s.recv(1024)
            if not data:
                break
            reply += data
    return reply.rstrip(b"\0").decode(errors="replace")


def clamd_scan(settings, data: bytes) -> tuple[str, str, str]:
    """Return (outcome, signature, engine); raise OSError when no verdict was produced."""
    engine = _clamd(settings, b"zVERSION\0")[:100]
    reply = _clamd(settings, b"zINSTREAM\0", data)
    if reply == "stream: OK":
        return "clean", "", engine
    if reply.startswith("stream: ") and reply.endswith(" FOUND"):
        return "infected", reply[8:-6][:200], engine
    raise OSError("scanner returned no verdict")


def scan_states(db: Session, docs) -> dict:
    """pending | clean | infected | rejected | failed per quarantined document, else None."""
    ids = [d.id for d in docs]
    scans = db.scalars(select(DocumentScan).where(DocumentScan.document_id.in_(ids))).all()
    states = {}
    for doc in docs:
        mine = [
            s for s in scans if s.document_id == doc.id and s.object_version == doc.object_version
        ]
        final = next((s for s in mine if s.outcome in TERMINAL), None)
        if doc.status != "quarantined":
            states[doc.id] = None
        elif final and final.outcome == "clean":
            states[doc.id] = "clean" if final.sha256 == doc.sha256 else "rejected"
        elif final:
            states[doc.id] = "infected" if final.outcome == "infected" else "rejected"
        else:
            errors = sum(s.outcome == "error" for s in mine)
            states[doc.id] = "failed" if errors >= MAX_ATTEMPTS else "pending"
    return states


def scan_pending(db: Session, s3, settings, limit: int = 10) -> dict:
    done = exists().where(
        DocumentScan.document_id == Document.id,
        DocumentScan.object_version == Document.object_version,
        DocumentScan.outcome.in_(TERMINAL),
    )
    errors = (
        select(func.count())
        .where(DocumentScan.document_id == Document.id, DocumentScan.outcome == "error")
        .scalar_subquery()
    )
    # ponytail: rows stay locked during fetch+scan; fine for one worker, use leases at scale.
    due = db.scalars(
        select(Document)
        .where(Document.status == "quarantined", ~done, errors < MAX_ATTEMPTS)
        .order_by(Document.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    results = Counter()
    for doc in due:
        sha256, signature, engine = None, "", ""
        previous_errors = db.scalar(
            select(func.count()).where(
                DocumentScan.document_id == doc.id, DocumentScan.outcome == "error"
            )
        )
        try:
            obj = s3.get_object(
                Bucket=settings.s3_bucket, Key=doc.object_key, VersionId=doc.object_version
            )
            data = obj["Body"].read(MAX_BYTES + 1)
            sha256 = hashlib.sha256(data).hexdigest()
            if sha256 != doc.sha256:
                outcome = "mismatch"
            else:
                outcome, signature, engine = clamd_scan(settings, data)
        except (BotoCoreError, ClientError, OSError):
            outcome = "error"
        db.add(
            DocumentScan(
                document_id=doc.id,
                object_version=doc.object_version,
                sha256=sha256,
                outcome=outcome,
                engine=engine,
                signature=signature,
            )
        )
        if outcome != "error" or previous_errors + 1 >= MAX_ATTEMPTS:
            instrument = db.get(Instrument, doc.instrument_id)
            db.add(
                AuditEvent(
                    institution_id=doc.institution_id,
                    instrument_id=doc.instrument_id,
                    actor_id=None,
                    action="document.scanned" if outcome != "error" else "document.scan_failed",
                    row_version=instrument.row_version,
                    request_id=str(uuid4()),
                    detail={"document_id": str(doc.id), "outcome": outcome, "engine": engine},
                )
            )
        results[outcome] += 1
    db.commit()
    return dict(results)


if __name__ == "__main__":
    from sqlalchemy import create_engine

    from safer.config import Settings
    from safer.storage import client

    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    s3 = client(settings)
    while True:
        with Session(engine) as session:
            results = scan_pending(session, s3, settings)
        if results:
            print(json.dumps(results), flush=True)
        if "--once" in sys.argv:
            break
        if not results:
            time.sleep(3)
