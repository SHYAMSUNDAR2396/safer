"""Configure password-only login for every LOCAL SYNTHETIC demo account.

The historical script name is retained for existing setup commands. Passwords
are restored from the private demo-users.json inventory, never embedded in code.
"""

import json
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
FLOW = "safer-password-only"


def configure():
    env = dotenv_values(ROOT / ".env")
    users = json.loads((ROOT / ".local/demo-users.json").read_text())
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
        base = "/admin/realms/safer"
        flows = client.get(base + "/authentication/flows").raise_for_status().json()
        if not any(f["alias"] == FLOW for f in flows):
            client.post(
                base + "/authentication/flows/browser/copy", json={"newName": FLOW}
            ).raise_for_status()
        execution_url = base + f"/authentication/flows/{FLOW}/executions"
        executions = client.get(execution_url).raise_for_status().json()
        # Disable the entire second-factor subflow, including for enrolled users.
        twofactor = next(e for e in executions if "Conditional 2FA" in e["displayName"])
        client.put(execution_url, json=twofactor | {"requirement": "DISABLED"}).raise_for_status()
        client.put(base, json={"browserFlow": FLOW, "rememberMe": False}).raise_for_status()
        for user in users:
            user_url = base + f"/users/{user['id']}"
            current = client.get(user_url).raise_for_status().json()
            actions = [a for a in current.get("requiredActions", []) if a != "CONFIGURE_TOTP"]
            client.put(user_url, json={"requiredActions": actions}).raise_for_status()
            client.put(
                user_url + "/reset-password",
                json={"type": "password", "value": user["password"], "temporary": False},
            ).raise_for_status()
        print(
            f"Password-only login configured for {len(users)} demo users. Fixed demo passwords synchronized; no secrets printed."
        )


if __name__ == "__main__":
    configure()
