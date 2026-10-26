"""On-demand advisory wording; financial authority stays with deterministic workflows."""

import hashlib
import json
import re
import time
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from safer import llm, summaries
from safer.errors import Problem
from safer.models import LlmAttempt
from safer.reviews import case
from safer.security import DB, Reviewer, current_user, reviewer

router = APIRouter(prefix="/api/v1")
Purpose = Literal["summary", "explanations"]
LOCK = 26265024
RESERVATION = 30000  # USD micro-units: deliberately overestimate each bounded request.


class GenerateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Purpose
    basis_sha256: str = Field(pattern="^[0-9a-f]{64}$")


def package(data: dict, purpose: Purpose) -> dict:
    if purpose == "summary":
        enabled = data["summary_state"]["enabled"]
        blocks = summaries.build(data)["sections"] if enabled else []
    else:
        enabled = data["explanations"]["enabled"]
        blocks = []
        for row in data["explanations"]["items"]:
            # Raw bank names/references aren't needed to explain the comparison outcome.
            facts = {
                "Comparison": row["status"],
                "Simulated": str(row["simulated"]),
                "Document differs": str(row["document_differs"]),
            }
            if row["field"] not in {"bank_name", "bank_reference"}:
                facts.update(
                    {
                        "Submitted": row["claimed"],
                        "Recorded evidence": row["evidence_value"],
                        "Document proposal": row["document_value"],
                    }
                )
            blocks.append(
                {
                    "title": row["label"],
                    "facts": facts,
                    "text": row["text"],
                    "citations": row["citations"],
                }
            )
    blocks = [{"id": f"b{i}", **b} for i, b in enumerate(blocks)]
    source = {
        "purpose": purpose,
        "version": llm.VERSION,
        "model": llm.MODEL,
        "case_basis": data["summary_state"]["basis_sha256"],
        "enabled": enabled,
        "blocks": blocks,
    }
    basis = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    return {
        "enabled": enabled,
        "purpose": purpose,
        "basis_sha256": basis,
        "case_basis_sha256": data["summary_state"]["basis_sha256"],
        "blocks": blocks,
    }


def gate(settings, source):
    if not source["enabled"]:
        return "feature_disabled"
    if settings.llm_mode != "gemini":
        return "disabled"
    if not settings.llm_synthetic_egress_approved:
        return "egress_not_approved"
    try:
        approved = llm.private_text(settings.llm_approved_sources_file).splitlines()
        if source["basis_sha256"] not in approved:
            return "source_not_approved"
    except llm.LlmFailure as error:
        return str(error)
    return None


def fallback(source, reason):
    return {**source, "mode": "deterministic_fallback", "reason": reason, "model": None}


@router.get("/reviews/{id}/ai")
def status(id: UUID, request: Request, user: Reviewer, db: DB, purpose: Purpose = "summary"):
    source = package(case(id, request, user, db), purpose)
    return {
        **source,
        "mode": "deterministic_fallback",
        "reason": gate(request.app.state.settings, source),
        "model": None,
    }


def reserve(db, actor_id, id, source, settings):
    now = db.scalar(select(func.clock_timestamp()))
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = db.scalar(
        select(func.coalesce(func.sum(LlmAttempt.reserved_microusd), 0)).where(
            LlmAttempt.created_at >= month
        )
    )
    if spent + RESERVATION > settings.llm_monthly_budget_microusd:
        raise llm.LlmFailure("budget_exhausted")
    daily = db.scalar(
        select(func.count())
        .select_from(LlmAttempt)
        .where(LlmAttempt.created_at >= now - timedelta(days=1))
    )
    recent = db.scalar(
        select(func.count())
        .select_from(LlmAttempt)
        .where(LlmAttempt.actor_id == actor_id, LlmAttempt.created_at >= now - timedelta(minutes=1))
    )
    if daily >= 100 or recent >= 3:
        raise llm.LlmFailure("rate_limited")
    attempt = LlmAttempt(
        actor_id=actor_id,
        instrument_id=id,
        purpose=source["purpose"],
        basis_sha256=source["basis_sha256"],
        model=llm.MODEL,
        reserved_microusd=RESERVATION,
    )
    db.add(attempt)
    db.commit()  # Never refund an ambiguous failure: the provider may have processed it.
    return attempt


@router.post("/reviews/{id}/ai")
def generate(id: UUID, data: GenerateInput, request: Request, user: Reviewer, db: DB):
    settings = request.app.state.settings
    source = package(case(id, request, user, db), data.purpose)
    if data.basis_sha256 != source["basis_sha256"]:
        raise Problem(409, "sources_changed", "Case facts changed. Refresh before generating.")
    if reason := gate(settings, source):
        return fallback(source, reason)
    try:
        key = llm.private_text(settings.llm_api_key_file)
        if not re.fullmatch(r"[a-zA-Z0-9_-]{20,256}", key):
            raise llm.LlmFailure("configuration_unavailable")
        llm.body_for(source["blocks"])
    except llm.LlmFailure as error:
        return fallback(source, str(error))

    # End the source-read transaction before checking out the inference connection.
    # Otherwise every request can retain one pool slot while waiting for a second.
    actor_id = user.id
    db.rollback()
    with request.app.state.engine.connect() as guard:
        acquired = guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK})
        guard.commit()  # Session-bound work below owns its transactions on this connection.
        if not acquired:
            return fallback(source, "busy")
        try:
            with Session(bind=guard, expire_on_commit=False) as inference_db:
                return infer(id, source, data.purpose, request, actor_id, inference_db, key)
        finally:
            guard.rollback()
            guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK})
            guard.commit()


def infer(id, source, purpose, request, actor_id, db, key):
    settings = request.app.state.settings
    try:
        attempt = reserve(db, actor_id, id, source, settings)
    except llm.LlmFailure as error:
        return fallback(source, str(error))
    started, result, failure = time.monotonic(), None, None
    try:
        result = llm.Gemini(key).generate(source["blocks"])
    except llm.LlmFailure as error:
        failure = str(error)
    attempt.status = "failed" if failure else "completed"
    attempt.reason = failure or ""
    attempt.total_tokens = result.tokens if result else 0
    attempt.duration_ms = round((time.monotonic() - started) * 1000)
    db.commit()
    # Expire the identity map and transaction snapshot before querying current
    # session, role, grants and facts. No output survives revocation or change.
    db.expire_all()
    try:
        fresh_user = reviewer(current_user(request, db))
        fresh = package(case(id, request, fresh_user, db), purpose)
        if fresh["basis_sha256"] != source["basis_sha256"]:
            raise Problem(
                409,
                "sources_changed",
                "Case facts changed while generating. Refresh and retry.",
            )
    except Problem:
        attempt.status, attempt.reason = "discarded", "access_or_sources_changed"
        db.commit()
        raise
    if reason := gate(settings, fresh):
        attempt.status, attempt.reason = "discarded", reason
        db.commit()
        return fallback(fresh, reason)
    if failure:
        return fallback(fresh, failure)
    return {
        **fresh,
        "mode": "llm",
        "reason": None,
        "model": llm.MODEL,
        "blocks": [{**b, "ai_text": result.texts[b["id"]]} for b in fresh["blocks"]],
    }
