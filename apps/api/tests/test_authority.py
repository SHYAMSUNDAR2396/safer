from datetime import UTC, datetime, timedelta

import pytest
from safer.models import Grant
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from test_reviews import submitted

SOON = (datetime.now(UTC) + timedelta(days=30)).isoformat()


def request_grant(client, actors, user, authority="review", institution=None, until=SOON):
    return client.post(
        "/api/v1/admin/grants",
        json={
            "user_id": str(actors[user].id),
            "authority": authority,
            "institution_id": str(institution or actors["alpha"].institution_id),
            "valid_until": until,
            "reason": "Portfolio cover",
        },
    )


def queue(client):
    return client.get("/api/v1/reviews").json()["items"]


def test_review_grant_takes_effect_once_granted(clients, actors):
    case = submitted(clients(), actors)
    reviewer2 = clients("reviewer2")
    assert queue(reviewer2) == []
    r = request_grant(clients("admin1"), actors, "reviewer2")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active" and r.json()["approved_by"] == "admin1"
    assert [q["instrument_id"] for q in queue(reviewer2)] == [case["id"]]


def test_sensitive_grant_needs_a_second_admin(clients, actors, db):
    admin1, admin2 = clients("admin1"), clients("admin2")
    grant = request_grant(admin1, actors, "reviewer2", "release_approve").json()
    assert grant["status"] == "pending"
    url = f"/api/v1/admin/grants/{grant['id']}"
    assert admin1.post(url + "/approve", json={}).status_code == 403, "no self-approval"
    assert clients("reviewer2").post(url + "/approve", json={}).status_code == 403
    r = admin2.post(url + "/approve", json={})
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert r.json()["requested_by"] == "admin1" and r.json()["approved_by"] == "admin2"
    assert admin2.post(url + "/approve", json={}).status_code == 409


def test_database_enforces_dual_control(clients, actors, db):
    grant = request_grant(clients("admin1"), actors, "reviewer2", "release_approve").json()
    with pytest.raises(DBAPIError):
        db.execute(
            text(
                "UPDATE grants SET status = 'active', approved_by = requested_by, decided_at = now()"
                " WHERE id = :id"
            ),
            {"id": grant["id"]},
        )
    db.rollback()


@pytest.mark.parametrize(
    "grantee,authority,status",
    [
        ("admin1", "review", 422),  # an admin granting themselves
        ("admin2", "review", 422),  # admins never hold case authority
        ("alpha", "review", 422),  # institution users cannot review
        ("auditor", "release_approve", 422),
    ],
)
def test_no_self_escalation_or_role_crossing(grantee, authority, status, clients, actors, db):
    assert request_grant(clients("admin1"), actors, grantee, authority).status_code == status
    assert (
        db.scalar(select(func.count()).select_from(Grant).where(Grant.reason == "Portfolio cover"))
        == 0
    )


def test_no_authority_over_your_own_institution(clients, actors):
    r = request_grant(
        clients("admin1"), actors, "reviewer2", institution=actors["reviewer2"].institution_id
    )
    assert r.status_code == 422


def test_only_admins_manage_grants(clients, actors):
    for name in ("reviewer", "alpha", "auditor"):
        assert request_grant(clients(name), actors, "reviewer2").status_code == 403
        assert clients(name).get("/api/v1/admin/grants").status_code == 403


def test_duplicate_live_grant_is_refused(clients, actors):
    admin1 = clients("admin1")
    assert request_grant(admin1, actors, "reviewer2").status_code == 201
    assert request_grant(admin1, actors, "reviewer2").status_code == 409


def test_expired_grants_confer_nothing(clients, actors, db):
    submitted(clients(), actors)
    db.add(
        Grant(
            user_id=actors["reviewer2"].id,
            authority="review",
            institution_id=actors["alpha"].institution_id,
            status="active",
            valid_until=datetime.now(UTC) - timedelta(seconds=1),
            reason="Expired cover",
        )
    )
    db.commit()
    assert queue(clients("reviewer2")) == []
    assert request_grant(clients("admin1"), actors, "reviewer2").status_code == 201


