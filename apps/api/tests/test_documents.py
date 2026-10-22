import hashlib
import io
import struct
import zlib
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from pypdf import PdfWriter
from safer import documents
from safer.models import AuditEvent, Document
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from test_instruments import draft

PDF = "application/pdf"


def pdf(pages=1, password=None):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if password:
        writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def image(kind="PNG"):
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, kind)
    return out.getvalue()


def png_header(width, height):
    """Valid PNG claiming huge dimensions; pixel data is never decoded by the checker."""

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\0"))
        + chunk(b"IEND", b"")
    )


def upload(client, id, body, media=PDF, name="receipt.pdf", kind="fdr_certificate"):
    return client.post(
        f"/api/v1/instruments/{id}/documents",
        params={"filename": name, "kind": kind},
        content=body,
        headers={"Content-Type": media},
    )


def counts(db):
    return (
        db.scalar(select(func.count()).select_from(Document)),
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action.like("document.%"))
        ),
    )


def stored(s3, settings):
    pages = s3.get_paginator("list_object_versions").paginate(Bucket=settings.s3_bucket)
    return [v for page in pages for v in page.get("Versions", [])]


@pytest.mark.parametrize(
    "body,media,name",
    [
        (pdf(3), PDF, "fdr.pdf"),
        (image("PNG"), "image/png", "scan.png"),
        (image("JPEG"), "image/jpeg", "scan.jpg"),
    ],
)
def test_upload_quarantines_exact_object_version_with_audit(
    body, media, name, clients, actors, db, s3, settings
):
    c = clients()
    item = draft(c, actors)
    r = upload(c, item["id"], body, media, name)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["status"] == "quarantined" and doc["media_type"] == media
    assert doc["sha256"] == hashlib.sha256(body).hexdigest() and doc["size_bytes"] == len(body)
    assert doc["filename"] == name and "object_key" not in doc
    if media == PDF:
        assert doc["page_count"] == 3
    row = db.get(Document, doc["id"])
    obj = s3.get_object(Bucket=settings.s3_bucket, Key=row.object_key, VersionId=row.object_version)
    assert obj["Body"].read() == body
    assert c.get(f"/api/v1/instruments/{item['id']}/documents").json()["items"] == [doc]
    actions = [
        e["action"] for e in c.get(f"/api/v1/instruments/{item['id']}/audit").json()["items"]
    ]
    assert actions == ["instrument.created", "document.uploaded"]


def test_documents_are_institution_and_role_scoped(clients, actors, db, s3):
    alpha = clients()
    item = draft(alpha, actors)
    assert upload(alpha, item["id"], pdf()).status_code == 201
    beta, auditor = clients("beta"), clients("auditor")
    assert upload(beta, item["id"], pdf()).status_code == 404
    assert beta.get(f"/api/v1/instruments/{item['id']}/documents").status_code == 404
    assert upload(auditor, item["id"], pdf()).status_code == 403
    assert len(auditor.get(f"/api/v1/instruments/{item['id']}/documents").json()["items"]) == 1
    alpha.headers.pop("X-CSRF-Token")
    assert upload(alpha, item["id"], pdf()).status_code == 403
    assert counts(db) == (1, 1)


@pytest.mark.parametrize(
    "body,media,name,status",
    [
        (b"hello, not a pdf", PDF, "a.pdf", 415),
        (image("PNG"), PDF, "a.pdf", 415),
        (pdf(), "text/html", "a.html", 415),
        (b"", PDF, "a.pdf", 415),
        (b"%PDF-1.7\n" + b"\0" * (10 * 1024 * 1024), PDF, "big.pdf", 413),
        (pdf(31), PDF, "long.pdf", 422),
        (pdf(1, password="secret"), PDF, "locked.pdf", 422),
        (b"%PDF-1.4\ngarbage that is not a document", PDF, "broken.pdf", 422),
        (png_header(20000, 20000), "image/png", "bomb.png", 422),
        (png_header(7000, 7000), "image/png", "huge.png", 422),
        (b"\xff\xd8\xff\xe0 truncated", "image/jpeg", "broken.jpg", 422),
        (pdf(), PDF, "bad\x00name.pdf", 422),
        (pdf(), PDF, "", 422),
    ],
)
def test_rejected_files_leave_no_record_object_or_audit(
    body, media, name, status, clients, actors, db, s3, settings
):
    c = clients()
    item = draft(c, actors)
    r = upload(c, item["id"], body, media, name)
    assert r.status_code == status, r.text
    if name in {"long.pdf", "locked.pdf", "bomb.png", "huge.png"}:
        assert "could not be read" not in r.json()["detail"], "rejected for the specific limit"
    assert r.headers["content-type"].startswith("application/problem+json")
    assert counts(db) == (0, 0)
    assert stored(s3, settings) == []


