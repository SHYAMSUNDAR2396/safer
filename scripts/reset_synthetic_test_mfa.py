"""Remove only labelled browser-test OTP factors on four fixed local fixture accounts.

Run after browser checks so a person can enroll their own authenticator on next login.
Personal/unknown factors are preserved. This is not a general MFA reset tool.
"""

import argparse
import json
from pathlib import Path

import httpx
from dotenv import dotenv_values
from safer.fixture_identity import owned_test_credentials
from safer.models import SessionRow, User
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    name: f"00000000-0000-4000-8000-00000000000{suffix}"
    for name, suffix in [("reviewer", 4), ("admin1", 5), ("admin2", 6), ("reviewer2", 7)]
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-fixtures-only", action="store_true", required=True)
    parser.parse_args()
    env = dotenv_values(ROOT / ".env")
    users = json.loads((ROOT / ".local/demo-users.json").read_text())
    selected = {u["username"]: u["id"] for u in users if u["username"] in FIXTURES}
    if selected != FIXTURES:
        raise ValueError("Fixed synthetic subject inventory does not match; no action taken")
    urls = [env["DATABASE_URL"]]
    profile = Path.home() / ".local/share/safer-readiness/profile/operator/runtime-host-url"
    if profile.exists():
        urls.append(profile.read_text().strip())
    for value in urls:
        url = make_url(value)
        if url.host not in {"localhost", "127.0.0.1"} or url.database not in {
            "safer",
            "safer_readiness",
        }:
            raise ValueError("Only the two named local synthetic databases are permitted")

    changed = []
    with httpx.Client(base_url="http://localhost:8090", timeout=15, trust_env=False) as client:
        token = (
            client.post(
                "/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": "local-admin",
                    "password": env["KEYCLOAK_ADMIN_PASSWORD"],
                },
            )
            .raise_for_status()
            .json()["access_token"]
        )
        client.headers["Authorization"] = "Bearer " + token
        for subject in FIXTURES.values():
            base = f"/admin/realms/safer/users/{subject}"
            credentials = client.get(base + "/credentials").raise_for_status().json()
            owned = owned_test_credentials(credentials)
            for credential_id in owned:
                client.delete(base + "/credentials/" + credential_id).raise_for_status()
            if owned:
                client.post(base + "/logout").raise_for_status()
                changed.append(subject)
    for value in urls:
        engine = create_engine(value)
        with engine.begin() as conn:
            conn.execute(
                delete(SessionRow).where(
                    SessionRow.user_id.in_(
                        select(User.id).where(
                            User.subject.in_(changed),
                            User.issuer == "http://localhost:8090/realms/safer",
                        )
                    )
                )
            )
        engine.dispose()
    print(
        f"Removed browser-owned factors on {len(changed)} local synthetic users; personal factors preserved. MFA remains required at next login."
    )


if __name__ == "__main__":
    main()
