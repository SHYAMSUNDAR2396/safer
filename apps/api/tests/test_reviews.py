from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from safer import scanning
from safer.models import EvidenceRecord, ReviewAssignment
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from test_documents import pdf, upload
from test_instruments import draft, payload

OBSERVED = (datetime.now(UTC) - timedelta(hours=1)).isoformat()


def submitted(client, actors, owner=0):
    r = client.post("/api/v1/instruments", json=payload(actors, owner))
    item = r.json()
    r = client.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": f"k-{item['id']}"},
    )
    assert r.status_code == 201, r.text
    return item


def evidence(field="principal_amount", value="500000.00", **change):
    return {
        "field": field,
        "value": value,
        "source": "Demo National Bank, Fort branch",
        "method": "bank_portal",
        "observed_at": OBSERVED,
        "note": "",
    } | change


def test_queue_holds_only_submitted_cases_of_assigned_institutions(clients, actors):
    alpha, beta, reviewer = clients(), clients("beta"), clients("reviewer")
    case = submitted(alpha, actors)
    pending = draft(alpha, actors)
    foreign = submitted(beta, actors, owner=1)
    queue = reviewer.get("/api/v1/reviews").json()["items"]
    assert [q["instrument_id"] for q in queue] == [case["id"]]
    assert queue[0]["institution"]["name"] == "Alpha Technical Institute"
    assert queue[0]["open_discrepancies"] == 0 and queue[0]["confirmed_fields"] == 0
    assert reviewer.get(f"/api/v1/reviews/{foreign['id']}").status_code == 404
    assert reviewer.get(f"/api/v1/reviews/{pending['id']}").status_code == 404
    for name in ("alpha", "auditor"):
        assert clients(name).get("/api/v1/reviews").status_code == 403
    assert reviewer.get("/api/v1/instruments").json()["items"] == []
    assert reviewer.post("/api/v1/instruments", json=payload(actors)).status_code == 403


def test_evidence_is_kept_apart_from_claims_and_compared_by_code(clients, actors):
    alpha, reviewer = clients(), clients("reviewer")
    case = submitted(alpha, actors)
    url = f"/api/v1/reviews/{case['id']}"
    assert reviewer.post(url + "/evidence", json=evidence()).status_code == 201
    r = reviewer.post(
        url + "/evidence",
        json=evidence("maturity_date", "2027-09-30", method="bank_letter", note="Letter ref 77"),
    )
    assert r.status_code == 201, r.text
    detail = reviewer.get(url).json()
    rows = {c["field"]: c for c in detail["comparison"]}
    assert rows["principal_amount"] | {"evidence_id": None} == {
        "field": "principal_amount",
        "label": "Principal amount",
        "claimed": "500000.00",
        "confirmed": "500000.00",
        "status": "match",
        "simulated": False,
        "evidence_id": None,
    }
    assert rows["maturity_date"]["claimed"] == "2027-10-01"
    assert rows["maturity_date"]["status"] == "mismatch"
    assert rows["bank_reference"]["status"] == "unconfirmed"
    record = detail["evidence"][1]
    assert record["source"] == "Demo National Bank, Fort branch"
    assert record["method"] == "bank_letter" and record["observer"] == "reviewer"
    assert record["observed_at"].startswith(OBSERVED[:16]) and record["note"] == "Letter ref 77"
    assert detail["claim"]["bank_reference"] == "000123-DEMO"
    assert reviewer.get("/api/v1/reviews").json()["items"][0]["confirmed_fields"] == 1
    actions = [
        e["action"] for e in alpha.get(f"/api/v1/instruments/{case['id']}/audit").json()["items"]
    ]
    assert actions.count("review.evidence_recorded") == 2


