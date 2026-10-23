from datetime import date

import pytest
from safer import policies
from safer.models import Obligation, Policy
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

RULES = {"clearances": ["no_dues_certificate"], "release_not_before": "obligation_end"}


def draft(client, applies_to="*", effective_from="2026-01-01", until=None, rules=RULES):
    return client.post(
        "/api/v1/admin/policies",
        json={
            "code": "release",
            "applies_to": applies_to,
            "effective_from": effective_from,
            "effective_until": until,
            "rules": rules,
            "note": "Illustrative release rules",
        },
    )


def published(clients, **kw):
    d = draft(clients("admin1"), **kw).json()
    r = clients("admin2").post(f"/api/v1/admin/policies/{d['id']}/publish", json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_publication_needs_a_second_administrator(clients, actors):
    admin1 = clients("admin1")
    d = draft(admin1)
    assert d.status_code == 201 and d.json()["status"] == "draft" and d.json()["version"] == 1
    url = f"/api/v1/admin/policies/{d.json()['id']}/publish"
    assert admin1.post(url, json={}).status_code == 403
    r = clients("admin2").post(url, json={})
    assert r.json()["status"] == "published"
    assert r.json()["drafted_by"] == "admin1" and r.json()["published_by"] == "admin2"
    assert r.json()["owner_validated"] is False
    assert clients("admin2").post(url, json={}).status_code == 409


@pytest.mark.parametrize(
    "rules",
    [
        {"clearances": [], "release_not_before": "obligation_end"},
        {"clearances": ["bribe"], "release_not_before": "obligation_end"},
        {
            "clearances": ["no_dues_certificate", "no_dues_certificate"],
            "release_not_before": "any_time",
        },
        {"clearances": ["no_dues_certificate"], "release_not_before": "tomorrow"},
        {
            "clearances": ["no_dues_certificate"],
            "release_not_before": "any_time",
            "auto_release": True,
        },
    ],
)
def test_rules_are_validated_against_a_strict_schema(rules, clients, actors):
    assert draft(clients("admin1"), rules=rules).status_code == 422


def test_only_admins_draft_or_publish(clients, actors):
    for name in ("alpha", "reviewer", "auditor"):
        assert draft(clients(name)).status_code == 403


def test_versions_resolve_by_effective_date(clients, actors, db):
    v1 = published(clients)
    v2 = published(
        clients,
        effective_from="2027-01-01",
        rules={
            "clearances": ["no_dues_certificate", "closure_approval_letter"],
            "release_not_before": "obligation_end",
        },
    )
    assert (v1["version"], v2["version"]) == (1, 2)
    obligation = db.get(Obligation, actors["obligations"][0].id)
    assert policies.resolve(db, "release", obligation, date(2026, 6, 1)).version == 1
    assert policies.resolve(db, "release", obligation, date(2027, 6, 1)).version == 2
    assert policies.resolve(db, "release", obligation, date(2025, 6, 1)) is None


def test_drafts_never_apply(clients, actors, db):
    draft(clients("admin1"))
    obligation = db.get(Obligation, actors["obligations"][0].id)
    assert policies.resolve(db, "release", obligation, date(2026, 6, 1)) is None


def test_specific_applicability_beats_general(clients, actors, db):
    published(clients)
    specific = published(clients, applies_to="approval_security_deposit")
    obligation = db.get(Obligation, actors["obligations"][0].id)
    assert str(policies.resolve(db, "release", obligation, date(2026, 6, 1)).id) == specific["id"]
    obligation.kind = "other_deposit"
    db.commit()
    assert policies.resolve(db, "release", obligation, date(2026, 6, 1)).applies_to == "*"


def test_effective_until_ends_a_version(clients, actors, db):
    published(clients, until="2026-12-31")
    obligation = db.get(Obligation, actors["obligations"][0].id)
    assert policies.resolve(db, "release", obligation, date(2026, 12, 30)) is not None
    assert policies.resolve(db, "release", obligation, date(2026, 12, 31)) is None


def test_institutions_read_the_policy_that_applies_to_them(clients, actors):
    published(clients)
    url = f"/api/v1/obligations/{actors['obligations'][0].id}/policy?on=2026-06-01"
    view = clients().get(url).json()
    assert view["version"] == 1 and view["rules"] == RULES
    assert clients("beta").get(url).status_code == 404


def test_snapshot_and_published_rules_are_frozen(clients, actors, db):
    p = published(clients)
    snapshot = policies.snapshot(db.get(Policy, p["id"]))
    assert snapshot == {
        "policy_id": p["id"],
        "code": "release",
        "version": 1,
        "rules": RULES,
        "owner_validated": False,
    }
    for statement in (
        "UPDATE policies SET rules = '{}'::jsonb",
        "UPDATE policies SET status = 'draft'",
        "DELETE FROM policies",
    ):
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()
