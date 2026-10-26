"""Measure local foundation controls using only the isolated synthetic readiness profile."""

import hashlib
import json
import ssl
import urllib.request
from pathlib import Path

import psycopg
from psycopg.errors import InsufficientPrivilege
from safer.config import Settings
from safer.keys import EnvelopeCipher, TransitKeys
from safer.storage import client
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = json.loads((ROOT / ".local/readiness-paths.json").read_text())
    private = Path(paths["private_dir"])
    url = (private / "operator/runtime-host-url").read_text()
    settings = Settings(database_url=url, s3_bucket="safer-readiness-encrypted")
    raw = client(settings)
    cipher = EnvelopeCipher(
        TransitKeys("http://127.0.0.1:58200", private / "app-secrets/transit-token")
    )
    from safer.storage import EncryptedObjects

    encrypted = EncryptedObjects(raw, cipher)
    with psycopg.connect(
        make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
    ) as db:
        flags = db.execute(
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        assert flags == (False, False, False, False)
        rows = db.execute(
            "SELECT object_key,object_version,sha256 FROM documents WHERE object_version IS NOT NULL"
        ).fetchall()
        assert rows, "Run the readiness browser submission first"
        for sql in [
            "CREATE TABLE must_not_be_allowed(id integer)",
            "UPDATE audit_events SET action=action WHERE false",
            "DELETE FROM instruments WHERE false",
        ]:
            try:
                db.execute(sql)
            except InsufficientPrivilege:
                db.rollback()
            else:
                db.rollback()
                raise AssertionError("Runtime privilege boundary failed")
    for key, version, sha in rows:
        data = raw.get_object(Bucket=settings.s3_bucket, Key=key, VersionId=version)["Body"].read()
        assert json.loads(data)["schema"] == "safer-envelope-1"
        clear = encrypted.get_object(Bucket=settings.s3_bucket, Key=key, VersionId=version)[
            "Body"
        ].read()
        assert hashlib.sha256(clear).hexdigest() == sha
    trust = ssl.create_default_context(cafile=str(private / "tls/tls-cert"))
    with urllib.request.urlopen(
        "https://localhost:9443/health/ready", context=trust, timeout=5
    ) as response:
        assert json.load(response) == {"status": "ready"}
    report = {
        "phase": "SAF-027",
        "classification": "synthetic_only",
        "status": "pass",
        "scope": "local foundation only",
        "tls_exact_certificate_verified": True,
        "encrypted_objects_verified": len(rows),
        "runtime_no_superuser_or_ddl": True,
        "runtime_immutable_update_and_instrument_delete_denied": True,
        "production_activation": "blocked",
        "limitations": [
            "Local self-signed front-door TLS only; internal Compose links require pilot encryption.",
            "One local key custodian; no independent recovery administrator.",
            "Worker/storage account separation and isolated parser network remain pilot controls.",
            "Hosting/residency and external federation remain undecided.",
        ],
    }
    (ROOT / ".local/saf027-foundation-evidence.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print("Local TLS, encrypted object versions and restricted database privileges verified.")


if __name__ == "__main__":
    main()
