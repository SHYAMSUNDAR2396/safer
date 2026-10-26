"""Provider-neutral pilot gate ledger. This module cannot activate real-data mode."""

import argparse
import json
from pathlib import Path

PHASES = {
    "SAF-026": [
        "approved representative held-out corpus",
        "owner-approved accuracy/utility thresholds",
    ],
    "SAF-027": [
        "India-resident hosting and certificate chain",
        "production Keycloak MFA/federation recovery review",
        "independent KMS administration and workload identity",
        "encrypted database/broker/identity/storage links",
        "least-privilege storage/worker and parser network isolation",
    ],
    "SAF-028": [
        "independent retention-locked audit destination",
        "approved retention/legal holds",
        "identity/cloud/DB/storage/KMS/CI SIEM connectors",
        "named responder and tested real alert destination",
    ],
    "SAF-029": [
        "independent backup/recovery administrators",
        "PITR and exact object-version restore",
        "identity/key recovery after primary loss",
        "measured RPO <= 1 hour and RTO <= 4 hours",
        "incident tabletop and external-effects reconciliation",
    ],
    "SAF-030": [
        "declared 10k institution / 100k instrument workload",
        "p95 read <= 500 ms / write <= 1 s at 50 requests/second",
        "upstream DDoS/origin/quotas control verification",
    ],
    "SAF-031": [
        "independent security assessment",
        "no unresolved critical/high exploitable findings",
        "dependency/container/secret/provenance scans",
        "rollback and accessibility acceptance",
    ],
    "SAF-032": [
        "written AICTE data-owner approval before real/anonymized data",
        "signed authority and regulation policy matrix",
        "approved India residency/retention and processing terms",
        "trained accountable service owners",
        "signed pilot acceptance covering all preceding gates",
    ],
}


def assess(evidence: dict, assumptions: dict) -> dict:
    if set(evidence) - set(PHASES):
        raise ValueError("Unknown phase evidence")
    result = {}
    for phase, requirements in PHASES.items():
        record = evidence.get(phase, {"status": "not_run"})
        if record.get("status") not in {"pass", "fail", "incomplete", "not_run"}:
            raise ValueError("Invalid local evidence status")
        result[phase] = {
            "local_status": record["status"],
            "pilot_status": "blocked",
            "required_pilot_evidence": requirements,
            "artifact": record.get("artifact"),
            "limitations": record.get("limitations", []),
        }
    return {
        "schema": "safer-pilot-readiness-1",
        "classification": "synthetic_only",
        "real_data_activation": "blocked",
        "assumptions": assumptions,
        "phases": result,
        "missing_owner_decisions": [
            "final MeitY-empanelled/NIC/MeghRaj India hosting selection and verification",
            "written data-owner approval for any real or anonymized FDRs",
            "retention/legal holds and recovery/alert ownership",
            "production identity/federation/key-provider terms and acceptance",
        ],
        "activation_note": "Local results never remove Settings.app_mode production rejection. Owner approvals and a reviewed deployment change remain required.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--assumptions", type=Path, default=Path("infra/pilot/assumptions.json"))
    p.add_argument("--output", type=Path, default=Path(".local/pilot-readiness.json"))
    args = p.parse_args()
    result = assess(json.loads(args.evidence.read_text()), json.loads(args.assumptions.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("Local gate report written. Real-data activation remains blocked.")


if __name__ == "__main__":
    main()
