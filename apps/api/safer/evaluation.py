"""SAF-026 offline synthetic evaluation; never a pilot-activation mechanism."""

import argparse
import hashlib
import io
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from safer import explanations, extraction, summaries
from safer.reviews import comparison

ROOT = Path(__file__).resolve().parents[3]
COUNTS = ("total", "answerable", "proposed", "correct", "wrong", "abstained", "correct_abstentions")
FIELDS = tuple(extraction.RULES)
SECURITY_TESTS = (
    "apps/api/tests/test_extraction.py",
    "apps/api/tests/test_explanations.py",
    "apps/api/tests/test_summaries.py",
)


class DocumentCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9-]{1,80}$")
    layout: str = Field(min_length=1, max_length=100)
    stratum: str = Field(min_length=1, max_length=100)
    media: Literal["text_pdf", "image_png"]
    pages: list[list[str]] = Field(min_length=1, max_length=3)
    expected: dict[str, str | None]
    noise: int = Field(default=0, ge=0, le=5000)

    @model_validator(mode="after")
    def bounds(self):
        if set(self.expected) != set(FIELDS):
            raise ValueError("Every extraction field must have an explicit label")
        if any(len(page) > 100 or any(len(line) > 500 for line in page) for page in self.pages):
            raise ValueError("Synthetic page bounds exceeded")
        return self


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9-]{1,80}$")
    claim: dict[str, str]
    status: Literal["submitted", "closed"]
    evidence: list[dict] = Field(max_length=20)

    @model_validator(mode="after")
    def fields(self):
        if set(self.claim) != set(FIELDS):
            raise ValueError("Review claim fields do not match the contract")
        return self


