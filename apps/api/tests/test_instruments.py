from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from safer.models import AuditEvent, Instrument, Submission
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import DBAPIError


def payload(actors, owner=0):
    return {
        "obligation_id": str(actors["obligations"][owner].id),
        "bank_name": "Demo National Bank",
        "bank_reference": "000123-DEMO",
        "principal_amount": "500000.00",
        "currency": "INR",
        "issue_date": "2026-10-01",
        "maturity_date": "2027-10-01",
    }


def draft(client, actors):
    response = client.post("/api/v1/instruments", json=payload(actors))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_persists_decimal_reference_and_atomic_audit(clients, actors, db, settings):
    c = clients()
    item = draft(c, actors)
    assert item["principal_amount"] == "500000.00"
    assert item["bank_reference"] == "000123-DEMO"
    assert item["verification_status"] == "unverified"
    assert item["status"] == "draft" and item["row_version"] == 1
    assert (
        c.get(f"/api/v1/instruments/{item['id']}/audit").json()["items"][0]["action"]
        == "instrument.created"
    )
    # A separate connection proves persistence beyond the request's unit of work.
    other = create_engine(settings.database_url.get_secret_value())
    with other.connect() as conn:
        assert (
            conn.execute(
                text("SELECT principal_amount FROM instruments WHERE id=:id"), {"id": item["id"]}
            ).scalar()
            == 500000
        )
    other.dispose()


@pytest.mark.parametrize(
    "change",
    [
        {"principal_amount": "0"},
        {"principal_amount": "-1.00"},
        {"principal_amount": "0.001"},
        {"principal_amount": 500000.12},
        {"principal_amount": "NaN"},
        {"bank_name": "   "},
        {"bank_reference": ""},
        {"currency": "USD"},
        {"maturity_date": "2026-09-30"},
        {"issue_date": "bad-date"},
        {"institution_id": str(uuid4())},
        {"status": "submitted"},
    ],
)
def test_invalid_input_cannot_create_partial_record(change, clients, actors, db):
    r = clients().post("/api/v1/instruments", json=payload(actors) | change)
    assert r.status_code == 422
    assert db.scalar(select(func.count()).select_from(Instrument)) == 0
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_all_record_paths_are_scoped(clients, actors):
    alpha, beta = clients(), clients("beta")
    item = draft(alpha, actors)
    url = f"/api/v1/instruments/{item['id']}"
    assert beta.get("/api/v1/instruments").json()["items"] == []
    assert len(beta.get("/api/v1/obligations").json()["items"]) == 1
    assert beta.post("/api/v1/instruments", json=payload(actors)).status_code == 404
    assert beta.get(url).status_code == 404
    assert beta.get(url + "/audit").status_code == 404
    assert beta.patch(url, json=payload(actors), headers={"If-Match": '"1"'}).status_code == 404
    assert (
        beta.post(
            url + "/submissions", json={}, headers={"If-Match": '"1"', "Idempotency-Key": "foreign"}
        ).status_code
        == 404
    )


def test_stale_edit_and_submission_are_rejected(clients, actors):
    c = clients()
    item = draft(c, actors)
    url = f"/api/v1/instruments/{item['id']}"
    r = c.patch(
        url, json=payload(actors) | {"bank_reference": "000124"}, headers={"If-Match": '"1"'}
    )
    assert r.status_code == 200 and r.json()["row_version"] == 2
    assert c.patch(url, json=payload(actors), headers={"If-Match": '"1"'}).status_code == 412
    assert (
        c.post(
            url + "/submissions", json={}, headers={"If-Match": '"1"', "Idempotency-Key": "stale"}
        ).status_code
        == 412
    )
    assert c.get(url).json()["bank_reference"] == "000124"


