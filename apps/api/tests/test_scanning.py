import hashlib
import io
from uuid import uuid4

import pytest
from safer import scanning
from safer.models import AuditEvent, Document, DocumentScan
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_documents import PDF, pdf, upload
from test_instruments import draft

EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def stored(db, s3, settings, actors, item, body, sha256=None, kind="fdr_certificate"):
    """A quarantined document whose bytes bypassed upload checks (e.g. EICAR)."""
    key = f"test/{uuid4()}"
    put = s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=body)
    doc = Document(
        institution_id=actors["alpha"].institution_id,
        instrument_id=item["id"],
        filename="sample.pdf",
        kind=kind,
        media_type=PDF,
        size_bytes=len(body),
        sha256=sha256 or hashlib.sha256(body).hexdigest(),
        object_key=key,
        object_version=put["VersionId"],
        status="quarantined",
        uploaded_by=actors["alpha"].id,
    )
    db.add(doc)
    db.commit()
    return doc


def scan_status(client, item):
    items = client.get(f"/api/v1/instruments/{item['id']}/documents").json()["items"]
    return [d["scan_status"] for d in items]


def actions(client, item):
    events = client.get(f"/api/v1/instruments/{item['id']}/audit").json()["items"]
    return [(e["action"], e["actor"]) for e in events]


def test_clean_upload_is_scanned_then_downloadable_with_audit(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    body = pdf(2)
    doc = upload(c, item["id"], body).json()
    url = f"/api/v1/documents/{doc['id']}/download"
    assert doc["scan_status"] == "pending"
    assert c.get(url).json()["code"] == "not_available"
    assert scanning.scan_pending(db, s3, settings) == {"clean": 1}
    assert scan_status(c, item) == ["clean"]
    r = c.get(url)
    assert r.status_code == 200 and r.content == body
    assert r.headers["content-type"] == PDF
    assert r.headers["content-disposition"].startswith("attachment;")
    assert "sandbox" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"
    assert actions(c, item) == [
        ("instrument.created", "alpha"),
        ("document.uploaded", "alpha"),
        ("document.scanned", "SAFER malware scanner"),
        ("document.downloaded", "alpha"),
    ]
    assert scanning.scan_pending(db, s3, settings) == {}, "terminal results are not rescanned"


def test_infected_file_stays_blocked(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    doc = stored(db, s3, settings, actors, item, EICAR)
    assert scanning.scan_pending(db, s3, settings) == {"infected": 1}
    assert scan_status(c, item) == ["infected"]
    assert c.get(f"/api/v1/documents/{doc.id}/download").status_code == 409
    scan = db.scalar(select(DocumentScan))
    assert scan.signature == "Eicar-Test-Signature" and scan.engine.startswith("ClamAV")
    assert scanning.scan_pending(db, s3, settings) == {}


def test_bytes_not_matching_upload_hash_are_never_scanned_clean(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    doc = stored(db, s3, settings, actors, item, pdf(), sha256="0" * 64)
    assert scanning.scan_pending(db, s3, settings) == {"mismatch": 1}
    assert scan_status(c, item) == ["rejected"]
    assert c.get(f"/api/v1/documents/{doc.id}/download").status_code == 409


def test_scanner_outage_retries_then_leaves_file_quarantined(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    doc = stored(db, s3, settings, actors, item, pdf())
    down = settings.model_copy(update={"clamd_port": 1})
    for _ in range(scanning.MAX_ATTEMPTS):
        assert scan_status(c, item) == ["pending"]
        assert scanning.scan_pending(db, s3, down) == {"error": 1}
    assert scanning.scan_pending(db, s3, down) == {}
    assert scan_status(c, item) == ["failed"]
    assert c.get(f"/api/v1/documents/{doc.id}/download").status_code == 409
    failed = db.scalars(
        select(AuditEvent.action).where(AuditEvent.action == "document.scan_failed")
    ).all()
    assert len(failed) == 1


def test_clean_result_for_other_bytes_never_applies(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    doc = stored(db, s3, settings, actors, item, pdf())
    db.add(
        DocumentScan(
            document_id=doc.id,
            object_version="some-other-version",
            sha256=doc.sha256,
            outcome="clean",
            engine="forged",
        )
    )
    db.commit()
    assert scan_status(c, item) == ["pending"]
    assert c.get(f"/api/v1/documents/{doc.id}/download").status_code == 409


def test_overwriting_the_key_after_scanning_serves_the_scanned_version(
    clients, actors, db, s3, settings
):
    c = clients()
    item = draft(c, actors)
    body = pdf()
    doc = upload(c, item["id"], body).json()
    scanning.scan_pending(db, s3, settings)
    row = db.get(Document, doc["id"])
    s3.put_object(Bucket=settings.s3_bucket, Key=row.object_key, Body=EICAR)
    assert c.get(f"/api/v1/documents/{doc['id']}/download").content == body


def test_download_refuses_bytes_that_fail_integrity(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    doc = upload(c, item["id"], pdf()).json()
    scanning.scan_pending(db, s3, settings)
    c.app.state.s3.get_object = lambda **kw: {"Body": io.BytesIO(b"%PDF-tampered")}
    r = c.get(f"/api/v1/documents/{doc['id']}/download")
    assert r.status_code == 409 and r.json()["code"] == "integrity_failed"
    assert ("document.downloaded", "alpha") not in actions(c, item)


def test_downloads_are_institution_scoped_and_auditors_may_read(clients, actors, db, s3, settings):
    alpha = clients()
    item = draft(alpha, actors)
    doc = upload(alpha, item["id"], pdf()).json()
    scanning.scan_pending(db, s3, settings)
    url = f"/api/v1/documents/{doc['id']}/download"
    assert clients("beta").get(url).status_code == 404
    assert clients("auditor").get(url).status_code == 200
    assert alpha.get(f"/api/v1/documents/{uuid4()}/download").status_code == 404


def test_scan_history_is_immutable(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    stored(db, s3, settings, actors, item, EICAR)
    scanning.scan_pending(db, s3, settings)
    for statement in [
        "UPDATE document_scans SET outcome='clean'",
        "DELETE FROM document_scans",
    ]:
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()
