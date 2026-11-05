from unittest.mock import AsyncMock

import pytest
from safer.models import SessionRow
from sqlalchemy import select


@pytest.mark.parametrize(
    "name", ["alpha", "beta", "auditor", "reviewer", "reviewer2", "admin1", "admin2"]
)
def test_every_demo_role_accepts_password_only_session(clients, db, name):
    c = clients(name)
    row = db.scalar(select(SessionRow))
    row.mfa_verified = False
    db.commit()
    r = c.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["display_name"] == name


def test_password_only_institution_session_keeps_role_restrictions(clients, actors, db):
    c = clients()
    row = db.scalar(select(SessionRow))
    row.mfa_verified = False
    db.commit()
    assert c.get("/api/v1/me").status_code == 200
    assert c.get("/api/v1/reviews").status_code == 403


@pytest.mark.parametrize("name", ["reviewer", "reviewer2", "admin1", "admin2"])
def test_password_only_oidc_callback_creates_privileged_session(
    clients, actors, db, name, monkeypatch
):
    c = clients(name)
    user = actors[name]
    monkeypatch.setattr(
        c.app.state.oauth.portal,
        "authorize_access_token",
        AsyncMock(return_value={"userinfo": {"iss": user.issuer, "sub": user.subject, "acr": "1"}}),
    )
    response = c.get("/auth/callback", follow_redirects=False)
    assert response.status_code == 303
    assert c.get("/api/v1/me").status_code == 200
    assert db.scalar(select(SessionRow)).mfa_verified is False


def test_only_explicit_verified_mfa_assurance_is_accepted():
    from safer.auth import has_mfa_assurance

    assert has_mfa_assurance({"acr": "2"})
    for claims in [
        {},
        {"acr": "1"},
        {"acr": True},
        {"acr": "mfa"},
        {"amr": ["pwd"]},
        {"mfa": True},
    ]:
        assert not has_mfa_assurance(claims)


def test_cleanup_selects_only_explicitly_owned_synthetic_enrollments():
    from safer.fixture_identity import owned_test_credentials

    rows = [
        {"id": "owned", "type": "otp", "userLabel": "Synthetic test authenticator"},
        {"id": "personal", "type": "otp", "userLabel": "Personal device"},
        {"id": "password", "type": "password", "userLabel": "Synthetic test authenticator"},
        {"id": "similar", "type": "otp", "userLabel": "Synthetic test authenticator personal"},
    ]
    assert owned_test_credentials(rows) == ["owned"]
