import copy
import json

import pytest


def test_audit_checkpoint_detects_change_reorder_and_missing_rows():
    from safer.audit_archive import checkpoint, verify_checkpoint

    rows = [
        {"id": "1", "action": "session.started", "created_at": "2026-10-24T00:00:00+00:00"},
        {
            "id": "2",
            "action": "review.evidence_recorded",
            "created_at": "2026-10-24T00:01:00+00:00",
        },
    ]
    manifest = checkpoint(rows)
    assert verify_checkpoint(rows, manifest)
    assert not verify_checkpoint(list(reversed(rows)), manifest)
    assert not verify_checkpoint(rows[:1], manifest)
    tampered = copy.deepcopy(rows)
    tampered[0]["action"] = "altered"
    assert not verify_checkpoint(tampered, manifest)


def test_alerts_are_owned_and_do_not_copy_sensitive_event_content():
    from safer.audit_archive import alerts

    events = [
        {
            "source": "application",
            "kind": "access_denied",
            "at": "2026-10-24T00:01:00+00:00",
            "detail": "financial values and tokens must not enter alert",
        }
        for _ in range(10)
    ]
    result = alerts(events)
    assert result and all(r["owner"] == "security-service-owner" and r["runbook"] for r in result)
    assert "financial values" not in json.dumps(result)
    assert alerts(events[:1]) == []
    assert (
        alerts(
            [{"source": "kms", "kind": "key_delete_attempt", "at": "2026-10-24T00:01:00+00:00"}]
        )[0]["severity"]
        == "high"
    )


def test_readiness_cannot_approve_real_data_from_synthetic_success(tmp_path):
    from safer.readiness import assess

    result = assess({"SAF-026": {"status": "pass", "classification": "synthetic_only"}}, {})
    assert result["real_data_activation"] == "blocked"
    assert result["phases"]["SAF-026"]["local_status"] == "pass"
    assert result["phases"]["SAF-027"]["local_status"] == "not_run"
    assert result["phases"]["SAF-028"]["pilot_status"] == "blocked"
    assert result["missing_owner_decisions"]


def test_readiness_rejects_unknown_or_fabricated_evidence():
    from safer.readiness import assess

    with pytest.raises(ValueError):
        assess({"SAF-999": {"status": "pass"}}, {})
    with pytest.raises(ValueError):
        assess({"SAF-027": {"status": "approved-real-data"}}, {})


def test_restore_target_cannot_be_a_working_database():
    from safer.local_drills import validate_restore_name

    assert validate_restore_name("safer_restore_synthetic_abcdef123456")
    for name in [
        "safer",
        "safer_readiness",
        "safer_test",
        "postgres",
        "safer_restore_synthetic_;DROP DATABASE safer",
    ]:
        with pytest.raises(ValueError):
            validate_restore_name(name)


def test_capacity_gates_fail_on_latency_errors_or_missing_samples():
    from safer.capacity import summarize

    samples = [
        {"method": "GET", "status": 200, "server_ms": 20, "client_ms": 30, "started": i / 50}
        for i in range(100)
    ]
    samples += [
        {
            "method": "POST",
            "status": 201,
            "server_ms": 40,
            "client_ms": 50,
            "started": (100 + i) / 50,
        }
        for i in range(25)
    ]
    result = summarize(samples, 50)
    assert result["latency_gate"] == "pass"
    assert result["reads"]["p95_ms"] == 20 and result["writes"]["p95_ms"] == 40
    bad = [dict(s, server_ms=2000) for s in samples]
    assert summarize(bad, 50)["latency_gate"] == "fail"
    bad[0]["status"] = 500
    assert summarize(bad, 50)["server_errors"] == 1
    assert summarize([], 50)["latency_gate"] == "incomplete"
