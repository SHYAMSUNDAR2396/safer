from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest
from safer.models import Grant, Obligation, Policy, ReleaseRequest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from test_reviews import evidence, submitted

CLEARANCES = ["no_dues_certificate", "closure_approval_letter"]


@pytest.fixture
def setup(db, actors):
    """Published release policy, cover period ended, and reviewer2 as release approver."""
    db.add(
        Policy(
            code="release",
            version=1,
            applies_to="*",
            effective_from=date(2026, 1, 1),
            rules={"clearances": CLEARANCES, "release_not_before": "obligation_end"},
            note="Test policy",
            status="published",
            drafted_by=actors["admin1"].id,
            published_by=actors["admin2"].id,
            published_at=datetime.now(UTC),
        )
    )
    grant_release(db, actors, "reviewer2")
    obligation = db.get(Obligation, actors["obligations"][0].id)
    obligation.required_until = date.today() - timedelta(days=1)
    db.commit()


def grant_release(db, actors, name):
    db.add(
        Grant(
            user_id=actors[name].id,
            authority="release_approve",
            institution_id=actors["alpha"].institution_id,
            status="active",
            requested_by=actors["admin1"].id,
            approved_by=actors["admin2"].id,
            reason="Release authority",
        )
    )
    db.commit()


def request(client, item, reason="Obligation period ended"):
    return client.post(
        f"/api/v1/instruments/{item['id']}/release-requests", json={"reason": reason}
    )


def act(client, req, action, **body):
    return client.post(f"/api/v1/release-requests/{req['id']}/{action}", json=body)


def clear_all(reviewer, req):
    for c in CLEARANCES:
        r = act(reviewer, req, "clearances", clearance=c, note="Received")
        assert r.status_code == 201, r.text


def view(client, req):
    return client.get(f"/api/v1/release-requests/{req['id']}").json()


def decide(client, req, approve=True, basis=None, key="d1"):
    basis = basis if basis is not None else view(client, req)["basis"]
    return client.post(
        f"/api/v1/release-requests/{req['id']}/decision",
        json={"approve": approve, "note": "Decided", "basis": basis},
        headers={"Idempotency-Key": key},
    )


def ready(clients, actors):
    alpha = clients()
    item = submitted(alpha, actors)
    req = request(alpha, item).json()
    clear_all(clients("reviewer"), req)
    return alpha, item, req


def test_release_needs_eligibility_and_a_policy(clients, actors, db, setup):
    alpha = clients()
    item = submitted(alpha, actors)
    obligation = db.get(Obligation, actors["obligations"][0].id)
    obligation.required_until = None
    db.commit()
    r = request(alpha, item)
    assert r.status_code == 409 and r.json()["code"] == "not_eligible"
    obligation.required_until = date.today() - timedelta(days=1)
    db.commit()
    r = request(alpha, item)
    assert r.status_code == 201, r.text
    assert r.json()["policy"]["version"] == 1 and r.json()["status"] == "open"
    assert r.json()["policy"]["rules"]["clearances"] == CLEARANCES
    assert request(alpha, item).status_code == 409, "one live request per FDR"
    assert request(clients("auditor"), item).status_code == 403
    assert request(clients("beta"), item).status_code == 404


def test_no_policy_means_no_release(clients, actors, db):
    alpha = clients()
    item = submitted(alpha, actors)
    obligation = db.get(Obligation, actors["obligations"][0].id)
    obligation.required_until = date.today() - timedelta(days=1)
    db.commit()
    assert request(alpha, item).json()["code"] == "no_policy"


def test_only_reviewers_record_clearances_once_each(clients, actors, setup):
    alpha = clients()
    req = request(alpha, submitted(alpha, actors)).json()
    reviewer = clients("reviewer")
    assert act(reviewer, req, "clearances", clearance="bribe", note="x").status_code == 422
    assert (
        act(reviewer, req, "clearances", clearance="audit_confirmation", note="x").status_code
        == 422
    )
    assert act(alpha, req, "clearances", clearance=CLEARANCES[0], note="x").status_code == 403
    assert (
        act(clients("reviewer2"), req, "clearances", clearance=CLEARANCES[0], note="x").status_code
        == 404
    )
    assert act(reviewer, req, "clearances", clearance=CLEARANCES[0], note="x").status_code == 201
    assert act(reviewer, req, "clearances", clearance=CLEARANCES[0], note="x").status_code == 409


