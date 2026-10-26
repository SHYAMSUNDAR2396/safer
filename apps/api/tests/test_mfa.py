from safer.models import SessionRow
from sqlalchemy import select


def test_privileged_password_only_session_is_rejected(clients, db):
    c = clients("reviewer")
    row = db.scalar(select(SessionRow))
    row.mfa_verified = False
    db.commit()
    r = c.get("/api/v1/me")
    assert r.status_code == 401 and r.json()["code"] == "mfa_required"


def test_institution_session_does_not_gain_privileged_access(clients, actors, db):
    c = clients()
    row = db.scalar(select(SessionRow))
    row.mfa_verified = False
    db.commit()
    assert c.get("/api/v1/me").status_code == 200
    actors["alpha"].role = "reviewer"
    db.commit()
    assert c.get("/api/v1/reviews").status_code == 401


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
