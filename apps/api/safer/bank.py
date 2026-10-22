"""Bank confirmation exchange. The only provider is a SYNTHETIC simulator; no bank is contacted.

Provider contract (what a real adapter must satisfy, SAF-036):
    provider(request, snapshot, key) -> signed answer dict, or raise TimeoutError
The answer is untrusted until `accept` verifies its signature, its binding to this request,
bank reference and case version, and its observation time. Only then does it become evidence.
"""

import hashlib
import hmac
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from safer.errors import Problem
from safer.instruments import assigned_case
from safer.models import BankRequest, BankResponse, EvidenceRecord, Instrument, Submission
from safer.reviews import FIELDS, bank_views
from safer.schemas import EmptyCommand
from safer.security import DB, Reviewer, audit

router = APIRouter(prefix="/api/v1")

SOURCE = "SAFER bank simulator · synthetic, not a bank"


def key(settings) -> bytes:
    return hmac.new(
        settings.session_secret.get_secret_value().encode(), b"bank-simulator", hashlib.sha256
    ).digest()


def sign(answer: dict, secret: bytes) -> str:
    body = json.dumps({k: v for k, v in answer.items() if k != "signature"}, sort_keys=True)
    return hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()


def snapshot(db: Session, item) -> dict:
    return db.scalar(select(Submission.snapshot).where(Submission.instrument_id == item.id))


def simulator(request: BankRequest, claim: dict, secret: bytes) -> dict:
    """Synthetic bank: mirrors the claim unless the FDR reference ends with a scenario suffix."""
    reference = claim["bank_reference"]
    if reference.endswith("-TIMEOUT"):
        raise TimeoutError("simulated provider timeout")
    record = {field: claim[field] for field in FIELDS}
    if reference.endswith("-MISMATCH"):
        maturity = date.fromisoformat(claim["maturity_date"]) - timedelta(days=1)
        record["maturity_date"] = maturity.isoformat()
    answer = {
        "provider": "simulator",
        "request_ref": str(request.id),
        "bank_reference": reference,
        "found": not reference.endswith("-NOTFOUND"),
        "record": record if not reference.endswith("-NOTFOUND") else None,
        "observed_at": datetime.now(UTC).isoformat(),
    }
    if reference.endswith("-REPLAY"):
        answer["request_ref"] = "an-earlier-request"  # an old answer replayed at us
    answer["signature"] = sign(answer, secret)
    if reference.endswith("-TAMPER"):
        answer["record"] = dict(record, principal_amount="1.00")  # altered after signing
    return answer


PROVIDERS = {"simulator": simulator}


def open_request(db: Session, item, user, provider="simulator") -> BankRequest:
    sub = db.scalar(select(Submission).where(Submission.instrument_id == item.id))
    request = BankRequest(
        instrument_id=item.id,
        institution_id=item.institution_id,
        submission_id=sub.id,
        row_version=item.row_version,
        provider=provider,
        requested_by=user.id,
    )
    db.add(request)
    db.flush()
    return request


def _problem(answer: dict, request: BankRequest, claim: dict, secret: bytes) -> str | None:
    if not hmac.compare_digest(str(answer.get("signature", "")), sign(answer, secret)):
        return "signature does not verify"
    if answer.get("request_ref") != str(request.id) or answer.get("provider") != request.provider:
        return "answer is bound to a different request"
    if answer.get("bank_reference") != claim["bank_reference"]:
        return "answer is for a different FDR reference"
    try:
        observed = datetime.fromisoformat(answer["observed_at"])
        record = answer["record"] or {}
        Decimal(record.get("principal_amount", "1"))
        for field in ("issue_date", "maturity_date"):
            if field in record:
                date.fromisoformat(record[field])
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return "answer is malformed"
    if (
        not request.created_at - timedelta(minutes=1)
        <= observed
        <= datetime.now(UTC) + timedelta(minutes=1)
    ):
        return "observation time is outside the request window"
    if answer["found"] and set(record) != set(FIELDS):
        return "answer is malformed"
    return None


def accept(db: Session, request: BankRequest, answer: dict | None, user, settings) -> str:
    """Record exactly one verified outcome per request; only 'confirmed' creates evidence.

    The caller commits, so the outcome, evidence and audit land in one transaction."""
    # populate_existing: sessions keep objects across commits, so re-read the locked row.
    item = db.scalar(
        select(Instrument)
        .where(Instrument.id == request.instrument_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if db.scalar(select(BankResponse.id).where(BankResponse.request_id == request.id)):
        raise Problem(409, "already_answered", "This bank request already has an answer.")
    claim = snapshot(db, item)
    secret = key(settings)
    if answer is None:
        outcome, detail = "timeout", "provider did not answer in time; fields stay unconfirmed"
    elif reason := _problem(answer, request, claim, secret):
        outcome, detail = "rejected", reason
    elif item.row_version != request.row_version:
        outcome, detail = "stale", "case changed after the request was sent"
    elif not answer["found"]:
        outcome, detail = "not_found", "provider has no deposit with this reference"
    else:
        outcome, detail = "confirmed", ""
        for field in FIELDS:
            value = answer["record"][field]
            if field == "principal_amount":
                value = f"{Decimal(value):.2f}"
            db.add(
                EvidenceRecord(
                    instrument_id=item.id,
                    institution_id=item.institution_id,
                    field=field,
                    value=str(value),
                    source=SOURCE,
                    method="bank_simulator",
                    observer_id=user.id,
                    observed_at=datetime.fromisoformat(answer["observed_at"]),
                    note=f"Simulated answer to request {request.id}",
                )
            )
    db.add(BankResponse(request_id=request.id, outcome=outcome, detail=detail, payload=answer))
    return outcome


@router.post("/reviews/{id}/bank-requests", status_code=201)
def request_confirmation(id: UUID, data: EmptyCommand, request: Request, user: Reviewer, db: DB):
    item = assigned_case(db, user, id)
    pending = open_request(db, item, user)
    audit(
        db,
        request,
        user,
        "review.bank_requested",
        item,
        {"bank_request_id": str(pending.id), "provider": pending.provider},
    )
    db.commit()  # the request exists before any provider is contacted
    settings = request.app.state.settings
    try:
        # ponytail: in-process simulator answers instantly; a real adapter needs a hard timeout.
        answer = PROVIDERS[pending.provider](pending, snapshot(db, item), key(settings))
    except TimeoutError:
        answer = None
    outcome = accept(db, pending, answer, user, settings)
    audit(
        db,
        request,
        user,
        "review.bank_answered",
        item,
        {"bank_request_id": str(pending.id), "outcome": outcome},
    )
    db.commit()
    return next(v for v in bank_views(db, id) if v["id"] == str(pending.id))
