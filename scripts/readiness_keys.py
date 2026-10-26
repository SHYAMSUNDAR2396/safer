"""Initialize local-only OpenBao and issue a short-lived least-privilege runtime token.

Unseal/recovery material and tokens are owner-only files OUTSIDE the repository and .env.
Single local custodian is demonstrational; pilot needs independent recovery/key administration.
"""

import argparse
import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path.home() / ".local/share/safer-readiness",
    )
    args = parser.parse_args()
    state = args.state_dir.resolve()
    if state.is_relative_to(ROOT) or (
        state.exists() and (state.is_symlink() or state.stat().st_uid != os.getuid())
    ):
        raise ValueError("Private key state must be outside the repository and owned by this user")
    os.umask(0o077)
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    state.chmod(0o700)
    client = httpx.Client(base_url="http://127.0.0.1:58200/v1", timeout=10, trust_env=False)
    recovery = state / "recovery.json"
    initialized = client.get("/sys/init").raise_for_status().json()["initialized"]
    if not initialized:
        if recovery.exists():
            raise RuntimeError(
                "Refusing to replace existing recovery material for a different key store"
            )
        result = (
            client.put("/sys/init", json={"secret_shares": 1, "secret_threshold": 1})
            .raise_for_status()
            .json()
        )
        recovery.write_text(json.dumps(result))
    if not recovery.exists():
        raise RuntimeError(
            "Existing key store requires its original recovery file; never reinitialize it"
        )
    if recovery.stat().st_mode & 0o077:
        raise ValueError("Recovery material has unsafe permissions")
    admin = json.loads(recovery.read_text())
    if client.get("/sys/seal-status").raise_for_status().json()["sealed"]:
        client.put("/sys/unseal", json={"key": admin["keys_base64"][0]}).raise_for_status()
    client.headers["X-Vault-Token"] = admin["root_token"]
    mounts = client.get("/sys/mounts").raise_for_status().json()["data"]
    if "transit/" not in mounts:
        client.post("/sys/mounts/transit", json={"type": "transit"}).raise_for_status()
    existing = client.get("/transit/keys/safer-data")
    if existing.status_code == 404:
        client.post(
            "/transit/keys/safer-data",
            json={
                "type": "aes256-gcm96",
                "exportable": False,
                "allow_plaintext_backup": False,
                "auto_rotate_period": "720h",
            },
        ).raise_for_status()
    else:
        existing.raise_for_status()
    client.put(
        "/sys/policies/acl/safer-runtime",
        json={"policy": (ROOT / "infra/openbao/runtime.hcl").read_text()},
    ).raise_for_status()
    token = (
        client.post(
            "/auth/token/create",
            json={
                "policies": ["safer-runtime"],
                "no_default_policy": True,
                "ttl": "1h",
                "renewable": False,
                "display_name": "safer-local-readiness",
            },
        )
        .raise_for_status()
        .json()["auth"]["client_token"]
    )
    (state / "runtime-token").write_text(token)
    (state / "runtime-token").chmod(0o600)
    print(
        f"OpenBao ready. Private credential directory: {state}. Runtime token expires in one hour. No keys printed."
    )


if __name__ == "__main__":
    main()
