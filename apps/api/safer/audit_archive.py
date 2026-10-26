"""Local protected-audit and SIEM-format readiness building blocks, not a WORM claim."""

import hashlib
import json
from collections import Counter
from datetime import datetime


def canonical(rows: list[dict]) -> bytes:
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def checkpoint(rows: list[dict]) -> dict:
    head = "0" * 64
    for row in rows:
        head = hashlib.sha256(bytes.fromhex(head) + canonical([row])).hexdigest()
    return {
        "schema": "safer-audit-checkpoint-1",
        "rows": len(rows),
        "sha256": hashlib.sha256(canonical(rows)).hexdigest(),
        "chain_head": head,
    }


def verify_checkpoint(rows: list[dict], manifest: dict) -> bool:
    return checkpoint(rows) == manifest


def alerts(events: list[dict]) -> list[dict]:
    """Stable redacted alert contract. Caller supplies a bounded five-minute window."""
    if len(events) > 10000:
        raise ValueError("Alert event window exceeds local limit")
    # Do not carry arbitrary event details/identifiers into SIEM payloads.
    counts = Counter((e.get("source"), e.get("kind")) for e in events)
    rules = [
        ("application", "access_denied", 10, "repeated-access-denials", "medium"),
        ("identity", "mfa_reset", 1, "privileged-mfa-reset", "high"),
        ("kms", "key_delete_attempt", 1, "key-deletion-attempt", "high"),
        ("backup", "stale", 1, "backup-freshness", "high"),
        ("audit", "gap", 1, "audit-checkpoint-gap", "high"),
        ("authority", "sensitive_grant_change", 1, "sensitive-authority-change", "high"),
    ]
    return [
        {
            "schema": "safer-security-alert-1",
            "rule": rule,
            "severity": severity,
            "source": source,
            "count": counts[(source, kind)],
            "owner": "security-service-owner",
            "response_minutes": 15 if severity == "high" else 60,
            "runbook": "docs/runbooks/SECURITY-ALERTS.md#" + rule,
        }
        for source, kind, threshold, rule, severity in rules
        if counts[(source, kind)] >= threshold
    ]


def recent_window(events: list[dict], now: datetime) -> list[dict]:
    selected = []
    for event in events:
        when = datetime.fromisoformat(event["at"])
        if when.tzinfo is None:
            raise ValueError("Security event requires timezone")
        if 0 <= (now - when).total_seconds() <= 300:
            selected.append(event)
    return selected
