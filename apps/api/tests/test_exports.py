import csv
import io
from datetime import date, timedelta

from safer import exports, jobs
from safer.models import AuditEvent, Export, Job, User
from sqlalchemy import select, text, update
from test_dashboard import fdr

TODAY = date.today()


def run_jobs(db, s3, settings):
    ids = db.scalars(select(Job.id).where(Job.kind == "build_export", Job.status == "queued")).all()
    return [jobs.run(db, i, jobs.Context(s3=s3, settings=settings)) for i in ids]


def requested(client, metric="active"):
    r = client.post("/api/v1/exports", json={"metric": metric})
    assert r.status_code == 202, r.text
    return r.json()


def rows(response):
    return list(csv.reader(io.StringIO(response.text)))


def test_export_builds_asynchronously_and_matches_the_dashboard(clients, actors, db, s3, settings):
    alpha = clients()
    fdr(alpha, actors, "EXP-1", "1000.00", TODAY + timedelta(days=50))
    fdr(alpha, actors, "EXP-2", "2000.00", TODAY + timedelta(days=60))
    export = requested(alpha)
    assert export["status"] == "queued"
    url = f"/api/v1/exports/{export['id']}/download"
    assert alpha.get(url).status_code == 409, "not ready yet"
    assert run_jobs(db, s3, settings) == ["succeeded"]
    listed = alpha.get("/api/v1/exports").json()["items"][0]
    assert listed["status"] == "ready" and listed["row_count"] == 2
    r = alpha.get(url)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"].startswith("attachment;")
    table = rows(r)
    assert table[0][:3] == ["FDR reference", "Bank", "Institution"]
    assert sorted(row[0] for row in table[1:]) == ["EXP-1", "EXP-2"]
    actions = db.scalars(select(AuditEvent.action).where(AuditEvent.action.like("export.%"))).all()
    assert sorted(actions) == ["export.built", "export.downloaded", "export.requested"]


def test_cells_cannot_become_spreadsheet_formulas(clients, actors, db, s3, settings):
    alpha = clients()
    item = alpha.post(
        "/api/v1/instruments",
        json={
            "obligation_id": str(actors["obligations"][0].id),
            "bank_name": '=HYPERLINK("http://example.invalid","x")',
            "bank_reference": "+REF-1",
            "principal_amount": "10.00",
            "issue_date": "2026-01-01",
            "maturity_date": "2027-01-01",
        },
    ).json()
    export = requested(alpha, "draft")
    run_jobs(db, s3, settings)
    table = rows(alpha.get(f"/api/v1/exports/{export['id']}/download"))
    assert table[1][0] == "'+REF-1" and table[1][1].startswith("'=HYPERLINK")
    assert item["bank_reference"] == "+REF-1", "stored data itself is unchanged"
    assert exports.safe_cell("@SUM(A1)") == "'@SUM(A1)" and exports.safe_cell("plain") == "plain"


def test_authorization_is_rechecked_when_the_job_runs(clients, actors, db, s3, settings):
    fdr(clients(), actors, "EXP-3", "1000.00", TODAY + timedelta(days=50))
    export = requested(clients("reviewer"))
    db.execute(text("UPDATE grants SET status = 'revoked', revoked_at = now()"))
    db.commit()
    run_jobs(db, s3, settings)
    row = db.get(Export, export["id"])
    assert row.status == "failed" and row.object_key is None
    assert "authority" in row.error


def test_authorization_is_rechecked_at_download(clients, actors, db, s3, settings):
    fdr(clients(), actors, "EXP-4", "1000.00", TODAY + timedelta(days=50))
    reviewer = clients("reviewer")
    export = requested(reviewer)
    run_jobs(db, s3, settings)
    url = f"/api/v1/exports/{export['id']}/download"
    assert reviewer.get(url).status_code == 200
    db.execute(text("UPDATE grants SET status = 'revoked', revoked_at = now()"))
    db.commit()
    assert reviewer.get(url).status_code == 403


def test_exports_expire_and_are_purged(clients, actors, db, s3, settings):
    alpha = clients()
    fdr(alpha, actors, "EXP-5", "1000.00", TODAY + timedelta(days=50))
    export = requested(alpha)
    run_jobs(db, s3, settings)
    key = db.get(Export, export["id"]).object_key
    db.execute(update(Export).values(expires_at=text("now() - interval '1 second'")))
    db.commit()
    assert alpha.get(f"/api/v1/exports/{export['id']}/download").status_code == 410
    assert exports.purge(db, s3, settings) == 1
    db.expire_all()
    assert db.get(Export, export["id"]).purged_at is not None
    listing = s3.list_object_versions(Bucket=settings.s3_bucket, Prefix=key)
    assert not listing.get("Versions")


def test_exports_are_private_to_their_owner(clients, actors, db, s3, settings):
    alpha, beta = clients(), clients("beta")
    fdr(alpha, actors, "EXP-6", "1000.00", TODAY + timedelta(days=50))
    export = requested(alpha)
    run_jobs(db, s3, settings)
    assert beta.get(f"/api/v1/exports/{export['id']}/download").status_code == 404
    assert clients("auditor").get(f"/api/v1/exports/{export['id']}/download").status_code == 404
    assert beta.get("/api/v1/exports").json()["items"] == []
    beta_export = requested(beta)
    run_jobs(db, s3, settings)
    table = rows(beta.get(f"/api/v1/exports/{beta_export['id']}/download"))
    assert "EXP-6" not in [r[0] for r in table]


def test_only_visible_metrics_can_be_exported(clients, actors):
    assert clients().post("/api/v1/exports", json={"metric": "nonsense"}).status_code == 422
    assert clients("reviewer").post("/api/v1/exports", json={"metric": "draft"}).status_code == 422
    assert clients("admin1").post("/api/v1/exports", json={"metric": "active"}).status_code == 403


def test_duplicate_delivery_builds_once(clients, actors, db, s3, settings):
    alpha = clients()
    fdr(alpha, actors, "EXP-7", "1000.00", TODAY + timedelta(days=50))
    export = requested(alpha)
    job = db.scalar(select(Job).where(Job.kind == "build_export"))
    exports.build(
        db,
        jobs.Context(s3=s3, settings=settings),
        exports.ExportPayload(export_id=export["id"]),
        final=False,
    )
    first = db.get(Export, export["id"]).object_key
    exports.build(
        db,
        jobs.Context(s3=s3, settings=settings),
        exports.ExportPayload(export_id=export["id"]),
        final=False,
    )
    db.expire_all()
    assert db.get(Export, export["id"]).object_key == first
    assert job is not None


def test_deactivated_owner_gets_nothing(clients, actors, db, s3, settings):
    alpha = clients()
    export = requested(alpha)
    db.execute(update(User).where(User.subject == "alpha").values(active=False))
    db.commit()
    run_jobs(db, s3, settings)
    assert db.get(Export, export["id"]).status == "failed"
