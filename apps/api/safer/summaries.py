"""Read-only, versioned local summaries. No model, prompt or external transfer."""

import hashlib
import json

VERSION = "case-summary-1"
MATERIAL = (
    "instrument_id",
    "status",
    "row_version",
    "institution",
    "submission_id",
    "submitted_at",
    "claim",
    "comparison",
    "evidence",
    "documents",
    "submitted_documents",
    "discrepancies",
    "deadlines",
    "replacement",
    "releases",
    "coverage",
)


def state(case: dict, enabled: bool) -> dict:
    # Explicit allowlist excludes access audit events and presentation-only explanations.
    source = {key: case[key] for key in MATERIAL}
    encoded = json.dumps(
        {"version": VERSION, "source": source}, sort_keys=True, separators=(",", ":")
    )
    return {"enabled": enabled, "basis_sha256": hashlib.sha256(encoded.encode()).hexdigest()}


def citation(kind: str, id: str, href: str, **version) -> dict:
    return {"kind": kind, "id": id, "href": href, **version}


def section(title: str, facts: dict, text: str, citations: list) -> dict:
    return {"title": title, "facts": facts, "text": text, "citations": citations}


def build(case: dict, basis: str | None = None) -> dict:
    source = case["summary_state"]
    if not source["enabled"]:
        return {"enabled": False, "status": "disabled", "sections": []}
    result = {**source, "mode": "deterministic_fallback", "version": VERSION, "status": "current"}
    if basis and basis != source["basis_sha256"]:
        return {**result, "status": "stale", "sections": []}
    claim, rows = case["claim"], case["comparison"]
    real = [r for r in rows if not r["simulated"]]
    confirmed = sum(r["status"] == "match" for r in real)
    mismatched = sum(r["status"] == "mismatch" for r in real)
    submitted = case["submitted_documents"]
    docs = {d["id"]: d for d in case["documents"]}
    clean = sum(docs[d["id"]]["scan_status"] == "clean" for d in submitted)
    observations = case["discrepancies"]
    deadlines = case["deadlines"]
    sections = [
        section(
            "Submitted FDR",
            {
                "Institution": case["institution"]["name"],
                "FDR reference": claim["bank_reference"],
                "Bank name": claim["bank_name"],
                "Claimed principal (INR)": claim["principal_amount"],
                "Issue date": claim["issue_date"],
                "Maturity date": claim["maturity_date"],
                "Case status": case["status"],
            },
            "Institution-submitted claims copied exactly; these are not independent bank confirmation.",
            [citation("submission", case["submission_id"], "#submitted-claim")],
        ),
        section(
            "Evidence review",
            {
                "Confirmed fields": str(confirmed),
                "Mismatched fields": str(mismatched),
                "Unconfirmed fields": str(len(rows) - confirmed - mismatched),
                "Simulated fields": str(sum(r["simulated"] for r in rows)),
            },
            "Code compares the latest recorded evidence for each field. Simulated evidence never counts as independent confirmation.",
            [
                citation("evidence", r["evidence_id"], f"#evidence-{r['evidence_id']}")
                for r in rows
                if r["evidence_id"]
            ],
        ),
        section(
            "Documents",
            {
                "Submitted documents": str(len(submitted)),
                "Clean documents": str(clean),
                "Not cleared for download": str(len(submitted) - clean),
            },
            "Counts refer to frozen submission document versions. A clean scan does not verify financial authenticity.",
            [
                citation(
                    "document",
                    d["id"],
                    f"#document-{d['id']}",
                    sha256=d.get("sha256"),
                    object_version=d.get("object_version"),
                )
                for d in submitted
            ],
        ),
        section(
            "Pending observations",
            {
                "Open observations": str(sum(d["status"] == "open" for d in observations)),
                "Resolved observations": str(sum(d["status"] == "resolved" for d in observations)),
            },
            "Review the cited observation threads for the questions, responses and resolution records.",
            [citation("observation", d["id"], f"#observation-{d['id']}") for d in observations],
        ),
        section(
            "Deadlines",
            {
                "Maturity date": deadlines["maturity_date"],
                "Action due date": deadlines["action_due_date"] or "Not set",
                "Obligation required until": deadlines["obligation_required_until"] or "Not set",
                "Renewal required": "Yes" if deadlines["renewal_required"] else "No",
            },
            "Dates and renewal state come from the configured monitoring rules; inspect the source panel for the schedule.",
            [citation("deadlines", case["instrument_id"], "#summary-deadlines")],
        ),
    ]
    for release in case["releases"]:
        sections.append(
            section(
                "Release request",
                {
                    "Request ID": release["id"],
                    "Current release status": release["effective_status"],
                },
                "A summary cannot authorize release. Review clearances, decision validity and execution evidence in the request.",
                [citation("release", release["id"], "#summary-releases")],
            )
        )
    return {**result, "sections": sections}
