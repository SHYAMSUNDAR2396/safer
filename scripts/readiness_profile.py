"""Prepare separate synthetic container DB, least-privilege roles and private secret mounts."""

import ipaddress
import json
import os
import secrets
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import psycopg
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "safer_readiness"
OWNER, RUNTIME = "safer_readiness_owner", "safer_readiness_app"
IMMUTABLE = {
    "audit_events",
    "submissions",
    "evidence_records",
    "document_scans",
    "discrepancy_replies",
    "bank_responses",
    "release_events",
    "release_instructions",
    "release_executions",
    "extraction_runs",
    "extracted_fields",
}


def main():
    os.umask(0o077)
    state = Path.home() / ".local/share/safer-readiness"
    profile = state / "profile"
    for directory in [
        state,
        profile,
        profile / "operator",
        profile / "app-secrets",
        profile / "tls",
    ]:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    env = dotenv_values(ROOT / ".env")

    def credential(name):
        p = profile / "operator" / name
        if not p.exists():
            p.write_text(secrets.token_urlsafe(40))
        p.chmod(0o600)
        return p.read_text()

    source = make_url(env["DATABASE_URL"])
    with psycopg.connect(
        source.set(database="postgres", drivername="postgresql").render_as_string(
            hide_password=False
        ),
        autocommit=True,
    ) as db:
        for role, filename in [(OWNER, "migration-password"), (RUNTIME, "runtime-password")]:
            password = credential(filename)
            found = db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            if not found:
                db.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                    ).format(sql.Identifier(role), sql.Literal(password))
                )
        if not db.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone():
            db.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DATABASE), sql.Identifier(OWNER)
                )
            )
        db.execute(
            sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DATABASE))
        )
        db.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(DATABASE), sql.Identifier(RUNTIME)
            )
        )
    owner_url = source.set(
        database=DATABASE, username=OWNER, password=credential("migration-password")
    )
    migration_env = os.environ | {
        "DATABASE_URL": owner_url.render_as_string(hide_password=False),
        "S3_BUCKET": "safer-readiness-encrypted",
        "PYTHONPATH": str(ROOT / "apps/api"),
    }
    subprocess.run(
        [str(ROOT / ".venv/bin/alembic"), "upgrade", "head"],
        cwd=ROOT,
        env=migration_env,
        check=True,
    )
    subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "safer.seed"],
        cwd=ROOT,
        env=migration_env,
        check=True,
    )
    with psycopg.connect(
        owner_url.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
    ) as db:
        db.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(RUNTIME)))
        tables = [
            r[0]
            for r in db.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='alembic_version'"
            )
        ]
        for table in tables:
            grants = "SELECT, INSERT" if table in IMMUTABLE else "SELECT, INSERT, UPDATE"
            db.execute(
                sql.SQL("GRANT " + grants + " ON TABLE {} TO {}").format(
                    sql.Identifier(table), sql.Identifier(RUNTIME)
                )
            )
        db.execute(sql.SQL("GRANT DELETE ON TABLE sessions TO {}").format(sql.Identifier(RUNTIME)))
    runtime_url = source.set(
        database=DATABASE, username=RUNTIME, password=credential("runtime-password")
    )
    app_values = {
        name: env[name]
        for name in ["SESSION_SECRET", "S3_ACCESS_KEY", "S3_SECRET_KEY", "REDIS_PASSWORD"]
    }
    app_values["SESSION_SECRET"] = credential("session-signing-key")
    app_values["DATABASE_URL"] = runtime_url.set(host="db", port=5432).render_as_string(
        hide_password=False
    )
    for name, value in app_values.items():
        target = profile / "app-secrets" / name
        target.write_text(value)
        target.chmod(0o600)
    token = state / "runtime-token"
    if not token.exists():
        raise RuntimeError("Initialize Transit first with scripts/readiness_keys.py")
    (profile / "app-secrets/transit-token").write_text(token.read_text())
    keyfile = profile / "tls/tls-key"
    if not keyfile.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "SAFER LOCAL SYNTHETIC READINESS")]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(UTC) - timedelta(minutes=5))
            .not_valid_after(datetime.now(UTC) + timedelta(days=7))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        keyfile.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        (profile / "tls/tls-cert").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # Add exact local HTTPS redirect to the existing synthetic client; no wildcard origins.
    client = httpx.Client(base_url="http://localhost:8090", timeout=10, trust_env=False)
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
    c = (
        client.get("/admin/realms/safer/clients", params={"clientId": "safer-web"})
        .raise_for_status()
        .json()[0]
    )
    c["redirectUris"] = sorted(set(c["redirectUris"] + ["https://localhost:9443/auth/callback"]))
    c["webOrigins"] = sorted(set(c["webOrigins"] + ["https://localhost:9443"]))
    client.put("/admin/realms/safer/clients/" + c["id"], json=c).raise_for_status()
    # Only non-secret paths and IDs are reported.
    (ROOT / ".local/readiness-paths.json").write_text(
        json.dumps(
            {
                "private_dir": str(profile),
                "uid": str(os.getuid()),
                "gid": str(os.getgid()),
                "runtime_host_url_file": str(profile / "operator/runtime-host-url"),
            },
            indent=2,
        )
        + "\n"
    )
    (profile / "operator/runtime-host-url").write_text(
        runtime_url.render_as_string(hide_password=False)
    )
    print(
        "Separate synthetic DB, restricted runtime role, private secret mounts and local TLS certificate prepared. No secrets printed."
    )


if __name__ == "__main__":
    main()
