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


def test_compose_settings_keep_public_identity_and_allow_only_known_local_services(settings):
    import pytest
    from pydantic import ValidationError
    from safer.config import Settings

    values = settings.model_dump() | {
        "local_transport": "compose",
        "s3_endpoint": "http://objects:8333",
        "smtp_host": "mail",
        "clamd_host": "scan-relay",
        "queue_host": "queue",
        "oidc_backchannel": "http://identity:8080/realms/safer",
        "app_origin": "https://localhost:9443",
    }
    configured = Settings(**values)
    assert configured.oidc_issuer == "http://localhost:8090/realms/safer"
    for changes in [
        {"app_mode": "production"},
        {"s3_endpoint": "http://foreign.invalid:8333"},
        {"oidc_backchannel": "http://foreign.invalid/realms/safer"},
    ]:
        with pytest.raises(ValidationError):
            Settings(**(values | changes))


def test_request_duration_header_contains_no_case_or_identity():
    with TestClient(create_app()) as client:
        response = client.get("/health/live")
    timing = response.headers.get("server-timing", "")
    assert timing.startswith("app;dur=")
    assert float(timing.split("=", 1)[1]) >= 0
