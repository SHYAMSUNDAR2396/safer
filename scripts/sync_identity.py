"""Add missing LOCAL-DEMO users to a running Keycloak, keeping their fixed subject ids.

Keycloak imports the realm only on first start; run this after bootstrap adds users.
"""

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://localhost:8090"
env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if "=" in line)
realm = json.loads((ROOT / ".local" / "realm.json").read_text())
token = (
    httpx.post(
        f"{BASE}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "local-admin",
            "password": env["KEYCLOAK_ADMIN_PASSWORD"],
        },
        timeout=10,
    )
    .raise_for_status()
    .json()["access_token"]
)
result = (
    httpx.post(
        f"{BASE}/admin/realms/safer/partialImport",
        headers={"Authorization": f"Bearer {token}"},
        json={"ifResourceExists": "SKIP", "users": realm["users"]},
        timeout=30,
    )
    .raise_for_status()
    .json()
)
print(f"Identity users added: {result['added']}, already present: {result['skipped']}.")
