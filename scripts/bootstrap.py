"""Generate private LOCAL-DEMO configuration. Never replaces existing secrets."""

import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.umask(0o077)
local = ROOT / ".local"
local.mkdir(exist_ok=True)
local.chmod(0o700)


def object_store():
    """Add private object-store credentials, also to an existing .env, without replacing others."""
    env_path = ROOT / ".env"
    env = dict(line.split("=", 1) for line in env_path.read_text().splitlines() if "=" in line)
    if "S3_SECRET_KEY" not in env:
        env["S3_ACCESS_KEY"], env["S3_SECRET_KEY"] = "safer-api", secrets.token_urlsafe(32)
        with env_path.open("a") as f:
            f.write(
                "S3_ENDPOINT=http://127.0.0.1:8333\nS3_BUCKET=safer-documents\n"
                f"S3_ACCESS_KEY={env['S3_ACCESS_KEY']}\nS3_SECRET_KEY={env['S3_SECRET_KEY']}\n"
            )
    if "REDIS_PASSWORD" not in env:
        with env_path.open("a") as f:
            f.write(f"REDIS_PASSWORD={secrets.token_urlsafe(32)}\n")
    identity = {"accessKey": env["S3_ACCESS_KEY"], "secretKey": env["S3_SECRET_KEY"]}
    actions = ["Admin", "Read", "Write", "List", "Tagging"]
    config = {"identities": [{"name": "safer-api", "credentials": [identity], "actions": actions}]}
    (local / "s3.json").write_text(json.dumps(config, indent=2))
    # Containers read these as non-root users; the 0700 .local directory keeps them private.
    for mounted in ("s3.json", "realm.json"):
        (local / mounted).chmod(0o644)


DEMO = [
    ("alpha", "00000000-0000-4000-8000-000000000001"),
    ("beta", "00000000-0000-4000-8000-000000000002"),
    ("auditor", "00000000-0000-4000-8000-000000000003"),
    ("reviewer", "00000000-0000-4000-8000-000000000004"),
]


def realm_user(u):
    return {
        "id": u["id"],
        "username": u["username"],
        "enabled": True,
        "firstName": u["username"].title(),
        "lastName": "Demo",
        "email": u["username"] + "@example.invalid",
        "emailVerified": True,
        "credentials": [{"type": "password", "value": u["password"], "temporary": False}],
    }


def demo_users():
    """Add demo users introduced after first setup; scripts/sync_identity.py loads them."""
    users_path, realm_path = local / "demo-users.json", local / "realm.json"
    users, realm = json.loads(users_path.read_text()), json.loads(realm_path.read_text())
    known = {u["username"] for u in users}
    for name, subject in DEMO:
        if name not in known:
            user = {"username": name, "id": subject, "password": secrets.token_urlsafe(18)}
            users.append(user)
            realm["users"].append(realm_user(user))
    users_path.write_text(json.dumps(users, indent=2))
    realm_path.write_text(json.dumps(realm, indent=2))


if (ROOT / ".env").exists():
    object_store()
    demo_users()
    print("Existing .env preserved. Local credentials: .local/demo-users.json")
    raise SystemExit(0)

password = secrets.token_urlsafe(24)
users = []
for name, subject in DEMO:
    users.append({"username": name, "id": subject, "password": secrets.token_urlsafe(18)})

realm = {
    "realm": "safer",
    "enabled": True,
    "displayName": "SAFER · Synthetic demonstration",
    "registrationAllowed": False,
    "resetPasswordAllowed": False,
    "bruteForceProtected": True,
    "clients": [
        {
            "clientId": "safer-web",
            "enabled": True,
            "publicClient": True,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "redirectUris": ["http://localhost:5173/auth/callback"],
            "webOrigins": ["http://localhost:5173"],
            "attributes": {"pkce.code.challenge.method": "S256"},
        }
    ],
    "users": [realm_user(u) for u in users],
}
(local / "realm.json").write_text(json.dumps(realm, indent=2))
(local / "demo-users.json").write_text(json.dumps(users, indent=2))
(ROOT / ".env").write_text(
    "APP_MODE=local\nAPP_ORIGIN=http://localhost:5173\n"
    f"DATABASE_URL=postgresql+psycopg://safer:{password}@localhost:55432/safer\n"
    f"TEST_DATABASE_URL=postgresql+psycopg://safer:{password}@localhost:55432/safer_test\n"
    "OIDC_ISSUER=http://localhost:8090/realms/safer\nOIDC_CLIENT_ID=safer-web\n"
    f"SESSION_SECRET={secrets.token_urlsafe(48)}\nPOSTGRES_PASSWORD={password}\n"
    f"KEYCLOAK_ADMIN_PASSWORD={secrets.token_urlsafe(32)}\n"
)
object_store()
print("Created private .env, identity import, and .local/demo-users.json. No secrets printed.")
