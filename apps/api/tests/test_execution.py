from datetime import UTC, date, datetime, timedelta

import pytest
from safer.main import app
from safer.models import Grant, Instrument
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_releases import act, clear_all, decide, request, view
from test_reviews import evidence, submitted

OBSERVED = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()


def approved(clients, actors):
    alpha = clients()
    item = submitted(alpha, actors)
    req = request(alpha, item).json()
    clear_all(clients("reviewer"), req)
    assert decide(clients("reviewer2"), req).status_code == 200
    return alpha, item, req


def instruct(client, req):
    return act(client, req, "instruction", note="Release lien and refund principal")


def execution(client, req, amount="500000.00", **change):
    body = {
        "executed_amount": amount,
        "executed_on": date.today().isoformat(),
        "bank_transaction_ref": "UTR-DEMO-0001",
        "source": "Demo National Bank, Fort branch",
        "method": "bank_letter",
        "observed_at": OBSERVED,
        "note": "Credit advice received from the bank",
    } | change
    return client.post(f"/api/v1/release-requests/{req['id']}/execution", json=body)


def test_instruction_needs_a_valid_approval(clients, actors, setup):
    alpha = clients()
    item = submitted(alpha, actors)
    req = request(alpha, item).json()
    approver = clients("reviewer2")
    assert instruct(approver, req).status_code == 409, "not approved yet"
    clear_all(clients("reviewer"), req)
    decide(approver, req)
    assert instruct(clients("reviewer"), req).status_code == 404, "no release authority"
    assert instruct(alpha, req).status_code == 403
    r = instruct(approver, req)
    assert r.status_code == 201, r.text
    ins = r.json()["instruction"]
    assert ins["reference"].startswith("SAFER-REL-") and ins["amount"] == "500000.00"
    assert ins["issued_by"] == "reviewer2" and ins["addressed_to"] == "Demo National Bank"
    assert instruct(approver, req).status_code == 409, "one instruction per request"


def test_invalidated_approval_cannot_be_instructed(clients, actors, setup):
    _, item, req = approved(clients, actors)
    clients("reviewer").post(f"/api/v1/reviews/{item['id']}/evidence", json=evidence())
    r = instruct(clients("reviewer2"), req)
    assert r.status_code == 409 and r.json()["code"] == "approval_invalidated"


def test_execution_evidence_follows_instruction_and_separation(clients, actors, db, setup):
    _, _, req = approved(clients, actors)
    reviewer, approver = clients("reviewer"), clients("reviewer2")
    assert execution(reviewer, req).json()["code"] == "no_instruction"
    instruct(approver, req)
    db.add(
        Grant(
            user_id=actors["reviewer2"].id,
            authority="review",
            institution_id=actors["alpha"].institution_id,
            status="active",
            reason="Also reviews",
        )
    )
    db.commit()
    r = execution(approver, req)
    assert r.status_code == 403 and r.json()["code"] == "separation_of_duties"
    assert execution(reviewer, req, method="uploaded_document").status_code == 422
    assert execution(reviewer, req, amount="-1").status_code == 422
    assert (
        execution(
            reviewer, req, observed_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()
        ).status_code
        == 422
    )
    r = execution(reviewer, req)
    assert r.status_code == 201, r.text
    assert r.json()["reconciliation"] == {
        "status": "matched",
        "instructed": "500000.00",
        "executed": "500000.00",
        "difference": "0.00",
    }


def test_differences_block_closure(clients, actors, setup):
    _, _, req = approved(clients, actors)
    reviewer = clients("reviewer")
    instruct(clients("reviewer2"), req)
    r = execution(reviewer, req, amount="499000.00")
    assert r.json()["reconciliation"]["status"] == "difference"
    assert r.json()["reconciliation"]["difference"] == "-1000.00"
    assert act(reviewer, req, "close", note="Done").json()["code"] == "not_reconciled"
    corrected = execution(reviewer, req, bank_transaction_ref="UTR-DEMO-0002")
    assert corrected.json()["reconciliation"]["status"] == "matched", "latest evidence governs"
    assert len(corrected.json()["executions"]) == 2, "earlier evidence is kept"


def test_closure_requires_reconciled_execution_not_approval_alone(clients, actors, db, setup):
    alpha, item, req = approved(clients, actors)
    reviewer = clients("reviewer")
    assert act(reviewer, req, "close", note="Approved").json()["code"] == "no_execution"
    instruct(clients("reviewer2"), req)
    execution(reviewer, req)
    assert act(alpha, req, "close", note="x").status_code == 403
    r = act(reviewer, req, "close", note="Reconciled with bank credit advice")
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert db.get(Instrument, item["id"]).status == "closed"
    assert alpha.get("/api/v1/instruments").status_code == 200, "closed FDRs still list"
    assert alpha.get(f"/api/v1/instruments/{item['id']}").json()["status"] == "closed"
    assert [e["kind"] for e in view(alpha, req)["events"]][-3:] == [
        "instructed",
        "executed",
        "closed",
    ]
    reviewer = clients("reviewer")
    assert item["id"] not in [
        q["instrument_id"] for q in reviewer.get("/api/v1/reviews").json()["items"]
    ]
    assert reviewer.get(f"/api/v1/reviews/{item['id']}").json()["releases"][0]["status"] == "closed"
    assert (
        reviewer.post(f"/api/v1/reviews/{item['id']}/evidence", json=evidence()).status_code == 404
    )


def test_portal_exposes_no_payment_api():
    paths = " ".join(app.openapi()["paths"]).lower()
    for word in ("pay", "transfer", "disburse", "remit"):
        assert word not in paths


def test_execution_history_is_append_only(clients, actors, db, setup):
    _, _, req = approved(clients, actors)
    instruct(clients("reviewer2"), req)
    execution(clients("reviewer"), req)
    for statement in (
        "UPDATE release_instructions SET amount = 1",
        "DELETE FROM release_instructions",
        "UPDATE release_executions SET executed_amount = 1",
        "DELETE FROM release_executions",
    ):
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()
