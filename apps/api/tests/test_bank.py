import pytest
from safer import bank
from safer.errors import Problem
from safer.models import BankRequest, EvidenceRecord, Instrument, ReviewAssignment
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from test_instruments import payload


def submitted(client, actors, reference="000123-DEMO"):
    item = client.post(
        "/api/v1/instruments", json=payload(actors) | {"bank_reference": reference}
    ).json()
    r = client.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": f"k-{item['id']}"},
    )
    assert r.status_code == 201, r.text
    return item


def request(client, item):
    return client.post(f"/api/v1/reviews/{item['id']}/bank-requests", json={})


def evidence_count(db):
    return db.scalar(select(func.count()).select_from(EvidenceRecord))


def test_simulated_confirmation_is_signed_bound_and_labelled(clients, actors, db):
    reviewer = clients("reviewer")
    item = submitted(clients(), actors)
    r = request(reviewer, item)
    assert r.status_code == 201, r.text
    assert r.json()["outcome"] == "confirmed" and r.json()["provider"] == "simulator"
    case = reviewer.get(f"/api/v1/reviews/{item['id']}").json()
    assert {(c["status"], c["simulated"]) for c in case["comparison"]} == {("match", True)}
    assert {e["method"] for e in case["evidence"]} == {"bank_simulator"}
    assert all("not a bank" in e["source"] for e in case["evidence"])
    assert case["bank_requests"][0]["outcome"] == "confirmed"
    queue = reviewer.get("/api/v1/reviews").json()["items"][0]
    assert queue["confirmed_fields"] == 0, "simulated answers never count as confirmation"
    assert queue["simulated_fields"] == 5
    actions = [a["action"] for a in case["audit"]]
    assert actions.count("review.bank_requested") == 1
    assert actions.count("review.bank_answered") == 1


@pytest.mark.parametrize(
    "suffix,outcome",
    [
        ("-NOTFOUND", "not_found"),
        ("-TIMEOUT", "timeout"),
        ("-TAMPER", "rejected"),
        ("-REPLAY", "rejected"),
    ],
)
def test_failed_answers_leave_fields_unconfirmed(suffix, outcome, clients, actors, db):
    reviewer = clients("reviewer")
    item = submitted(clients(), actors, "000123" + suffix)
    r = request(reviewer, item)
    assert r.status_code == 201 and r.json()["outcome"] == outcome
    assert evidence_count(db) == 0
    case = reviewer.get(f"/api/v1/reviews/{item['id']}").json()
    assert {c["status"] for c in case["comparison"]} == {"unconfirmed"}


def test_simulated_mismatch_is_detected_by_code(clients, actors):
    reviewer = clients("reviewer")
    item = submitted(clients(), actors, "000123-MISMATCH")
    request(reviewer, item)
    rows = {
        c["field"]: c["status"]
        for c in reviewer.get(f"/api/v1/reviews/{item['id']}").json()["comparison"]
    }
    assert rows["maturity_date"] == "mismatch" and rows["principal_amount"] == "match"


def test_answer_for_a_changed_case_version_is_stale(clients, actors, db, settings):
    item = submitted(clients(), actors)
    instrument = db.get(Instrument, item["id"])
    pending = bank.open_request(db, instrument, actors["reviewer"])
    answer = bank.PROVIDERS["simulator"](pending, bank.snapshot(db, instrument), bank.key(settings))
    db.execute(
        text("UPDATE instruments SET row_version = row_version + 1 WHERE id = :id"),
        {"id": item["id"]},
    )
    db.commit()
    assert bank.accept(db, pending, answer, actors["reviewer"], settings) == "stale"
    assert evidence_count(db) == 0


def test_the_same_answer_cannot_be_accepted_twice(clients, actors, db, settings):
    item = submitted(clients(), actors)
    instrument = db.get(Instrument, item["id"])
    pending = bank.open_request(db, instrument, actors["reviewer"])
    answer = bank.PROVIDERS["simulator"](pending, bank.snapshot(db, instrument), bank.key(settings))
    assert bank.accept(db, pending, answer, actors["reviewer"], settings) == "confirmed"
    with pytest.raises(Problem) as replay:
        bank.accept(db, pending, answer, actors["reviewer"], settings)
    assert replay.value.status == 409
    assert evidence_count(db) == 5


def test_answer_with_altered_values_fails_signature(clients, actors, db, settings):
    item = submitted(clients(), actors)
    instrument = db.get(Instrument, item["id"])
    pending = bank.open_request(db, instrument, actors["reviewer"])
    answer = bank.PROVIDERS["simulator"](pending, bank.snapshot(db, instrument), bank.key(settings))
    answer["record"]["principal_amount"] = "1.00"
    assert bank.accept(db, pending, answer, actors["reviewer"], settings) == "rejected"
    assert evidence_count(db) == 0


def test_only_assigned_reviewers_can_ask_the_simulator(clients, actors, db):
    alpha, reviewer = clients(), clients("reviewer")
    item = submitted(alpha, actors)
    assert request(alpha, item).status_code == 403
    db.execute(delete(ReviewAssignment))
    db.commit()
    assert request(reviewer, item).status_code == 404
    assert db.scalar(select(func.count()).select_from(BankRequest)) == 0


def test_bank_exchange_history_is_immutable(clients, actors, db):
    item = submitted(clients(), actors)
    request(clients("reviewer"), item)
    for table in ("bank_requests", "bank_responses"):
        for statement in (f"UPDATE {table} SET provider = provider", f"DELETE FROM {table}"):
            if table == "bank_responses":
                statement = statement.replace("provider = provider", "outcome = outcome")
            with pytest.raises(DBAPIError):
                db.execute(text(statement))
            db.rollback()
