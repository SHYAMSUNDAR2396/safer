"""SAF-024 advisory fallback. No model, outbound calls or authoritative writes.

Only fixed wording is emitted. Untrusted document lines and evidence notes cannot
become instructions. Every value carries an immutable source identity; recomputing
on each read avoids a saved explanation silently outliving its source facts.
"""

import hashlib
import json

from sqlalchemy import select

from safer.extraction import latest
from safer.models import ExtractedField

VERSION = "comparison-explanation-1"


def build(db, sub, records, docs, states, compare):
    frozen = {d["id"]: d for d in sub.snapshot.get("documents", [])}
    eligible = [
        d
        for d in docs
        if d.kind != "other"
        and states[d.id] == "clean"
        and str(d.id) in frozen
        and frozen[str(d.id)]["sha256"] == d.sha256
        and frozen[str(d.id)]["object_version"] == d.object_version
    ]
    run = latest(db, [d.id for d in eligible])
    proposals = {}
    fields = {}
    doc = None
    if run:
        doc = next(d for d in eligible if d.id == run.document_id)
        fields = {
            f.field: f
            for f in db.scalars(
                select(ExtractedField).where(
                    ExtractedField.run_id == run.id, ExtractedField.status == "proposed"
                )
            ).all()
        }
        proposals = {key: f.value for key, f in fields.items()}
    items = []
    for row in compare(sub.snapshot, records, proposals):
        citations = [
            {
                "kind": "submission",
                "id": str(sub.id),
                "created_at": sub.created_at.isoformat(),
                "field": row["field"],
                "href": "#submitted-claim",
            }
        ]
        if row["evidence_id"]:
            r = next(r for r in records if str(r.id) == row["evidence_id"])
            citations.append(
                {
                    "kind": "evidence",
                    "id": str(r.id),
                    "field": r.field,
                    "method": r.method,
                    "observed_at": r.observed_at.isoformat(),
                    "created_at": r.created_at.isoformat(),
                    "href": f"#evidence-{r.id}",
                }
            )
        if row["field"] in fields:
            f = fields[row["field"]]
            citations.append(
                {
                    "kind": "extraction",
                    "id": str(f.id),
                    "field": f.field,
                    "run_id": str(run.id),
                    "extractor": run.extractor,
                    "document_id": str(doc.id),
                    "sha256": doc.sha256,
                    "object_version": doc.object_version,
                    "page": f.page,
                    "x": f.x,
                    "y": f.y,
                    "href": f"#document-{doc.id}",
                }
            )
        if row["simulated"]:
            wording = "Simulation only: these values are not independent bank confirmation. "
            wording += (
                "The simulated value differs from the submitted claim."
                if row["status"] == "mismatch"
                else "The simulated value agrees with the submitted claim."
            )
        elif row["status"] == "unconfirmed":
            wording = "No independent evidence is recorded for this field; it remains unconfirmed."
        elif row["status"] == "mismatch":
            wording = "The submitted claim and the latest recorded independent evidence differ. A reviewer must check the cited sources."
        else:
            wording = "The submitted claim agrees with the latest recorded independent evidence under the comparison rules. This does not authorize release."
        if row["extracted_differs"]:
            wording += " The institution document also differs from the claim; extracted text is a proposal, not independent evidence."
        items.append(
            {
                "field": row["field"],
                "label": row["label"],
                "status": row["status"],
                "claimed": row["claimed"],
                "evidence_value": row["confirmed"],
                "simulated": row["simulated"],
                "document_value": row["extracted"],
                "document_differs": row["extracted_differs"],
                "text": wording,
                "citations": citations,
            }
        )
    payload = {"version": VERSION, "items": items}
    basis = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return {"enabled": True, "mode": "deterministic_fallback", "basis_sha256": basis, **payload}


def disabled():
    return {"enabled": False, "mode": "disabled", "items": []}
