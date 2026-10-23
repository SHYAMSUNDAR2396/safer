from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from safer import deadlines, replacements
from safer.models import Grant, Instrument, Obligation, Reminder, ReplacementLink
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_deadlines import at
from test_instruments import payload


def fdr(client, actors, ref, amount="500000.00", maturity="2027-10-01", owner=0, submit=True):
    item = client.post(
        "/api/v1/instruments",
        json=payload(actors, owner)
        | {"bank_reference": ref, "principal_amount": amount, "maturity_date": maturity},
    ).json()
    if submit:
        r = client.post(
            f"/api/v1/instruments/{item['id']}/submissions",
            json={},
            headers={"If-Match": '"1"', "Idempotency-Key": f"k-{item['id']}"},
        )
        assert r.status_code == 201, r.text
    return item


def propose(client, old, new):
    return client.post(
        f"/api/v1/instruments/{old['id']}/replacement", json={"successor_id": new["id"]}
    )


def decide(client, link_id, accept=True):
    return client.post(
        f"/api/v1/replacements/{link_id}/decision", json={"accept": accept, "note": "Checked"}
    )


def coverage(client, actors):
    return client.get(f"/api/v1/obligations/{actors['obligations'][0].id}/coverage").json()


def test_proposed_successor_is_reported_apart_from_accepted_coverage(clients, actors):
    alpha = clients()
    old = fdr(alpha, actors, "OLD-1")
    new = fdr(alpha, actors, "NEW-1", maturity="2028-10-01")
    r = propose(alpha, old, new)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "proposed"
    view = coverage(alpha, actors)
    assert view["covered_amount"] == "500000.00" and view["proposed_amount"] == "500000.00"
    assert view["gap_amount"] == "0.00"
    states = {i["bank_reference"]: i["state"] for i in view["instruments"]}
    assert states == {"OLD-1": "counting", "NEW-1": "proposed_successor"}


@pytest.mark.parametrize(
    "case,status",
    [
        ("foreign", 404),
        ("self", 422),
        ("draft", 409),
        ("partial", 422),
        ("earlier", 422),
        ("other_obligation", 422),
    ],
)
def test_invalid_replacements_are_refused(case, status, clients, actors, db):
    alpha = clients()
    old = fdr(alpha, actors, "OLD-2")
    if case == "foreign":
        new = fdr(clients("beta"), actors, "BETA-1", maturity="2028-10-01", owner=1)
    elif case == "self":
        new = old
    elif case == "draft":
        new = fdr(alpha, actors, "NEW-D", maturity="2028-10-01", submit=False)
    elif case == "partial":
        new = fdr(alpha, actors, "NEW-P", amount="1000.00", maturity="2028-10-01")
    elif case == "earlier":
        new = fdr(alpha, actors, "NEW-E", maturity="2027-01-01")
    else:
        other = Obligation(
            institution_id=actors["alpha"].institution_id,
            title="Second obligation",
            required_amount="1.00",
            required_documents=[],
        )
        db.add(other)
        db.commit()
        new = alpha.post(
            "/api/v1/instruments",
            json=payload(actors) | {"obligation_id": str(other.id), "maturity_date": "2028-10-01"},
        ).json()
        alpha.post(
            f"/api/v1/instruments/{new['id']}/submissions",
            json={},
            headers={"If-Match": '"1"', "Idempotency-Key": "other"},
        )
    assert propose(alpha, old, new).status_code == status
    assert db.scalars(select(ReplacementLink)).all() == []


def test_one_active_proposal_per_predecessor_and_per_successor(clients, actors):
    alpha = clients()
    old, other = fdr(alpha, actors, "OLD-3"), fdr(alpha, actors, "OLD-4")
    new = fdr(alpha, actors, "NEW-3", maturity="2028-10-01")
    spare = fdr(alpha, actors, "NEW-4", maturity="2028-10-01")
    assert propose(alpha, old, new).status_code == 201
    assert propose(alpha, old, spare).status_code == 409
    assert propose(alpha, other, new).status_code == 409


def test_cycles_are_refused(clients, actors, db):
    alpha = clients()
    a, b = fdr(alpha, actors, "A"), fdr(alpha, actors, "B", maturity="2028-10-01")
    propose(alpha, a, b)
    assert replacements.would_cycle(db, b["id"], a["id"]) is True
    assert replacements.would_cycle(db, a["id"], b["id"]) is False


