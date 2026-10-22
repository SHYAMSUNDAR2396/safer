from datetime import UTC, datetime, timedelta

from safer.models import SessionRow
from sqlalchemy import select


def test_identity_comes_from_provisioned_membership(clients, actors):
    r = clients().get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["institution"]["id"] == str(actors["alpha"].institution_id)
    assert r.json()["role"] == "institution_user"
    assert r.json()["csrf_token"]
    assert r.headers["cache-control"] == "no-store"


def test_deactivated_user_cannot_reuse_session(clients, actors, db):
    c = clients()
    actors["alpha"].active = False
    db.commit()
    assert c.get("/api/v1/me").status_code == 401


def test_idle_expiry_is_enforced(clients, db):
    c = clients()
    row = db.scalar(select(SessionRow))
    row.last_seen_at = datetime.now(UTC) - timedelta(minutes=31)
    db.commit()
    assert c.get("/api/v1/me").status_code == 401


def test_absolute_expiry_is_enforced(clients, db):
    c = clients()
    row = db.scalar(select(SessionRow))
    row.created_at = datetime.now(UTC) - timedelta(hours=9)
    db.commit()
    assert c.get("/api/v1/me").status_code == 401


def test_csrf_and_origin_required_on_logout(clients):
    c = clients()
    assert c.post("/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert c.post("/auth/logout", headers={"Origin": "https://attacker.invalid"}).status_code == 403
    assert c.get("/api/v1/me").status_code == 200
    assert c.post("/auth/logout").status_code == 204
    assert c.get("/api/v1/me").status_code == 401


def test_auditor_has_no_write_permission(clients):
    c = clients("auditor")
    assert c.post("/api/v1/instruments", json={}).status_code == 403


def test_invalid_oidc_callback_rejected_without_session(clients):
    c = clients()
    c.cookies.clear()
    r = c.get("/auth/callback?code=fake&state=fake", follow_redirects=False)
    assert r.status_code == 400
    assert "safer_session=" not in r.headers.get("set-cookie", "")