def test_revocation_is_immediate_and_cascades_to_delegations(clients, actors, db):
    case = submitted(clients(), actors)
    reviewer, reviewer2 = clients("reviewer"), clients("reviewer2")
    mine = reviewer.get("/api/v1/grants/mine").json()["held"][0]
    r = reviewer.post(
        f"/api/v1/grants/{mine['id']}/delegate",
        json={"user_id": str(actors["reviewer2"].id), "valid_until": SOON, "reason": "Leave"},
    )
    assert r.status_code == 201 and r.json()["status"] == "active"
    assert queue(reviewer2)[0]["instrument_id"] == case["id"]
    admin = clients("admin1")
    assert (
        admin.post(
            f"/api/v1/admin/grants/{mine['id']}/revoke", json={"reason": "Moved"}
        ).status_code
        == 200
    )
    assert reviewer.get(f"/api/v1/reviews/{case['id']}").status_code == 404
    assert queue(reviewer2) == [], "delegated authority ends with its source"


@pytest.mark.parametrize(
    "change,status",
    [
        ({"user_id": "reviewer"}, 422),  # to self
        ({"user_id": "alpha"}, 422),  # to a non-reviewer
        ({"valid_until": (datetime.now(UTC) + timedelta(days=400)).isoformat()}, 422),
    ],
)
def test_delegation_cannot_widen_authority(change, status, clients, actors, db):
    reviewer = clients("reviewer")
    # The seeded grant expires in 90 days, so a 400-day delegation would outlive it.
    db.execute(
        text("UPDATE grants SET status = 'revoked', revoked_at = now() WHERE status = 'active'")
    )
    db.add(
        Grant(
            user_id=actors["reviewer"].id,
            authority="review",
            institution_id=actors["alpha"].institution_id,
            status="active",
            valid_until=datetime.now(UTC) + timedelta(days=90),
            reason="Limited cover",
        )
    )
    db.commit()
    mine = reviewer.get("/api/v1/grants/mine").json()["held"][0]
    body = {"user_id": str(actors["reviewer2"].id), "valid_until": SOON, "reason": "Leave"}
    if "user_id" in change:
        body["user_id"] = str(actors[change["user_id"]].id)
    else:
        body |= change
    assert reviewer.post(f"/api/v1/grants/{mine['id']}/delegate", json=body).status_code == status


def test_delegations_cannot_be_redelegated_and_sensitive_ones_need_approval(clients, actors):
    admin1, admin2 = clients("admin1"), clients("admin2")
    release = request_grant(admin1, actors, "reviewer", "release_approve").json()
    admin2.post(f"/api/v1/admin/grants/{release['id']}/approve", json={})
    reviewer = clients("reviewer")
    delegated = reviewer.post(
        f"/api/v1/grants/{release['id']}/delegate",
        json={"user_id": str(actors["reviewer2"].id), "valid_until": SOON, "reason": "Leave"},
    ).json()
    assert delegated["status"] == "pending", "delegated release authority needs an admin"
    review = reviewer.get("/api/v1/grants/mine").json()["held"]
    review_grant = next(g for g in review if g["authority"] == "review")
    child = reviewer.post(
        f"/api/v1/grants/{review_grant['id']}/delegate",
        json={"user_id": str(actors["reviewer2"].id), "valid_until": SOON, "reason": "Leave"},
    ).json()
    again = clients("reviewer2").post(
        f"/api/v1/grants/{child['id']}/delegate",
        json={"user_id": str(actors["reviewer"].id), "valid_until": SOON, "reason": "x"},
    )
    assert again.status_code == 422


def test_grant_history_cannot_be_rewritten(clients, actors, db):
    request_grant(clients("admin1"), actors, "reviewer2")
    for statement in (
        "UPDATE grants SET authority = 'release_approve'",
        "UPDATE grants SET user_id = requested_by",
        "DELETE FROM grants",
    ):
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()
    listed = clients("admin2").get("/api/v1/admin/grants").json()["items"]
    assert any(g["user"] == "reviewer2" and g["requested_by"] == "admin1" for g in listed)