def test_acceptance_moves_coverage_without_double_counting(clients, actors):
    alpha, reviewer = clients(), clients("reviewer")
    old = fdr(alpha, actors, "OLD-5")
    new = fdr(alpha, actors, "NEW-5", amount="600000.00", maturity="2028-10-01")
    link = propose(alpha, old, new).json()
    assert decide(alpha, link["id"]).status_code == 403
    r = decide(reviewer, link["id"])
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    view = coverage(alpha, actors)
    assert view["covered_amount"] == "600000.00" and view["proposed_amount"] == "0.00"
    states = {i["bank_reference"]: i["state"] for i in view["instruments"]}
    assert states == {"OLD-5": "superseded", "NEW-5": "counting"}
    assert decide(reviewer, link["id"]).status_code == 409
    case = reviewer.get(f"/api/v1/reviews/{old['id']}").json()
    assert case["replacement"]["outgoing"]["status"] == "accepted"
    assert case["coverage"]["covered_amount"] == "600000.00"
    actions = [
        e["action"] for e in alpha.get(f"/api/v1/instruments/{new['id']}/audit").json()["items"]
    ]
    assert "replacement.proposed" in actions and "replacement.accepted" in actions


def test_rejection_keeps_predecessor_and_frees_both_for_new_proposals(clients, actors):
    alpha, reviewer = clients(), clients("reviewer")
    old = fdr(alpha, actors, "OLD-6")
    new = fdr(alpha, actors, "NEW-6", maturity="2028-10-01")
    link = propose(alpha, old, new).json()
    assert decide(reviewer, link["id"], accept=False).json()["status"] == "rejected"
    view = coverage(alpha, actors)
    assert view["covered_amount"] == "1000000.00", "both count again: nothing was replaced"
    assert propose(alpha, old, new).status_code == 201


def test_only_assigned_reviewers_decide(clients, actors, db):
    alpha, reviewer = clients(), clients("reviewer")
    link = propose(
        alpha, fdr(alpha, actors, "OLD-7"), fdr(alpha, actors, "NEW-7", maturity="2028-10-01")
    ).json()
    db.execute(update(Grant).values(status="revoked", revoked_at=func.now()))
    db.commit()
    assert decide(reviewer, link["id"]).status_code == 404


def test_concurrent_decisions_record_one(clients, actors):
    alpha = clients()
    link = propose(
        alpha, fdr(alpha, actors, "OLD-8"), fdr(alpha, actors, "NEW-8", maturity="2028-10-01")
    ).json()
    a, b = clients("reviewer"), clients("reviewer")
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda c: decide(c, link["id"]).status_code, [a, b]))
    assert sorted(codes) == [200, 409]


def test_a_replacement_settles_the_renewal_action(clients, actors, db):
    alpha = clients()
    soon = (date.today() + timedelta(days=10)).isoformat()
    old = alpha.post(
        "/api/v1/instruments",
        json=payload(actors)
        | {
            "bank_reference": "OLD-9",
            "issue_date": (date.today() - timedelta(days=200)).isoformat(),
            "maturity_date": soon,
        },
    ).json()
    alpha.post(
        f"/api/v1/instruments/{old['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": "old9"},
    )
    propose(alpha, old, fdr(alpha, actors, "NEW-9", maturity="2028-10-01"))
    deadlines.sweep(db, at(date.today(), 1))
    steps = db.scalars(select(Reminder.step).where(Reminder.instrument_id == old["id"])).all()
    assert "action_due" not in steps and "escalation" not in steps
    view = alpha.get(f"/api/v1/instruments/{old['id']}/deadlines").json()
    assert view["renewal_required"] is False and view["replacement_status"] == "proposed"


def test_links_keep_their_history(clients, actors, db):
    alpha, reviewer = clients(), clients("reviewer")
    link = propose(
        alpha, fdr(alpha, actors, "OLD-10"), fdr(alpha, actors, "NEW-10", maturity="2028-10-01")
    ).json()
    decide(reviewer, link["id"])
    for statement in (
        "UPDATE replacement_links SET status = 'proposed'",
        "UPDATE replacement_links SET successor_id = predecessor_id",
        "DELETE FROM replacement_links",
    ):
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()
    assert db.get(Instrument, link["predecessor_id"]) is not None