def test_path_components_are_stripped_from_display_name(clients, actors, s3):
    c = clients()
    item = draft(c, actors)
    assert upload(c, item["id"], pdf(), name="../../etc/x.pdf").json()["filename"] == "x.pdf"


def test_submitted_record_rejects_new_documents(clients, actors, db, s3):
    c = clients()
    item = draft(c, actors)
    r = c.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": "doc-test"},
    )
    assert r.status_code == 201
    assert upload(c, item["id"], pdf()).status_code == 409
    assert counts(db) == (0, 0)


def test_document_count_is_bounded_per_record(clients, actors, s3, monkeypatch):
    monkeypatch.setattr(documents, "MAX_DOCUMENTS", 1)
    c = clients()
    item = draft(c, actors)
    assert upload(c, item["id"], pdf()).status_code == 201
    assert upload(c, item["id"], pdf()).status_code == 409


def test_storage_failure_marks_upload_failed_without_audit(clients, actors, db, s3):
    c = clients()
    item = draft(c, actors)

    def broken(**kwargs):
        from botocore.exceptions import EndpointConnectionError

        raise EndpointConnectionError(endpoint_url="http://127.0.0.1:8333")

    c.app.state.s3.put_object = broken
    r = upload(c, item["id"], pdf())
    assert r.status_code == 503 and r.json()["code"] == "storage_unavailable"
    assert db.scalar(select(Document.status)) == "failed"
    assert counts(db)[1] == 0


def test_overwritten_bytes_never_inherit_quarantined_binding(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    original = pdf()
    doc = db.get(Document, upload(c, item["id"], original).json()["id"])
    swapped = s3.put_object(Bucket=settings.s3_bucket, Key=doc.object_key, Body=b"%PDF-swap")
    assert swapped["VersionId"] != doc.object_version
    # The record stays bound to the exact version and hash it was accepted with.
    obj = s3.get_object(Bucket=settings.s3_bucket, Key=doc.object_key, VersionId=doc.object_version)
    assert hashlib.sha256(obj["Body"].read()).hexdigest() == doc.sha256
    result = documents.reconcile(db, s3, settings.s3_bucket, grace=timedelta(0))
    assert result == {"failed": 0, "removed": 1}
    assert [v["VersionId"] for v in stored(s3, settings)] == [doc.object_version]


def test_reconcile_fails_stale_pending_uploads_and_removes_their_objects(
    clients, actors, db, s3, settings
):
    c = clients()
    item = draft(c, actors)
    doc = Document(
        institution_id=actors["alpha"].institution_id,
        instrument_id=item["id"],
        filename="interrupted.pdf",
        kind="other",
        media_type=PDF,
        size_bytes=4,
        sha256="0" * 64,
        object_key="interrupted",
        uploaded_by=actors["alpha"].id,
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(doc)
    db.commit()
    s3.put_object(Bucket=settings.s3_bucket, Key="interrupted", Body=b"%PDF")
    fresh = documents.reconcile(db, s3, settings.s3_bucket)
    assert fresh == {"failed": 1, "removed": 0}, "objects inside the grace period are kept"
    assert documents.reconcile(db, s3, settings.s3_bucket, grace=timedelta(0))["removed"] == 1
    db.refresh(doc)
    assert doc.status == "failed" and stored(s3, settings) == []


def test_database_rejects_rebinding_or_deleting_documents(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    id = upload(c, item["id"], pdf()).json()["id"]
    for statement in [
        "UPDATE documents SET sha256=repeat('1', 64) WHERE id=:id",
        "UPDATE documents SET object_version='other' WHERE id=:id",
        "UPDATE documents SET status='pending' WHERE id=:id",
        "DELETE FROM documents WHERE id=:id",
    ]:
        with pytest.raises(DBAPIError):
            db.execute(text(statement), {"id": id})
        db.rollback()


def test_submission_during_upload_fails_the_upload(clients, actors, db, s3):
    c, other = clients(), clients()
    item = draft(c, actors)
    store = c.app.state.s3.put_object

    def submit_meanwhile(**kwargs):
        result = store(**kwargs)
        r = other.post(
            f"/api/v1/instruments/{item['id']}/submissions",
            json={},
            headers={"If-Match": '"1"', "Idempotency-Key": "race"},
        )
        assert r.status_code == 201
        return result

    c.app.state.s3.put_object = submit_meanwhile
    r = upload(c, item["id"], pdf())
    assert r.status_code == 409 and r.json()["code"] == "already_submitted"
    assert db.scalar(select(Document.status)) == "failed"
