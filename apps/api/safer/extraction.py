"""Text-first field extraction from clean FDR documents.

Deterministic, versioned rules read the PDF text layer (parsed in the isolated, credential-free
child process) and PROPOSE values with their page, position and source line. A field abstains
when it is missing, has several different values, or does not parse; nothing is guessed and no
confidence score is invented. Images and scans without a text layer need manual entry (OCR is
not configured). Proposals never change a claim and never count as evidence: an officer reviews
them in the edit form and saves. Results inherit the document's access rules.
"""

import hashlib
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from safer import filecheck
from safer.errors import Problem
from safer.instruments import assigned_case, scoped_instrument
from safer.models import Document, ExtractedField, ExtractionRun
from safer.scanning import scan_states
from safer.security import DB, Actor

router = APIRouter(prefix="/api/v1")
VERSION = "text-rules-2"
DATE = r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})"
RULES = {
    "bank_reference": r"(?:FDR|Deposit|Receipt)\s*(?:No\.?|Number|Ref(?:erence)?)\s*[:#]?\s*([A-Z0-9][A-Z0-9/-]{3,40})",
    "principal_amount": r"(?:Principal(?: Amount)?|Deposit Amount|Amount)\s*:?\s*(?:Rs\.?|INR|₹)?\s*([0-9][0-9,.]*)",
    "issue_date": rf"(?:Date of Deposit|Issue Date|Deposit Date)\s*:?\s*{DATE}",
    "maturity_date": rf"(?:Maturity Date|Date of Maturity|Due Date)\s*:?\s*{DATE}",
    "bank_name": r"Bank Name\s*:\s*([A-Za-z][A-Za-z .&'-]{2,118})",
}


def text_lines(data: bytes):
    return filecheck.text_layer(data)


def normalise(field: str, raw: str) -> str:
    """Canonical value, or ValueError if the text does not form a valid value."""
    if field == "principal_amount":
        if not re.fullmatch(
            r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+|[1-9][0-9]?(?:,[0-9]{2})*,[0-9]{3})(?:\.[0-9]{1,2})?",
            raw,
        ):
            raise ValueError
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            raise ValueError from None
        if value <= 0 or value > Decimal("9999999999999999.99"):
            raise ValueError
        return f"{value:.2f}"
    if field.endswith("_date"):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return date.fromisoformat(raw).isoformat()
        return datetime.strptime(raw.replace("-", "/"), "%d/%m/%Y").date().isoformat()
    return raw.strip()


def extract(lines: list) -> list[dict]:
    proposals = []
    for field, pattern in RULES.items():
        hits = []
        for page, x, y, text in lines:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                hits.append((match.group(1), page, x, y, text))
        result = {"field": field, "value": None, "page": None, "x": None, "y": None, "snippet": ""}
        if not hits:
            proposals.append(
                result | {"status": "abstained", "reason": "Not found in the document text."}
            )
            continue
        try:
            values = {normalise(field, h[0]) for h in hits}
        except ValueError:
            proposals.append(
                result
                | {
                    "status": "abstained",
                    "reason": "Found, but it is not a valid value.",
                    "snippet": hits[0][4],
                }
            )
            continue
        if len(values) > 1:
            proposals.append(
                result
                | {
                    "status": "abstained",
                    "reason": f"{len(values)} different values found; check the document.",
                }
            )
            continue
        raw, page, x, y, text = hits[0]
        proposals.append(
            result
            | {
                "status": "proposed",
                "reason": "",
                "value": values.pop(),
                "page": page,
                "x": x,
                "y": y,
                "snippet": text,
            }
        )
    return proposals


class ExtractPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID


def run(db: Session, ctx, payload: ExtractPayload, final: bool):
    """Job handler. Idempotent per document and extractor version; clean documents only."""
    doc = db.get(Document, payload.document_id)
    done = db.scalar(
        select(ExtractionRun.id).where(
            ExtractionRun.document_id == payload.document_id, ExtractionRun.extractor == VERSION
        )
    )
    if not doc or done or scan_states(db, [doc])[doc.id] != "clean":
        return
    data = ctx.s3.get_object(
        Bucket=ctx.settings.s3_bucket, Key=doc.object_key, VersionId=doc.object_version
    )["Body"].read(filecheck.MAX_BYTES + 1)
    if hashlib.sha256(data).hexdigest() != doc.sha256:
        status, lines, error = "failed", None, "Stored bytes do not match the uploaded hash."
    elif doc.media_type != "application/pdf":
        status, lines, error = "manual_required", [], ""
    else:
        lines = text_lines(data)
        status, error = (
            ("failed", "The text layer could not be read.")
            if lines is None
            else (
                "completed" if lines else "manual_required",
                "",
            )
        )
    r = ExtractionRun(
        document_id=doc.id, extractor=VERSION, status=status, text_layer=bool(lines), error=error
    )
    db.add(r)
    db.flush()
    if status != "failed":
        for p in extract(lines or []):
            if status == "manual_required":
                p |= {
                    "status": "abstained",
                    "reason": "No text layer; OCR is not configured, enter manually.",
                }
            db.add(ExtractedField(run_id=r.id, **p))
    db.commit()


def run_view(db: Session, r: ExtractionRun) -> dict:
    rows = db.scalars(select(ExtractedField).where(ExtractedField.run_id == r.id)).all()
    order = list(RULES)
    return {
        "status": r.status,
        "extractor": r.extractor,
        "text_layer": r.text_layer,
        "error": r.error,
        "created_at": r.created_at.isoformat(),
        "fields": [
            {
                "field": f.field,
                "status": f.status,
                "value": f.value,
                "reason": f.reason,
                "page": f.page,
                "x": f.x,
                "y": f.y,
                "snippet": f.snippet,
            }
            for f in sorted(rows, key=lambda f: order.index(f.field))
        ],
    }


def latest(db: Session, doc_ids) -> ExtractionRun | None:
    return db.scalar(
        select(ExtractionRun)
        .where(ExtractionRun.document_id.in_(doc_ids), ExtractionRun.status == "completed")
        .order_by(ExtractionRun.created_at.desc())
        .limit(1)
    )


def proposed_values(db: Session, doc_ids) -> dict:
    """Field -> proposed value from the newest completed run over these documents."""
    r = latest(db, doc_ids)
    if not r:
        return {}
    rows = db.scalars(
        select(ExtractedField).where(
            ExtractedField.run_id == r.id, ExtractedField.status == "proposed"
        )
    ).all()
    return {f.field: f.value for f in rows}


@router.get("/documents/{id}/extraction")
def extraction(id: UUID, user: Actor, db: DB):
    doc = db.get(Document, id)
    if not doc:
        raise Problem(404, "not_found", "Document not found.")
    if user.role == "reviewer":
        assigned_case(db, user, doc.instrument_id, closed=True)
    else:
        scoped_instrument(db, user, doc.instrument_id)
    if scan_states(db, [doc])[doc.id] != "clean":
        raise Problem(409, "not_available", "Only clean documents are read for extraction.")
    r = db.scalar(
        select(ExtractionRun).where(
            ExtractionRun.document_id == id, ExtractionRun.extractor == VERSION
        )
    )
    return run_view(db, r) if r else {"status": "pending", "extractor": VERSION, "fields": []}
