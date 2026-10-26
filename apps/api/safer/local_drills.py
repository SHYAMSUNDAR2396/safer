"""Synthetic-only local audit and database recovery component drills.

Does not exercise independent custody, PITR, complete object/identity/key loss or pilot DR.
Recovered database is new and never connected to a worker; external effects stay paused.
"""

import argparse
import hashlib
import json
import os
import re
import smtplib
import subprocess
import time
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

import httpx
import psycopg
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.engine import make_url

from safer.audit_archive import alerts, checkpoint, recent_window, verify_checkpoint
from safer.keys import EnvelopeCipher, TransitKeys

ROOT = Path(__file__).resolve().parents[3]


def validate_restore_name(name: str) -> str:
    if not re.fullmatch(r"safer_restore_synthetic_[0-9a-f]{12}", name):
        raise ValueError("Restore target must be a new isolated synthetic drill database")
    return name


def private_profile():
    paths = json.loads((ROOT / ".local/readiness-paths.json").read_text())
    profile = Path(paths["private_dir"])
    cipher = EnvelopeCipher(
        TransitKeys("http://127.0.0.1:58200", profile / "app-secrets/transit-token")
    )
    url = make_url((profile / "operator/runtime-host-url").read_text()).set(drivername="postgresql")
    if url.database != "safer_readiness":
        raise ValueError("Drills only use the separate synthetic readiness database")
    return profile, cipher, url


def archive_drill() -> dict:
    profile, cipher, url = private_profile()
    with psycopg.connect(url.render_as_string(hide_password=False)) as db:
        rows = [
            {
                "id": str(r[0]),
                "created_at": r[1].isoformat(),
                "action": r[2],
                "actor_id": str(r[3]),
                "institution_id": str(r[4]),
                "request_id": r[5],
            }
            for r in db.execute(
                "SELECT id,created_at,action,actor_id,institution_id,request_id FROM audit_events ORDER BY created_at,id"
            )
        ]
    if not rows:
        raise ValueError("Run synthetic readiness browser workflow before archival drill")
    manifest = checkpoint(rows)
    context = {
        "institution_id": "synthetic-regulation",
        "object_id": "audit-" + manifest["sha256"],
        "purpose": "audit-checkpoint",
    }
    envelope = cipher.encrypt(json.dumps(rows).encode(), context)
    archive_dir = profile / "archives"
    archive_dir.mkdir(mode=0o700, exist_ok=True)
    file = archive_dir / f"audit-{manifest['sha256']}.json"
    file.write_text(json.dumps({"context": context, "envelope": envelope}))
    # Local operator anchor is separate from app-mounted directories; not independent WORM custody.
    (profile / "operator" / f"audit-{manifest['sha256']}-checkpoint.json").write_text(
        json.dumps(manifest)
    )
    restored = json.loads(cipher.decrypt(envelope, context))
    assert verify_checkpoint(restored, manifest)
    assert not verify_checkpoint(restored[:-1], manifest)
    now = datetime.now(UTC)
    events = [
        {"source": "application", "kind": "access_denied", "at": now.isoformat()} for _ in range(10)
    ]
    events += [
        {"source": source, "kind": kind, "at": now.isoformat()}
        for source, kind in [
            ("identity", "mfa_reset"),
            ("kms", "key_delete_attempt"),
            ("backup", "stale"),
            ("audit", "gap"),
            ("authority", "sensitive_grant_change"),
        ]
    ]
    notices = alerts(recent_window(events, now))
    marker = "SYNTHETIC-SECURITY-" + uuid.uuid4().hex
    msg = EmailMessage()
    msg["From"] = "safer-readiness@example.invalid"
    msg["To"] = "security-owner@example.invalid"
    msg["Subject"] = marker
    msg.set_content(json.dumps(notices))
    with smtplib.SMTP("127.0.0.1", 51025, timeout=5) as smtp:
        smtp.send_message(msg)
    with httpx.Client(timeout=5, trust_env=False) as client:
        captured = client.get("http://127.0.0.1:58025/api/v1/messages").raise_for_status().json()
    assert any(m.get("Subject") == marker for m in captured["messages"])
    return {
        "phase": "SAF-028",
        "status": "pass",
        "classification": "synthetic_only",
        "scope": "local archive integrity and capture-only alerts",
        "audit_rows": len(rows),
        "checkpoint_sha256": manifest["sha256"],
        "alert_rules_tested": len(notices),
        "local_delivery_verified": True,
        "pilot_status": "blocked",
        "limitations": [
            "Local checkpoint owner is not independent retention-locked custody.",
            "Enterprise SIEM connectors and named responders are not configured.",
            "Retention/legal hold periods require approval.",
            "Archive contains a minimal event projection; full business audit remains in its source DB.",
        ],
    }


