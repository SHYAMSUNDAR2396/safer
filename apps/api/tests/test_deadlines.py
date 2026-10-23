from datetime import date, datetime, timedelta

import pytest
from safer import deadlines
from safer.models import Obligation, Reminder, ReminderSchedule, ReviewAssignment
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from test_instruments import payload

TODAY = date.today()


def submitted(client, actors, maturity: date, issue: date | None = None):
    issue = issue or TODAY - timedelta(days=200)
    item = client.post(
        "/api/v1/instruments",
        json=payload(actors)
        | {"issue_date": issue.isoformat(), "maturity_date": maturity.isoformat()},
    ).json()
    r = client.post(
        f"/api/v1/instruments/{item['id']}/submissions",
        json={},
        headers={"If-Match": '"1"', "Idempotency-Key": f"k-{item['id']}"},
    )
    assert r.status_code == 201, r.text
    return item


def steps(db, item):
    return sorted(
        db.scalars(select(Reminder.step).where(Reminder.instrument_id == item["id"])).all()
    )


def at(day: date, minutes=0) -> datetime:
    return deadlines.due_at(day) + timedelta(minutes=minutes)


def test_drafts_get_no_reminders(clients, actors, db):
    clients().post(
        "/api/v1/instruments",
        json=payload(actors) | {"maturity_date": (TODAY + timedelta(days=5)).isoformat()},
    )
    assert deadlines.sweep(db, at(TODAY + timedelta(days=5))) == 0


def test_reminder_fires_at_its_due_time_and_not_before(clients, actors, db):
    maturity = TODAY + timedelta(days=100)
    submitted(clients(), actors, maturity)
    first = maturity - timedelta(days=90)
    assert deadlines.sweep(db, at(first, -1)) == 0
    assert deadlines.sweep(db, at(first, 1)) == 1
    reminder = db.scalar(select(Reminder))
    assert reminder.step == "reminder:90" and reminder.owner_role == "institution"
    assert reminder.schedule_version == 1 and reminder.late is False


def test_missed_runs_catch_up_without_duplicates(clients, actors, db):
    maturity = TODAY + timedelta(days=100)
    item = submitted(clients(), actors, maturity)
    later = at(maturity - timedelta(days=29))
    assert deadlines.sweep(db, later) == 4
    assert steps(db, item) == ["action_due", "reminder:30", "reminder:60", "reminder:90"]
    assert deadlines.sweep(db, later) == 0
    late = dict(db.execute(select(Reminder.step, Reminder.late)).all())
    assert late["reminder:90"] is True and late["action_due"] is True


def test_fifteen_minute_target_is_measured(clients, actors, db):
    maturity = TODAY + timedelta(days=100)
    submitted(clients(), actors, maturity)
    deadlines.sweep(db, at(maturity - timedelta(days=90), 14))
    deadlines.sweep(db, at(maturity - timedelta(days=60), 16))
    late = dict(db.execute(select(Reminder.step, Reminder.late)).all())
    assert late == {"reminder:90": False, "reminder:60": True}


def test_reminders_due_before_submission_are_skipped_but_overdue_action_is_not(clients, actors, db):
    maturity = TODAY + timedelta(days=10)
    item = submitted(clients(), actors, maturity)
    deadlines.sweep(db, at(TODAY, 1))
    # 90/60/30-day notices are moot after submission; the overdue action (and its
    # escalation, 13 days past due) still apply.
    assert steps(db, item) == ["action_due", "escalation"]


def test_unresolved_action_escalates_to_the_assigned_reviewer(clients, actors, db):
    maturity = TODAY + timedelta(days=40)
    item = submitted(clients(), actors, maturity)
    action = maturity - timedelta(days=30)
    deadlines.sweep(db, at(action + timedelta(days=7), 1))
    escalation = db.scalar(select(Reminder).where(Reminder.step == "escalation"))
    assert escalation.owner_role == "reviewer"
    reviewer = clients("reviewer")
    assert reviewer.get("/api/v1/reviews").json()["items"][0]["escalated"] is True
    view = clients().get(f"/api/v1/instruments/{item['id']}/deadlines").json()
    assert view["escalation_owners"] == ["reviewer"]
    db.execute(delete(ReviewAssignment))
    db.commit()
    view = clients().get(f"/api/v1/instruments/{item['id']}/deadlines").json()
    assert view["escalation_owners"] == [], "unowned escalations are visible, not hidden"


def test_new_schedule_version_applies_forward_and_keeps_history(clients, actors, db):
    maturity = TODAY + timedelta(days=100)
    submitted(clients(), actors, maturity)
    deadlines.sweep(db, at(maturity - timedelta(days=90), 1))
    db.add(
        ReminderSchedule(
            version=2,
            offsets_days=[45, 7],
            action_lead_days=20,
            escalate_after_days=5,
            effective_from=at(maturity - timedelta(days=89)),
            note="Shorter notice",
        )
    )
    db.commit()
    deadlines.sweep(db, at(maturity - timedelta(days=44)))
    rows = dict(db.execute(select(Reminder.step, Reminder.schedule_version)).all())
    assert rows == {"reminder:90": 1, "reminder:45": 2}, "v1's 60-day notice no longer applies"


def test_no_renewal_needed_when_obligation_ends_before_maturity(clients, actors, db):
    maturity = TODAY + timedelta(days=40)
    obligation = db.get(Obligation, actors["obligations"][0].id)
    obligation.required_until = maturity - timedelta(days=60)
    db.commit()
    item = submitted(clients(), actors, maturity)
    deadlines.sweep(db, at(maturity, 1))
    assert steps(db, item) == ["reminder:30", "reminder:7"]
    view = clients().get(f"/api/v1/instruments/{item['id']}/deadlines").json()
    assert view["renewal_required"] is False and view["action_due_date"] is None


def test_deadlines_keep_the_three_dates_separate(clients, actors, db):
    maturity = TODAY + timedelta(days=100)
    obligation = db.get(Obligation, actors["obligations"][0].id)
    obligation.required_until = maturity + timedelta(days=365)
    db.commit()
    item = submitted(clients(), actors, maturity)
    view = clients().get(f"/api/v1/instruments/{item['id']}/deadlines").json()
    assert view["maturity_date"] == maturity.isoformat()
    assert view["action_due_date"] == (maturity - timedelta(days=30)).isoformat()
    assert view["obligation_required_until"] == (maturity + timedelta(days=365)).isoformat()
    assert view["renewal_required"] is True and view["schedule_version"] == 1
    assert [u["step"] for u in view["upcoming"]][:2] == ["reminder:90", "reminder:60"]
    assert clients("beta").get(f"/api/v1/instruments/{item['id']}/deadlines").status_code == 404
    reviewer = clients("reviewer").get(f"/api/v1/reviews/{item['id']}").json()
    assert reviewer["deadlines"]["action_due_date"] == view["action_due_date"]


def test_reminders_and_schedules_are_immutable(clients, actors, db):
    maturity = TODAY + timedelta(days=10)
    submitted(clients(), actors, maturity)
    deadlines.sweep(db, at(TODAY, 1))
    for statement in (
        "UPDATE reminders SET step = step",
        "DELETE FROM reminders",
        "UPDATE reminder_schedules SET note = 'x'",
    ):
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()
    assert db.scalar(select(func.count()).select_from(Reminder)) == 2
