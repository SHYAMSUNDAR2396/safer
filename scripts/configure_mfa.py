"""Configure privileged TOTP on the existing LOCAL SYNTHETIC Keycloak realm.

Idempotent copy of browser flow; original flow remains available for reviewed rollback.
Federation is a realm configuration concern; no external identity/provider calls occur here.
"""

import json
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
FLOW = "safer-privileged-mfa"
ROLE = "safer-mfa-required"


def configure():
    env = dotenv_values(ROOT / ".env")
    client = httpx.Client(base_url="http://localhost:8090", timeout=15, trust_env=False)
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
    base = "/admin/realms/safer"
    role = client.get(base + "/roles/" + ROLE)
    if role.status_code == 404:
        client.post(
            base + "/roles",
            json={"name": ROLE, "description": "Privileged synthetic SAFER users require TOTP"},
        ).raise_for_status()
    else:
        role.raise_for_status()
    role = client.get(base + "/roles/" + ROLE).raise_for_status().json()
    users = json.loads((ROOT / ".local/demo-users.json").read_text())
    for user in users:
        if user["username"] in {"reviewer", "reviewer2", "admin1", "admin2"}:
            client.post(
                base + f"/users/{user['id']}/role-mappings/realm", json=[role]
            ).raise_for_status()
    flows = client.get(base + "/authentication/flows").raise_for_status().json()
    if not any(f["alias"] == FLOW for f in flows):
        client.post(
            base + "/authentication/flows/browser/copy", json={"newName": FLOW}
        ).raise_for_status()
    execution_url = base + f"/authentication/flows/{FLOW}/executions"
    executions = client.get(execution_url).raise_for_status().json()
    twofactor = next(e for e in executions if "Conditional 2FA" in e["displayName"])
    subflow = (
        client.get(base + f"/authentication/flows/{twofactor['flowId']}")
        .raise_for_status()
        .json()["alias"]
    )
    # Disable conditions based on already-enrolled credentials: new privileged users must enroll.
    in_twofactor = False
    for e in executions:
        if e["id"] == twofactor["id"]:
            in_twofactor = True
        elif in_twofactor and e["level"] <= twofactor["level"]:
            in_twofactor = False
        if in_twofactor and e.get("providerId") in {
            "conditional-user-configured",
            "conditional-credential",
        }:
            client.put(execution_url, json=e | {"requirement": "DISABLED"}).raise_for_status()
        if in_twofactor and e.get("providerId") == "auth-otp-form":
            client.put(execution_url, json=e | {"requirement": "REQUIRED"}).raise_for_status()
    for provider, config in [
        ("conditional-user-role", {"condUserRole": ROLE, "negate": "false"}),
        ("conditional-level-of-authentication", {"loa-condition-level": "2", "loa-max-age": "0"}),
    ]:
        executions = client.get(execution_url).raise_for_status().json()
        found = next((e for e in executions if e.get("providerId") == provider), None)
        if found is None:
            client.post(
                base + f"/authentication/flows/{subflow}/executions/execution",
                json={"provider": provider},
            ).raise_for_status()
            found = next(
                e
                for e in client.get(execution_url).raise_for_status().json()
                if e.get("providerId") == provider
            )
        client.put(execution_url, json=found | {"requirement": "REQUIRED"}).raise_for_status()
        if found.get("authenticationConfig"):
            cid = found["authenticationConfig"]
            client.put(
                base + f"/authentication/config/{cid}",
                json={"id": cid, "alias": "safer-" + provider, "config": config},
            ).raise_for_status()
        else:
            client.post(
                base + f"/authentication/executions/{found['id']}/config",
                json={"alias": "safer-" + provider, "config": config},
            ).raise_for_status()
    # Conditions are evaluated before authenticators regardless of UI priority.
    client.put(
        base,
        json={
            "browserFlow": FLOW,
            "otpPolicyType": "totp",
            "otpPolicyAlgorithm": "HmacSHA1",
            "otpPolicyDigits": 6,
            "otpPolicyPeriod": 30,
            "otpPolicyLookAheadWindow": 1,
            "rememberMe": False,
        },
    ).raise_for_status()
    print("Local privileged TOTP flow configured. Four demo users must enroll; no secrets printed.")


if __name__ == "__main__":
    configure()