def table_counts(db) -> dict:
    tables = [
        r[0]
        for r in db.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='alembic_version'"
        )
    ]
    return {
        table: db.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        ).fetchone()[0]
        for table in sorted(tables)
    }


def recovery_drill() -> dict:
    profile, cipher, url = private_profile()
    started = time.monotonic()
    checkpoint_time = datetime.now(UTC)
    with psycopg.connect(url.render_as_string(hide_password=False)) as db:
        before = table_counts(db)
    command = [str(ROOT / "scripts/compose.sh"), "exec", "-T", "db"]
    dumped = subprocess.run(
        command + ["pg_dump", "-U", "safer", "-d", "safer_readiness", "-Fc"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    context = {
        "institution_id": "synthetic-regulation",
        "object_id": "database-" + uuid.uuid4().hex,
        "purpose": "backup-drill",
    }
    encrypted = cipher.encrypt(dumped, context)
    directory = profile / "backups"
    directory.mkdir(exist_ok=True, mode=0o700)
    archive = directory / (context["object_id"] + ".json")
    archive.write_text(json.dumps({"context": context, "envelope": encrypted}))
    restored = cipher.decrypt(encrypted, context)
    assert hashlib.sha256(restored).digest() == hashlib.sha256(dumped).digest()
    target = validate_restore_name("safer_restore_synthetic_" + uuid.uuid4().hex[:12])
    # createdb refuses an existing database; no DROP, overwrite, --clean or worker startup.
    subprocess.run(
        command + ["createdb", "-U", "safer", target],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        command
        + [
            "pg_restore",
            "-U",
            "safer",
            "-d",
            target,
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
        ],
        cwd=ROOT,
        input=restored,
        capture_output=True,
        check=True,
        timeout=60,
    )
    env = dotenv_values(ROOT / ".env")
    admin_url = make_url(env["DATABASE_URL"]).set(drivername="postgresql", database=target)
    with psycopg.connect(admin_url.render_as_string(hide_password=False)) as db:
        after = table_counts(db)
        assert after == before, (
            "Concurrent source writes require a quiesced rerun; do not claim consistency"
        )
    return {
        "phase": "SAF-029",
        "status": "incomplete",
        "classification": "synthetic_only",
        "scope": "database backup encryption and isolated restore component",
        "database_component": "pass",
        "new_database": target,
        "tables_reconciled": len(before),
        "rows_reconciled": sum(before.values()),
        "backup_sha256": hashlib.sha256(dumped).hexdigest(),
        "component_restore_seconds": round(time.monotonic() - started, 3),
        "checkpoint_age_seconds": round((datetime.now(UTC) - checkpoint_time).total_seconds(), 3),
        "external_effects": "paused; no worker or notification sender uses restored DB",
        "pilot_status": "blocked",
        "limitations": [
            "Not a complete disaster-recovery or PITR exercise.",
            "Original object store, identity and key service remained available; their loss/recovery is not measured.",
            "No independent backup administrator or compromised-primary-credential exercise.",
            "Component duration and checkpoint age do not prove whole-system RPO/RTO.",
            "Scratch recovery DB is intentionally preserved for inspection.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["audit", "recovery"])
    args = parser.parse_args()
    os.umask(0o077)
    result = archive_drill() if args.phase == "audit" else recovery_drill()
    file = ROOT / ".local" / f"{result['phase'].lower()}-evidence.json"
    file.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['phase']} local result: {result['status']}; real-data pilot remains blocked.")


if __name__ == "__main__":
    main()
