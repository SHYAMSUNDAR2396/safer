from fastapi.testclient import TestClient
from safer.main import create_app


def test_unauthenticated_identity_requires_login():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "authentication_required"


def test_live_probe_has_no_financial_information():
    with TestClient(create_app()) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unauthenticated_mutation_does_not_create_record():
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/instruments", json={})
    assert response.status_code == 401
