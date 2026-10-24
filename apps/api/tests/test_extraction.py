from safer import extraction, jobs
from safer.models import Document, EvidenceRecord, ExtractionRun, Instrument, Job
from sqlalchemy import func, select
from test_documents import image, upload
from test_instruments import draft

RECEIPT = [
    "Demo National Bank",
    "Fixed Deposit Receipt",
    "FDR No: 000123-DEMO",
    "Deposit Amount: Rs. 5,00,000.00",
    "Date of Deposit: 01/10/2026",
    "Maturity Date: 01/10/2027",
    "Bank Name: Demo National Bank",
]


def text_pdf(lines: list[str]) -> bytes:
    """A real one-page PDF with a Helvetica text layer, one line per entry."""
    ops = "".join(
        f"BT /F1 11 Tf 72 {760 - 18 * i} Td ({line}) Tj ET\n" for i, line in enumerate(lines)
    )
    stream = ops.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return body


def processed(c, actors, db, s3, settings, body=None, media="application/pdf", name="receipt.pdf"):
    item = draft(c, actors)
    doc = upload(c, item["id"], body or text_pdf(RECEIPT), media, name).json()
    ctx = jobs.Context(s3=s3, settings=settings)
    for kind in ("scan_document", "extract_document"):
        for id in db.scalars(select(Job.id).where(Job.kind == kind, Job.status == "queued")).all():
            jobs.run(db, id, ctx)
    return item, doc


def fields(client, doc):
    data = client.get(f"/api/v1/documents/{doc['id']}/extraction").json()
    return data, {f["field"]: f for f in data["fields"]}


def test_clean_text_pdf_yields_positioned_proposals(clients, actors, db, s3, settings):
    c = clients()
    item, doc = processed(c, actors, db, s3, settings)
    data, f = fields(c, doc)
    assert data["status"] == "completed" and data["extractor"] == extraction.VERSION
    assert data["text_layer"] is True
    assert f["bank_reference"]["value"] == "000123-DEMO"
    assert f["principal_amount"]["value"] == "500000.00"
    assert f["issue_date"]["value"] == "2026-10-01"
    assert f["maturity_date"]["value"] == "2027-10-01"
    assert f["bank_name"]["value"] == "Demo National Bank"
    ref = f["bank_reference"]
    assert ref["status"] == "proposed" and ref["page"] == 1
    assert ref["x"] == 72 and ref["y"] > 700 and "FDR No" in ref["snippet"]


def test_ambiguous_or_missing_fields_abstain(clients, actors, db, s3, settings):
    lines = [line for line in RECEIPT if not line.startswith("Maturity")] + [
        "Amount: Rs. 4,00,000.00"
    ]
    c = clients()
    _, doc = processed(c, actors, db, s3, settings, text_pdf(lines))
    _, f = fields(c, doc)
    assert f["principal_amount"]["status"] == "abstained"
    assert "different values" in f["principal_amount"]["reason"]
    assert f["maturity_date"] == {
        **f["maturity_date"],
        "status": "abstained",
        "value": None,
        "reason": "Not found in the document text.",
    }
    assert f["bank_reference"]["status"] == "proposed"


def test_impossible_values_abstain_rather_than_guess(clients, actors, db, s3, settings):
    lines = [
        "FDR No: 000999-DEMO",
        "Deposit Amount: Rs. 1,00,000.00",
        "Date of Deposit: 31/02/2026",
    ]
    c = clients()
    _, doc = processed(c, actors, db, s3, settings, text_pdf(lines))
    _, f = fields(c, doc)
    assert f["issue_date"]["status"] == "abstained" and "valid" in f["issue_date"]["reason"]


def test_images_fall_back_to_manual_entry(clients, actors, db, s3, settings):
    c = clients()
    _, doc = processed(c, actors, db, s3, settings, image("PNG"), "image/png", "scan.png")
    data, f = fields(c, doc)
    assert data["status"] == "manual_required" and data["text_layer"] is False
    assert {x["status"] for x in f.values()} == {"abstained"}


def test_unscanned_documents_are_never_parsed(clients, actors, db, s3, settings):
    c = clients()
    item = draft(c, actors)
    doc = upload(c, item["id"], text_pdf(RECEIPT)).json()
    assert (
        db.scalar(select(func.count()).select_from(Job).where(Job.kind == "extract_document")) == 0
    )
    r = c.get(f"/api/v1/documents/{doc['id']}/extraction")
    assert r.status_code == 409 and r.json()["code"] == "not_available"


def test_extraction_inherits_document_access(clients, actors, db, s3, settings):
    _, doc = processed(clients(), actors, db, s3, settings)
    url = f"/api/v1/documents/{doc['id']}/extraction"
    assert clients("beta").get(url).status_code == 404
    assert clients("auditor").get(url).status_code == 200
    assert clients("reviewer").get(url).status_code == 404, "draft cases are not reviewable"


def test_proposals_never_change_claims_or_become_evidence(clients, actors, db, s3, settings):
    lines = [line.replace("5,00,000.00", "4,50,000.00") for line in RECEIPT]
    c = clients()
    item, doc = processed(c, actors, db, s3, settings, text_pdf(lines))
    assert db.get(Instrument, item["id"]).principal_amount == 500000
    assert db.scalar(select(func.count()).select_from(EvidenceRecord)) == 0
    c.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": "ex"},
    )
    case = clients("reviewer").get(f"/api/v1/reviews/{item['id']}").json()
    rows = {r["field"]: r for r in case["comparison"]}
    assert rows["principal_amount"]["extracted"] == "450000.00"
    assert rows["principal_amount"]["extracted_differs"] is True
    assert rows["principal_amount"]["status"] == "unconfirmed", "extraction is not evidence"


def test_unreadable_pdf_fails_safely(clients, actors, db, s3, settings, monkeypatch):
    monkeypatch.setattr(extraction, "text_lines", lambda data: None)
    c = clients()
    _, doc = processed(c, actors, db, s3, settings)
    data, _ = fields(c, doc)
    assert data["status"] == "failed"
    assert db.scalar(select(func.count()).select_from(ExtractionRun)) == 1
    assert db.get(Document, doc["id"]).status == "quarantined"