def test_decision_waits_for_clearances_and_clean_evidence(clients, actors, setup):
    alpha = clients()
    item = submitted(alpha, actors)
    req = request(alpha, item).json()
    approver, reviewer = clients("reviewer2"), clients("reviewer")
    assert decide(approver, req).json()["code"] == "clearances_pending"
    clear_all(reviewer, req)
    reviewer.post(
        f"/api/v1/reviews/{item['id']}/evidence", json=evidence("maturity_date", "2027-09-30")
    )
    assert decide(approver, req).json()["code"] == "evidence_mismatch"
    reviewer.post(
        f"/api/v1/reviews/{item['id']}/evidence", json=evidence("maturity_date", "2027-10-01")
    )
    d = reviewer.post(
        f"/api/v1/reviews/{item['id']}/discrepancies", json={"message": "Check"}
    ).json()
    assert decide(approver, req).json()["code"] == "open_observations"
    reviewer.post(
        f"/api/v1/discrepancies/{d['id']}/replies", json={"message": "Fine", "resolve": True}
    )
    assert decide(approver, req).status_code == 200


def test_competent_approval_with_stale_and_replay_protection(clients, actors, setup):
    alpha, item, req = ready(clients, actors)
    approver = clients("reviewer2")
    assert decide(approver, req, basis="0" * 64).status_code == 412
    first = decide(approver, req, key="once")
    assert first.status_code == 200 and first.json()["status"] == "approved"
    assert first.json()["decided_by"] == "reviewer2"
    again = decide(approver, req, key="once", basis="ignored-on-replay")
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert decide(approver, req, key="other").status_code == 409
    kinds = [e["kind"] for e in view(alpha, req)["events"]]
    assert kinds == ["requested", "cleared", "cleared", "approved"]
    assert decide(clients("reviewer"), req, key="x").status_code == 404, "no release authority"


def test_whoever_cleared_cannot_also_approve(clients, actors, db, setup):
    _, _, req = ready(clients, actors)
    grant_release(db, actors, "reviewer")
    r = decide(clients("reviewer"), req)
    assert r.status_code == 403 and r.json()["code"] == "separation_of_duties"


def test_hold_return_and_resubmit(clients, actors, setup):
    alpha, item, req = ready(clients, actors)
    reviewer, approver = clients("reviewer"), clients("reviewer2")
    assert act(reviewer, req, "hold", note="Awaiting branch letter").json()["status"] == "on_hold"
    assert decide(approver, req).status_code == 409
    assert act(reviewer, req, "resume", note="Letter received").json()["status"] == "open"
    assert act(reviewer, req, "return", note="Attach lien release").json()["status"] == "returned"
    assert act(alpha, req, "hold", note="x").status_code == 403
    assert decide(approver, req).status_code == 409
    assert act(alpha, req, "resubmit", note="Lien release attached").json()["status"] == "open"
    assert decide(approver, req).status_code == 200
    kinds = [e["kind"] for e in view(alpha, req)["events"]]
    assert kinds[-5:] == ["held", "resumed", "returned", "resubmitted", "approved"]


def test_institution_can_withdraw_and_request_again(clients, actors, setup):
    alpha = clients()
    item = submitted(alpha, actors)
    req = request(alpha, item).json()
    assert act(alpha, req, "withdraw", note="Not needed").json()["status"] == "withdrawn"
    assert request(alpha, item).status_code == 201


def test_concurrent_decisions_record_one(clients, actors, setup):
    _, _, req = ready(clients, actors)
    a, b = clients("reviewer2"), clients("reviewer2")
    basis = view(a, req)["basis"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(
            pool.map(
                lambda pair: decide(pair[0], req, basis=basis, key=pair[1]).status_code,
                [(a, "a"), (b, "b")],
            )
        )
    assert sorted(codes) == [200, 409]


def test_material_change_invalidates_approval_until_redecided(clients, actors, setup):
    alpha, item, req = ready(clients, actors)
    approver, reviewer = clients("reviewer2"), clients("reviewer")
    assert decide(approver, req, key="v1").status_code == 200
    reviewer.post(f"/api/v1/reviews/{item['id']}/evidence", json=evidence())
    current = view(alpha, req)
    assert current["status"] == "approved" and current["approval_valid"] is False
    assert current["effective_status"] == "approval_invalidated"
    assert act(reviewer, req, "reopen", note="New evidence").json()["status"] == "open"
    assert decide(approver, req, key="v2").json()["approval_valid"] is True


def test_cannot_reopen_a_valid_approval(clients, actors, setup):
    _, _, req = ready(clients, actors)
    decide(clients("reviewer2"), req)
    assert act(clients("reviewer"), req, "reopen", note="x").status_code == 409


def test_release_history_is_append_only(clients, actors, db, setup):
    _, _, req = ready(clients, actors)
    for statement in (
        "UPDATE release_events SET note = 'x'",
        "DELETE FROM release_clearances",
        "UPDATE release_requests SET reason = 'rewritten'",
        "UPDATE release_requests SET status = 'approved'",
        "DELETE FROM release_requests",
    ):
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()
    assert db.scalar(select(func.count()).select_from(ReleaseRequest)) == 1