def test_submission_is_immutable_and_retries_are_idempotent(clients, actors, db):
    c = clients()
    item = draft(c, actors)
    url = f"/api/v1/instruments/{item['id']}"
    headers = {"If-Match": '"1"', "Idempotency-Key": "request-one"}
    first = c.post(url + "/submissions", json={}, headers=headers)
    assert first.status_code == 201, first.text
    again = c.post(url + "/submissions", json={}, headers=headers)
    assert again.status_code == 200 and again.json() == first.json()
    assert first.json()["snapshot"]["principal_amount"] == "500000.00"
    assert c.get(url).json()["status"] == "submitted"
    assert c.patch(url, json=payload(actors), headers={"If-Match": '"2"'}).status_code == 409
    assert (
        c.post(
            url + "/submissions", json={}, headers=headers | {"Idempotency-Key": "new-key"}
        ).status_code
        == 409
    )
    assert db.scalar(select(func.count()).select_from(Submission)) == 1
    events = c.get(url + "/audit").json()["items"]
    assert [e["action"] for e in events] == ["instrument.created", "instrument.submitted"]


def test_missing_preconditions_and_csrf_fail(clients, actors):
    c = clients()
    item = draft(c, actors)
    url = f"/api/v1/instruments/{item['id']}"
    assert c.patch(url, json=payload(actors)).status_code == 428
    assert c.post(url + "/submissions", json={}, headers={"If-Match": '"1"'}).status_code == 422
    assert (
        c.post(
            "/api/v1/instruments", json=payload(actors), headers={"X-CSRF-Token": "bad"}
        ).status_code
        == 403
    )


def test_auditor_can_read_but_cannot_update_or_submit(clients, actors):
    alpha, reader = clients(), clients("auditor")
    item = draft(alpha, actors)
    url = f"/api/v1/instruments/{item['id']}"
    assert reader.get(url).status_code == 200
    assert reader.get(url + "/audit").status_code == 200
    assert reader.patch(url, json=payload(actors), headers={"If-Match": '"1"'}).status_code == 403
    assert (
        reader.post(
            url + "/submissions", json={}, headers={"If-Match": '"1"', "Idempotency-Key": "reader"}
        ).status_code
        == 403
    )


def test_concurrent_submissions_create_one_snapshot(clients, actors, db):
    a, b = clients(), clients()
    item = draft(a, actors)
    url = f"/api/v1/instruments/{item['id']}/submissions"

    def submit(pair):
        c, key = pair
        return c.post(url, json={}, headers={"If-Match": '"1"', "Idempotency-Key": key}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, [(a, "concurrent-a"), (b, "concurrent-b")]))
    assert sorted(outcomes) == [201, 409]
    assert db.scalar(select(func.count()).select_from(Submission)) == 1


def test_audit_failure_rolls_back_business_creation(clients, actors, db):
    c = clients()

    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO audit_events"):
            raise DBAPIError(statement, None, RuntimeError("injected audit outage"))

    event.listen(c.app.state.engine, "before_cursor_execute", fail_audit)
    try:
        r = c.post("/api/v1/instruments", json=payload(actors))
        assert r.status_code == 503
    finally:
        event.remove(c.app.state.engine, "before_cursor_execute", fail_audit)
    assert db.scalar(select(func.count()).select_from(Instrument)) == 0


def test_database_rejects_audit_and_snapshot_rewrite(clients, actors, db):
    c = clients()
    item = draft(c, actors)
    c.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": "immutable"},
    )
    for statement in ["UPDATE audit_events SET action='changed'", "DELETE FROM submissions"]:
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
            db.commit()
        db.rollback()


def test_pagination_and_search_do_not_bypass_scope(clients, actors):
    a, b = clients(), clients("beta")
    draft(a, actors)
    a.post("/api/v1/instruments", json=payload(actors) | {"bank_reference": "SECOND"})
    first = a.get("/api/v1/instruments?limit=1").json()
    second = a.get(
        "/api/v1/instruments", params={"limit": 1, "cursor": first["next_cursor"]}
    ).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert second["next_cursor"] is None
    assert b.get("/api/v1/instruments?q=000123").json()["items"] == []
    assert a.get("/api/v1/instruments?limit=101").status_code == 422
