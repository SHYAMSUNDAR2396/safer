from datetime import date, timedelta

import pytest
from safer import deadlines
from sqlalchemy import text
from test_deadlines import at
from test_instruments import payload

TODAY = date.today()


def fdr(client, actors, ref, amount, maturity, submit=True, owner=0, issue=None):
    item = client.post(
        "/api/v1/instruments",
        json=payload(actors, owner)
        | {
            "bank_reference": ref,
            "principal_amount": amount,
            "issue_date": (issue or TODAY - timedelta(days=400)).isoformat(),
            "maturity_date": maturity.isoformat(),
        },
    ).json()
    if submit:
        r = client.post(
            f"/api/v1/instruments/{item['id']}/submissions",
            json={},
            headers={"If-Match": '"1"', "Idempotency-Key": f"k-{item['id']}"},
        )
        assert r.status_code == 201, r.text
    return item


@pytest.fixture
def portfolio(clients, actors, db):
    """Known fixture: 2 drafts, 3 active (one maturing soon), 1 closed; plus a Beta FDR."""
    alpha = clients()
    fdr(alpha, actors, "D-1", "100.00", TODAY + timedelta(days=300), submit=False)
    fdr(alpha, actors, "D-2", "200.00", TODAY + timedelta(days=300), submit=False)
    soon = fdr(alpha, actors, "S-SOON", "1000.00", TODAY + timedelta(days=10))
    fdr(alpha, actors, "S-LATER", "2000.00", TODAY + timedelta(days=200))
    fdr(
        alpha,
        actors,
        "S-MATURED",
        "3000.00",
        TODAY - timedelta(days=5),
        issue=TODAY - timedelta(days=400),
    )
    closed = fdr(alpha, actors, "C-1", "4000.00", TODAY + timedelta(days=50))
    db.execute(
        text("UPDATE instruments SET status = 'closed' WHERE id = :id"), {"id": closed["id"]}
    )
    db.commit()
    fdr(clients("beta"), actors, "BETA-1", "9999.00", TODAY + timedelta(days=10), owner=1)
    return {"soon": soon}


def metrics(client):
    data = client.get("/api/v1/dashboard").json()
    return {m["key"]: (m["count"], m["amount"]) for m in data["metrics"]}


def test_lifecycle_totals_reconcile_to_fixture_and_register(clients, actors, portfolio):
    alpha = clients()
    m = metrics(alpha)
    assert m["draft"] == (2, "300.00")
    assert m["active"] == (3, "6000.00")
    assert m["closed"] == (1, "4000.00")
    summary = alpha.get("/api/v1/instruments").json()["summary"]
    total = sum(m[k][0] for k in ("draft", "active", "closed"))
    amount = sum(float(m[k][1]) for k in ("draft", "active", "closed"))
    assert total == summary["total"] == 6
    assert f"{amount:.2f}" == summary["recorded_amount"]


def test_attention_metrics_use_their_documented_grain(clients, actors, db, portfolio):
    alpha = clients()
    m = metrics(alpha)
    assert m["maturing_30"] == (1, "1000.00"), "only active FDRs maturing within 30 days"
    assert m["matured_uncovered"] == (1, "3000.00")
    assert m["action_overdue"] == (0, "0.00")
    deadlines.sweep(db, at(TODAY, 1))
    m = metrics(alpha)
    assert m["action_overdue"][0] == 2 and m["escalated"][0] == 2


def test_resolved_actions_leave_the_queue(clients, actors, db, portfolio):
    alpha = clients()
    later = fdr(alpha, actors, "S-NEW", "5000.00", TODAY + timedelta(days=500))
    alpha.post(
        f"/api/v1/instruments/{portfolio['soon']['id']}/replacement",
        json={"successor_id": later["id"]},
    )
    deadlines.sweep(db, at(TODAY, 1))
    drill = alpha.get("/api/v1/dashboard/action_overdue").json()["items"]
    assert "S-SOON" not in [i["bank_reference"] for i in drill]


def test_drill_down_lists_exactly_what_is_counted(clients, actors, portfolio):
    alpha = clients()
    data = alpha.get("/api/v1/dashboard").json()
    for metric in data["metrics"]:
        drill = alpha.get(f"/api/v1/dashboard/{metric['key']}").json()
        assert len(drill["items"]) == metric["count"], metric["key"]
        total = sum(float(i["principal_amount"]) for i in drill["items"])
        assert f"{total:.2f}" == metric["amount"], metric["key"]
        assert metric["grain"] and metric["label"]
    assert alpha.get("/api/v1/dashboard/everything").status_code == 404


def test_scope_follows_institution_and_authority(clients, actors, db, portfolio):
    assert metrics(clients("beta"))["active"] == (1, "9999.00")
    reviewer = metrics(clients("reviewer"))
    assert reviewer["active"] == (3, "6000.00"), "reviewer sees Alpha only"
    assert "draft" not in reviewer, "drafts are institution-private"
    assert metrics(clients("auditor"))["draft"] == (2, "300.00")
    db.execute(text("UPDATE grants SET status = 'revoked', revoked_at = now()"))
    db.commit()
    assert metrics(clients("reviewer"))["active"] == (0, "0.00")
    drill = clients("beta").get("/api/v1/dashboard/active").json()["items"]
    assert [i["bank_reference"] for i in drill] == ["BETA-1"]


def test_coverage_is_reported_per_obligation(clients, actors, portfolio):
    data = clients().get("/api/v1/dashboard").json()
    cover = data["coverage"][0]
    assert cover["required_amount"] == "500000.00" and cover["covered_amount"] == "6000.00"
    assert cover["gap_amount"] == "494000.00"


def test_release_work_queues(clients, actors, db, setup):
    from test_releases import clear_all, decide, request

    alpha = clients()
    item = fdr(alpha, actors, "R-1", "700.00", TODAY + timedelta(days=100))
    req = request(alpha, item).json()
    assert metrics(clients("reviewer2"))["releases_clearing"] == (1, "700.00")
    clear_all(clients("reviewer"), req)
    assert metrics(clients("reviewer2"))["releases_ready"] == (1, "700.00")
    decide(clients("reviewer2"), req)
    assert metrics(clients("reviewer2"))["releases_to_instruct"] == (1, "700.00")