@pytest.mark.parametrize(
    "change",
    [
        {"observed_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat()},
        {"observed_at": "2026-10-01T10:00:00"},
        {"value": "500000.001"},
        {"value": "-5"},
        {"method": "uploaded_document"},
        {"field": "status"},
        {"source": "  "},
        {"note": "x" * 501},
        {"verified": True},
    ],
)
def test_invalid_evidence_is_rejected_without_trace(change, clients, actors, db):
    case = submitted(clients(), actors)
    r = clients("reviewer").post(f"/api/v1/reviews/{case['id']}/evidence", json=evidence() | change)
    assert r.status_code == 422
    assert db.scalar(select(func.count()).select_from(EvidenceRecord)) == 0


def test_dates_and_text_fields_are_validated_by_type(clients, actors):
    case = submitted(clients(), actors)
    url = f"/api/v1/reviews/{case['id']}/evidence"
    reviewer = clients("reviewer")
    assert reviewer.post(url, json=evidence("issue_date", "01-10-2026")).status_code == 422
    assert reviewer.post(url, json=evidence("bank_reference", "000123-DEMO")).status_code == 201


def test_only_assigned_reviewers_record_evidence(clients, actors, db):
    alpha, reviewer = clients(), clients("reviewer")
    case = submitted(alpha, actors)
    url = f"/api/v1/reviews/{case['id']}/evidence"
    assert alpha.post(url, json=evidence()).status_code == 403
    db.execute(delete(ReviewAssignment))
    db.commit()
    assert reviewer.post(url, json=evidence()).status_code == 404
    assert reviewer.get("/api/v1/reviews").json()["items"] == []


def test_discrepancy_conversation_is_preserved_and_resolved_once(clients, actors):
    alpha, reviewer = clients(), clients("reviewer")
    case = submitted(alpha, actors)
    raised = reviewer.post(
        f"/api/v1/reviews/{case['id']}/discrepancies",
        json={"field": "maturity_date", "message": "Bank letter shows 30 Sep 2027."},
    )
    assert raised.status_code == 201, raised.text
    reply_url = f"/api/v1/discrepancies/{raised.json()['id']}/replies"
    listed = alpha.get(f"/api/v1/instruments/{case['id']}/discrepancies").json()["items"]
    assert (
        listed[0]["message"] == "Bank letter shows 30 Sep 2027." and listed[0]["status"] == "open"
    )
    assert clients("beta").post(reply_url, json={"message": "x"}).status_code == 404
    assert clients("auditor").post(reply_url, json={"message": "x"}).status_code == 403
    assert alpha.post(reply_url, json={"message": "x", "resolve": True}).status_code == 403
    r = alpha.post(reply_url, json={"message": "Our copy says 1 Oct; we will ask the bank."})
    assert r.status_code == 201
    assert (
        reviewer.post(
            reply_url, json={"message": "Confirmed with branch.", "resolve": True}
        ).status_code
        == 201
    )
    assert reviewer.post(reply_url, json={"message": "again", "resolve": True}).status_code == 409
    assert alpha.post(reply_url, json={"message": "late"}).status_code == 409
    case_view = reviewer.get(f"/api/v1/reviews/{case['id']}").json()
    d = case_view["discrepancies"][0]
    assert d["status"] == "resolved" and d["field"] == "maturity_date"
    assert [(x["kind"], x["author"]) for x in d["replies"]] == [
        ("response", "alpha"),
        ("resolution", "reviewer"),
    ]
    assert reviewer.get("/api/v1/reviews").json()["items"][0]["open_discrepancies"] == 0


def test_concurrent_resolutions_record_one(clients, actors):
    case = submitted(clients(), actors)
    a, b = clients("reviewer"), clients("reviewer")
    raised = a.post(
        f"/api/v1/reviews/{case['id']}/discrepancies", json={"field": None, "message": "Check"}
    )
    url = f"/api/v1/discrepancies/{raised.json()['id']}/replies"
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(
            pool.map(
                lambda c: c.post(url, json={"message": "ok", "resolve": True}).status_code, [a, b]
            )
        )
    assert sorted(codes) == [201, 409]


def test_review_records_cannot_be_rewritten(clients, actors, db):
    alpha, reviewer = clients(), clients("reviewer")
    case = submitted(alpha, actors)
    reviewer.post(f"/api/v1/reviews/{case['id']}/evidence", json=evidence())
    raised = reviewer.post(f"/api/v1/reviews/{case['id']}/discrepancies", json={"message": "Check"})
    alpha.post(f"/api/v1/discrepancies/{raised.json()['id']}/replies", json={"message": "Done"})
    for table in ("evidence_records", "discrepancies", "discrepancy_replies"):
        for statement in (f"UPDATE {table} SET created_at = now()", f"DELETE FROM {table}"):
            with pytest.raises(DBAPIError):
                db.execute(text(statement))
            db.rollback()


def test_assigned_reviewer_can_download_clean_case_documents(clients, actors, db, s3, settings):
    alpha = clients()
    item = draft(alpha, actors)
    doc = upload(alpha, item["id"], pdf()).json()
    scanning.scan_pending(db, s3, settings)
    alpha.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": "docs"},
    )
    reviewer = clients("reviewer")
    case = reviewer.get(f"/api/v1/reviews/{item['id']}").json()
    assert [d["id"] for d in case["documents"]] == [doc["id"]]
    url = f"/api/v1/documents/{doc['id']}/download"
    assert reviewer.get(url).status_code == 200
    db.execute(delete(ReviewAssignment))
    db.commit()
    assert reviewer.get(url).status_code == 404