class Corpus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    classification: Literal["synthetic_only"]
    split: Literal["synthetic_layout_holdout", "synthetic_regression"]
    limitations: list[str]
    documents: list[DocumentCase] = Field(min_length=1, max_length=200)
    review_cases: list[ReviewInput] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique(self):
        ids = [x.id for x in self.documents] + [x.id for x in self.review_cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Corpus IDs must be unique")
        return self


def rates(counts: dict) -> dict:
    def ratio(a, b):
        return counts[a] / counts[b] if counts[b] else None

    return {
        "counts": {key: counts.get(key, 0) for key in COUNTS},
        "exact_match": ratio("correct", "answerable"),
        "selective_accuracy": ratio("correct", "proposed"),
        "critical_error_rate": ratio("wrong", "proposed"),
        "abstention_rate": ratio("abstained", "total"),
    }


def score_fields(expected: dict, proposals: list[dict]) -> dict:
    if len(proposals) != len(expected) or {p["field"] for p in proposals} != set(expected):
        raise ValueError("Missing, duplicate or unknown extraction field")
    total, fields = Counter({key: 0 for key in COUNTS}), {}
    for p in proposals:
        field, status, value = p["field"], p["status"], p["value"]
        if status not in {"proposed", "abstained"} or (
            (status == "proposed" and not isinstance(value, str))
            or (status == "abstained" and value is not None)
        ):
            raise ValueError("Invalid extraction disposition")
        c = Counter({key: 0 for key in COUNTS})
        c.update(total=1, answerable=int(expected[field] is not None))
        if status == "proposed":
            c.update(
                proposed=1,
                correct=int(value == expected[field]),
                wrong=int(value != expected[field]),
            )
        else:
            c.update(abstained=1, correct_abstentions=int(expected[field] is None))
        total.update(c)
        fields[field] = rates(c)
    return rates(total) | {"per_field": fields}


def percentile(values: list, fraction: float):
    if not 0 < fraction <= 1:
        raise ValueError("Percentile must be in (0, 1]")
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


def document_bytes(item: DocumentCase) -> bytes:
    if item.media == "image_png":
        im = Image.new("RGB", (1200, 800), "white")
        draw = ImageDraw.Draw(im)
        for i, line in enumerate(sum(item.pages, [])):
            draw.text((35, 35 + i * 25), line, fill="black")
        rng = random.Random(item.id)
        for _ in range(item.noise):
            draw.point((rng.randrange(1200), rng.randrange(800)), fill="gray")
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for lines in item.pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        escaped = [
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines
        ]
        stream.set_data(
            "".join(
                f"BT /F1 10 Tf 48 {740 - i * 18} Td ({line}) Tj ET\n"
                for i, line in enumerate(escaped)
            ).encode("latin-1")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def review_case(item: dict) -> dict:
    """Synthetic read-model fixture, not a business write or authorization replacement."""
    caseid = item["id"]
    records = [
        SimpleNamespace(
            id=f"{caseid}-e{i}",
            field=e["field"],
            value=e["value"],
            method="bank_simulator" if e.get("simulated") else "bank_letter",
            created_at=i,
        )
        for i, e in enumerate(item["evidence"])
    ]
    doc = {
        "id": f"{caseid}-doc",
        "sha256": hashlib.sha256(caseid.encode()).hexdigest(),
        "object_version": "synthetic-version-1",
        "scan_status": "clean",
    }
    case = {
        "instrument_id": caseid,
        "status": item["status"],
        "row_version": 2,
        "institution": {"id": "synthetic-institution", "name": "Synthetic Evaluation Institute"},
        "submission_id": f"{caseid}-submission",
        "submitted_at": "2026-10-24T00:00:00+00:00",
        "claim": item["claim"],
        "comparison": comparison(item["claim"], records),
        "evidence": [vars(r) for r in records],
        "documents": [doc],
        "submitted_documents": [doc],
        "discrepancies": [{"id": f"{caseid}-observation", "status": "open"}],
        "deadlines": {
            "maturity_date": item["claim"]["maturity_date"],
            "action_due_date": "2027-01-01",
            "obligation_required_until": None,
            "renewal_required": item["status"] != "closed",
        },
        "replacement": {},
        "releases": [
            {
                "id": f"{caseid}-release",
                "effective_status": "closed" if item["status"] == "closed" else "open",
            }
        ],
        "coverage": {},
    }
    case["summary_state"] = summaries.state(case, True)
    return case


def check_summary(case: dict, output: dict) -> dict:
    """Independent fact/citation oracle; do not rebuild expected output with the builder."""
    claim, deadline = case["claim"], case["deadlines"]
    expected = {
        "Submitted FDR": {
            "Institution": case["institution"]["name"],
            "FDR reference": claim["bank_reference"],
            "Bank name": claim["bank_name"],
            "Claimed principal (INR)": claim["principal_amount"],
            "Issue date": claim["issue_date"],
            "Maturity date": claim["maturity_date"],
            "Case status": case["status"],
        },
        "Deadlines": {
            "Maturity date": deadline["maturity_date"],
            "Action due date": deadline["action_due_date"] or "Not set",
            "Obligation required until": deadline["obligation_required_until"] or "Not set",
            "Renewal required": "Yes" if deadline["renewal_required"] else "No",
        },
    }
    latest = {r["field"]: r for r in case["evidence"]}
    match = sum(
        r["method"] != "bank_simulator" and r["value"] == claim[r["field"]] for r in latest.values()
    )
    mismatch = sum(
        r["method"] != "bank_simulator" and r["value"] != claim[r["field"]] for r in latest.values()
    )
    expected["Evidence review"] = {
        "Confirmed fields": str(match),
        "Mismatched fields": str(mismatch),
        "Unconfirmed fields": str(5 - match - mismatch),
        "Simulated fields": str(sum(r["method"] == "bank_simulator" for r in latest.values())),
    }
    expected["Pending observations"] = {
        "Open observations": str(sum(d["status"] == "open" for d in case["discrepancies"])),
        "Resolved observations": str(sum(d["status"] == "resolved" for d in case["discrepancies"])),
    }
    docs = {d["id"]: d for d in case["documents"]}
    clean = sum(docs[d["id"]]["scan_status"] == "clean" for d in case["submitted_documents"])
    expected["Documents"] = {
        "Submitted documents": str(len(case["submitted_documents"])),
        "Clean documents": str(clean),
        "Not cleared for download": str(len(case["submitted_documents"]) - clean),
    }
    sections = output.get("sections", [])
    errors, facts, citations = [], 0, 0
    allowed = {
        ("submission", case["submission_id"]): "#submitted-claim",
        ("deadlines", case["instrument_id"]): "#summary-deadlines",
    }
    for kind, rows, prefix in [
        ("evidence", latest.values(), "evidence"),
        ("document", case["submitted_documents"], "document"),
        ("observation", case["discrepancies"], "observation"),
        ("release", case["releases"], "summary-releases"),
    ]:
        for row in rows:
            allowed[(kind, row["id"])] = (
                f"#{prefix}-{row['id']}" if kind != "release" else "#summary-releases"
            )
    required = set(allowed)
    section_sources = {
        "Submitted FDR": {("submission", case["submission_id"])},
        "Evidence review": {("evidence", r["id"]) for r in latest.values()},
        "Documents": {("document", d["id"]) for d in case["submitted_documents"]},
        "Pending observations": {("observation", d["id"]) for d in case["discrepancies"]},
        "Deadlines": {("deadlines", case["instrument_id"])},
    }

    def check_sources(section, expected_sources):
        actual = [(c.get("kind"), c.get("id")) for c in section.get("citations", [])]
        if set(actual) != expected_sources or len(actual) != len(expected_sources):
            errors.append(f"citation:{section['title']}:section_sources")

    for title, values in expected.items():
        found = [s for s in sections if s["title"] == title]
        if len(found) != 1:
            errors.append(f"section:{title}")
            continue
        if set(found[0]["facts"]) != set(values):
            errors.append(f"fact:{title}:unexpected_fields")
        check_sources(found[0], section_sources[title])
        for key, value in values.items():
            facts += 1
            if found[0]["facts"].get(key) != value:
                errors.append(f"fact:{title}:{key}")
    if any(s["title"] not in set(expected) | {"Release request"} for s in sections):
        errors.append("section:unexpected")
    releases = [s for s in sections if s["title"] == "Release request"]
    if len(releases) != len(case["releases"]):
        errors.append("section:Release request")
    for r in case["releases"]:
        facts += 2
        matching = [
            s
            for s in releases
            if s["facts"]
            == {"Request ID": r["id"], "Current release status": r["effective_status"]}
        ]
        if len(matching) != 1:
            errors.append("fact:Release request")
        else:
            check_sources(matching[0], {("release", r["id"])})
    for section in sections:
        for c in section.get("citations", []):
            citations += 1
            key = (c.get("kind"), c.get("id"))
            if key not in allowed or allowed[key] != c.get("href"):
                errors.append(f"citation:{c.get('kind')}:unresolved")
            else:
                required.discard(key)
                if key[0] == "document":
                    frozen = next(d for d in case["submitted_documents"] if d["id"] == key[1])
                    if any(c.get(k) != frozen[k] for k in ["sha256", "object_version"]):
                        errors.append("citation:document:version")
    errors.extend(f"citation:{kind}:missing" for kind, id in sorted(required))
    return {"facts_checked": facts, "citations_checked": citations, "errors": errors}


def security_result(root, returncode, expected: set[tuple[str, str]] | None = None) -> dict:
    if root is None and returncode is None:
        return {"status": "not_run", "tests": 0}
    if root is None:
        return {"status": "fail", "tests": 0, "reason": "missing_junit"}
    cases = list(root.iter("testcase"))
    suites = list(root.iter("testsuite"))
    declared = sum(int(s.attrib.get("tests", "0")) for s in suites)
    identities = [(c.get("classname"), c.get("name")) for c in cases]
    bad = (
        returncode != 0
        or not expected
        or set(identities) != expected
        or len(identities) != len(set(identities))
        or not cases
        or declared != len(cases)
        or any(
            any(c.find(tag) is not None for tag in ("failure", "error", "skipped")) for c in cases
        )
    )
    return {
        "status": "fail" if bad else "pass",
        "tests": len(cases),
        "expected_tests": len(expected or ()),
        "exit_code": returncode,
    }


def gates(critical_errors: int, summary_errors: int, security: dict) -> dict:
    status = (
        "fail"
        if critical_errors or summary_errors or security["status"] == "fail"
        else "pass"
        if security["status"] == "pass"
        else "incomplete"
    )
    return {"regression": status, "pilot": "blocked"}


def security_suite(output: Path) -> dict:
    junit = output / "security.xml"
    junit.unlink(missing_ok=True)  # Never accept a previous successful run's evidence.
    env = {k: v for k, v in os.environ.items() if k not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    command = [sys.executable, "-m", "pytest", "-o", "addopts=", *SECURITY_TESTS, "-q"]
    try:
        # Collect independently of execution, with inherited selection/plugins disabled.
        collection = output / "security-collection.log"
        with collection.open("w") as log:
            proc = subprocess.run(
                command + ["--collect-only"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=60,
            )
        nodes = [
            line.strip()
            for line in collection.read_text().splitlines()
            if any(line.startswith(p + "::") for p in SECURITY_TESTS)
        ]
        expected = set()
        for node in nodes:
            parts = node.split("::")
            expected.add((".".join([parts[0][:-3].replace("/", "."), *parts[1:-1]]), parts[-1]))
        if proc.returncode != 0 or not expected or len(nodes) != len(expected):
            return {"status": "fail", "tests": 0, "reason": "invalid_collection"}
        with (output / "security.log").open("w") as log:
            proc = subprocess.run(
                command + [f"--junitxml={junit}"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=180,
            )
        root = ET.parse(junit).getroot() if junit.exists() else None
        result = security_result(root, proc.returncode, expected)
    except (subprocess.TimeoutExpired, ET.ParseError, OSError) as exc:
        result = {"status": "fail", "tests": 0, "reason": type(exc).__name__}
    return result


def evaluate(corpus: Corpus, digest: str) -> dict:
    rows, counters, per_field, strata = [], Counter({k: 0 for k in COUNTS}), {}, {}
    for item in corpus.documents:
        data = document_bytes(item)
        started = time.perf_counter()
        lines = extraction.text_lines(data) if item.media == "text_pdf" else []
        parser_failed = lines is None
        proposals = extraction.extract(lines or [])
        elapsed = (time.perf_counter() - started) * 1000
        score = score_fields(item.expected, proposals)
        counters.update(score["counts"])
        strata.setdefault(item.stratum, Counter({k: 0 for k in COUNTS})).update(score["counts"])
        for key, value in score["per_field"].items():
            per_field.setdefault(key, Counter({k: 0 for k in COUNTS})).update(value["counts"])
        rows.append(
            {
                "id": item.id,
                "layout": item.layout,
                "stratum": item.stratum,
                "input_sha256": hashlib.sha256(data).hexdigest(),
                "media": item.media,
                "manual_required": item.media == "image_png" or not lines,
                "parser_failed": parser_failed,
                "latency_ms": elapsed,
                **score,
            }
        )
    review_rows, tp, fp, fn = [], 0, 0, 0
    for item in corpus.review_cases:
        started = time.perf_counter()
        case = review_case(item.model_dump())
        output = summaries.build(case)
        result = check_summary(case, output)
        duration = (time.perf_counter() - started) * 1000
        expected = {e["field"]: e["expected_status"] for e in item.evidence}
        for row in case["comparison"]:
            actual = row["status"] == "mismatch"
            truth = expected.get(row["field"]) == "mismatch"
            tp += actual and truth
            fp += actual and not truth
            fn += truth and not actual
        changed = dict(case, status="closed" if case["status"] == "submitted" else "submitted")
        changed["summary_state"] = summaries.state(changed, True)
        if summaries.build(changed, output["basis_sha256"])["status"] != "stale":
            result["errors"].append("stale_invalidation")
        review_rows.append({"id": item.id, "latency_ms": duration, **result})
    return {
        "schema_version": "saf026-report-1",
        "created_at": datetime.now(UTC).isoformat(),
        "corpus": {
            "version": corpus.version,
            "sha256": digest,
            "classification": corpus.classification,
            "split": corpus.split,
            "documents": len(rows),
            "reviews": len(review_rows),
            "limitations": corpus.limitations,
        },
        "implementation": {
            "extraction": extraction.VERSION,
            "explanation": explanations.VERSION,
            "summary": summaries.VERSION,
            "python": platform.python_version(),
            "pypdf": version("pypdf"),
            "pillow": version("pillow"),
            "source_sha256": {
                name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in [
                    "extraction.py",
                    "filecheck.py",
                    "reviews.py",
                    "summaries.py",
                    "explanations.py",
                    "evaluation.py",
                ]
            },
        },
        "extraction": rates(counters)
        | {
            "per_field": {k: rates(v) for k, v in per_field.items()},
            "strata": {k: rates(v) for k, v in strata.items()},
            "cases": rows,
            "parser_failures": sum(r["parser_failed"] for r in rows),
        },
        "comparison": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "summaries": {
            "facts_checked": sum(r["facts_checked"] for r in review_rows),
            "citations_checked": sum(r["citations_checked"] for r in review_rows),
            "errors": sum(len(r["errors"]) for r in review_rows),
            "cases": review_rows,
        },
        "operations": {
            "extraction_p50_ms": percentile([r["latency_ms"] for r in rows], 0.5),
            "extraction_p95_ms": percentile([r["latency_ms"] for r in rows], 0.95),
            "summary_p95_ms": percentile([r["latency_ms"] for r in review_rows], 0.95),
            "external_ai_calls": 0,
            "external_inference_cost_inr": "0.00",
            "hosting_cpu_storage_cost": "not_measured",
            "queue_latency": "not_measured_offline_runner",
            "manual_baseline_time": "not_measured_requires_human_study",
            "human_correction_rate": "not_measured_requires_reviewer_dispositions",
        },
        "acceptance": {
            "representative_dataset": "not_supplied",
            "representative_thresholds": "not_approved",
            "owners": "not_signed",
            "decision": "synthetic regression only; real-data pilot remains blocked",
        },
    }


def markdown(report: dict) -> str:
    def percent(value):
        return "N/A" if value is None else f"{value:.2%}"

    parts = [
        "# SAF-026 local assistance evaluation",
        "",
        f"Generated: {report['created_at']}",
        f"Corpus: `{report['corpus']['version']}` / SHA-256 `{report['corpus']['sha256']}`",
        f"Mode: {report['corpus']['classification']} / {report['corpus']['split']}",
        f"Regression gate: **{report['gates']['regression']}**; pilot gate: **blocked**.",
        "",
        "| Stratum | Fields | Exact match among answerable | Wrong proposals | Abstention |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, row in report["extraction"]["strata"].items():
        parts.append(
            f"| {name} | {row['counts']['total']} | {percent(row['exact_match'])} | {row['counts']['wrong']} | {percent(row['abstention_rate'])} |"
        )
    parts += [
        "",
        "Exact match = correct proposals / answerable fields. Abstentions are not correct answers. Critical error = wrong proposals / all proposals, including unsafe proposals on unanswerable fields. N/A means no denominator.",
        "",
        f"Summary facts checked: {report['summaries']['facts_checked']}; citations checked: {report['summaries']['citations_checked']}; errors: {report['summaries']['errors']}.",
        f"Comparison precision: {percent(report['comparison']['precision'])}; recall: {percent(report['comparison']['recall'])}.",
        f"Security suite: {report['security']['status']} ({report['security']['tests']} executed tests).",
        "",
        "## Local measurements",
        "",
        "```json",
        json.dumps(report["operations"], indent=2),
        "```",
        "",
        "## Limits and remaining acceptance",
        "",
    ]
    parts += [f"- {x}" for x in report["corpus"]["limitations"]]
    parts += [
        "- Representative layout/noise thresholds and human time/correction baselines require approved samples and named owner acceptance.",
        "- Local parser/service runtimes exclude queue wait and network transfer; zero external inference fees excludes infrastructure/operations costs.",
        "- JUnit/logs and source/library versions are recorded with the machine-readable report. No production security, statistical generalization or cloud performance certification.",
    ]
    return "\n".join(parts) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "evaluation/saf026/corpus.json")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/evaluation/saf026")
    parser.add_argument(
        "--security",
        action="store_true",
        help="Run real API authorization/provenance/injection regressions on the configured dedicated test DB",
    )
    args = parser.parse_args(argv)
    os.umask(0o077)
    raw = args.corpus.read_bytes()
    corpus = Corpus.model_validate_json(raw)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = evaluate(corpus, hashlib.sha256(raw).hexdigest())
    report["security"] = security_suite(output) if args.security else security_result(None, None)
    critical = report["extraction"]["counts"]["wrong"] + report["extraction"]["parser_failures"]
    review_errors = (
        report["summaries"]["errors"]
        + report["comparison"]["false_positive"]
        + report["comparison"]["false_negative"]
    )
    report["gates"] = gates(critical, review_errors, report["security"])
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "report.md").write_text(markdown(report))
    print(
        f"Regression: {report['gates']['regression']}; pilot: blocked. Report: {output / 'report.md'}"
    )
    return 0 if report["gates"]["regression"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
