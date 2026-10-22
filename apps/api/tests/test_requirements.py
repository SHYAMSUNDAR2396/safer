from safer import scanning
from safer.models import AuditEvent, Obligation, Submission
from sqlalchemy import func, select
from test_documents import pdf, upload
from test_instruments import draft
from test_scanning import EICAR, stored


def require(db, actors, *kinds):
    obligation = db.get(Obligation, actors["obligations"][0].id)
    obligation.required_documents = list(kinds)
    db.commit()


def submit(client, item, version=1, key="req"):
    return client.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": f'"{version}"', "Idempotency-Key": key},
    )


def documents(client, item):
    return client.get(f"/api/v1/instruments/{item['id']}/documents").json()


def test_new_obligations_require_an_fdr_certificate_by_default(db, actors):
    obligation = Obligation(
        institution_id=actors["alpha"].institution_id, title="Default", required_amount="1.00"
    )
    db.add(obligation)
    db.commit()
    db.refresh(obligation)
    assert obligation.required_documents == ["fdr_certificate"]


def test_submission_waits_for_clean_required_documents(clients, actors, db, s3, settings):
    require(db, actors, "fdr_certificate", "bank_letter")
    c = clients()
    item = draft(c, actors)
    r = submit(c, item)
    assert r.status_code == 409 and r.json()["code"] == "documents_required"
    assert "FDR certificate" in r.json()["detail"] and "Bank covering letter" in r.json()["detail"]
    certificate = upload(c, item["id"], pdf(), kind="fdr_certificate").json()
    upload(c, item["id"], pdf(), name="other.pdf", kind="other")
    assert [(q["kind"], q["satisfied"]) for q in documents(c, item)["requirements"]] == [
        ("fdr_certificate", False),
        ("bank_letter", False),
    ]
    scanning.scan_pending(db, s3, settings)
    assert submit(c, item).json()["detail"].endswith("Bank covering letter.")
    letter = upload(c, item["id"], pdf(), name="letter.pdf", kind="bank_letter").json()
    assert submit(c, item).status_code == 409, "an unscanned document does not count"
    scanning.scan_pending(db, s3, settings)
    assert all(q["satisfied"] for q in documents(c, item)["requirements"])
    r = submit(c, item)
    assert r.status_code == 201, r.text
    refs = r.json()["snapshot"]["documents"]
    assert [(d["id"], d["kind"]) for d in refs] == [
        (certificate["id"], "fdr_certificate"),
        (letter["id"], "bank_letter"),
    ] + [(refs[2]["id"], "other")]
    assert all(d["sha256"] and d["object_version"] for d in refs)
    assert submit(c, item).status_code == 200, "replay still returns the original submission"
    assert db.scalar(select(func.count()).select_from(Submission)) == 1


def test_rejected_attempts_leave_no_trace(clients, actors, db, s3):
    require(db, actors, "fdr_certificate")
    c = clients()
    item = draft(c, actors)
    assert submit(c, item).status_code == 409
    assert c.get(f"/api/v1/instruments/{item['id']}").json()["status"] == "draft"
    actions = db.scalars(select(AuditEvent.action)).all()
    assert "instrument.submitted" not in actions


def test_correction_supersedes_without_erasing_history(clients, actors, db, s3, settings):
    require(db, actors, "fdr_certificate")
    c = clients()
    item = draft(c, actors)
    infected = stored(db, s3, settings, actors, item, EICAR)
    scanning.scan_pending(db, s3, settings)
    assert submit(c, item).status_code == 409, "the current certificate is infected"
    corrected = upload(c, item["id"], pdf(), name="corrected.pdf").json()
    scanning.scan_pending(db, s3, settings)
    listed = {d["id"]: d for d in documents(c, item)["items"]}
    assert listed[str(infected.id)]["current"] is False
    assert listed[str(infected.id)]["scan_status"] == "infected"
    assert listed[corrected["id"]]["current"] is True
    refs = submit(c, item).json()["snapshot"]["documents"]
    assert [d["id"] for d in refs] == [corrected["id"]]


def test_latest_upload_of_a_kind_is_the_one_that_counts(clients, actors, db, s3, settings):
    require(db, actors, "fdr_certificate")
    c = clients()
    item = draft(c, actors)
    upload(c, item["id"], pdf())
    scanning.scan_pending(db, s3, settings)
    upload(c, item["id"], pdf(2), name="newer.pdf")
    assert submit(c, item).status_code == 409, "newer certificate is still being scanned"


def test_other_documents_never_satisfy_a_requirement(clients, actors, db, s3, settings):
    require(db, actors, "fdr_certificate")
    c = clients()
    item = draft(c, actors)
    upload(c, item["id"], pdf(), kind="other")
    scanning.scan_pending(db, s3, settings)
    assert submit(c, item).status_code == 409


def test_unknown_document_kind_is_rejected(clients, actors, db, s3):
    c = clients()
    item = draft(c, actors)
    assert upload(c, item["id"], pdf(), kind="cheque").status_code == 422


def test_obligations_publish_their_requirements(clients, actors, db):
    require(db, actors, "fdr_certificate", "bank_letter")
    items = clients().get("/api/v1/obligations").json()["items"]
    assert items[0]["required_documents"] == ["fdr_certificate", "bank_letter"]
