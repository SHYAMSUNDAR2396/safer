"""SAF-026 metrics must fail honestly; synthetic evidence is never pilot approval."""

import copy
import xml.etree.ElementTree as ET

import pytest


def test_metrics_do_not_hide_errors_or_count_abstention_as_an_answer():
    from safer.evaluation import score_fields

    expected = {"bank_reference": "00004567", "principal_amount": "1234.56", "issue_date": None}
    rows = [
        {"field": "bank_reference", "status": "proposed", "value": "00004567"},
        {"field": "principal_amount", "status": "proposed", "value": "1234.50"},
        {"field": "issue_date", "status": "abstained", "value": None},
    ]
    result = score_fields(expected, rows)
    assert result["counts"] == {
        "total": 3,
        "answerable": 2,
        "proposed": 2,
        "correct": 1,
        "wrong": 1,
        "abstained": 1,
        "correct_abstentions": 1,
    }
    assert result["exact_match"] == 0.5 and result["selective_accuracy"] == 0.5
    assert result["critical_error_rate"] == 0.5
    assert result["abstention_rate"] == pytest.approx(1 / 3)
    assert result["per_field"]["principal_amount"]["counts"]["wrong"] == 1


def test_missing_answer_and_unsafe_proposal_have_distinct_denominators():
    from safer.evaluation import score_fields

    result = score_fields(
        {"a": "known", "b": None},
        [
            {"field": "a", "status": "abstained", "value": None},
            {"field": "b", "status": "proposed", "value": "invented"},
        ],
    )
    assert result["exact_match"] == 0 and result["critical_error_rate"] == 1
    assert result["counts"]["correct_abstentions"] == 0
    empty = score_fields({"a": None}, [{"field": "a", "status": "abstained", "value": None}])
    assert empty["exact_match"] is None and empty["selective_accuracy"] is None
    assert empty["abstention_rate"] == 1


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"field": "a", "status": "proposed", "value": "ok"}] * 2,
        [{"field": "foreign", "status": "proposed", "value": "ok"}],
        [{"field": "a", "status": "proposed", "value": None}],
        [{"field": "a", "status": "abstained", "value": "guessed"}],
    ],
)
def test_missing_duplicate_or_invalid_field_output_fails_validation(rows):
    from safer.evaluation import score_fields

    with pytest.raises(ValueError):
        score_fields({"a": "ok"}, rows)


def test_percentile_is_nearest_rank_and_empty_is_not_zero_latency():
    from safer.evaluation import percentile

    assert percentile(list(range(1, 21)), 0.95) == 19
    assert percentile([7], 0.95) == 7
    assert percentile([], 0.95) is None


def test_summary_oracle_detects_facts_and_citation_version_tampering():
    from safer import summaries
    from safer.evaluation import check_summary, review_case

    case = review_case(
        {
            "id": "oracle",
            "claim": {
                "bank_reference": "000007",
                "bank_name": "Synthetic Heldout Bank",
                "principal_amount": "9999999999999999.99",
                "issue_date": "2026-01-01",
                "maturity_date": "2027-01-01",
            },
            "status": "submitted",
            "evidence": [],
        }
    )
    good = summaries.build(case)
    assert check_summary(case, good)["errors"] == []
    bad = copy.deepcopy(good)
    bad["sections"][0]["facts"]["Claimed principal (INR)"] = "10000000000000000.00"
    bad["sections"][2]["citations"][0]["sha256"] = "bad"
    result = check_summary(case, bad)
    assert "fact:Submitted FDR:Claimed principal (INR)" in result["errors"]
    assert any(x.startswith("citation:") for x in result["errors"])
    assert check_summary(case, good | {"sections": []})["errors"]


def test_security_evidence_requires_passing_executed_unskipped_named_tests():
    from safer.evaluation import security_result

    good = ET.fromstring(
        '<testsuites><testsuite tests="2" failures="0" errors="0" skipped="0"><testcase classname="test_scope" name="test_denied"/><testcase classname="test_summary" name="test_safe"/></testsuite></testsuites>'
    )
    expected = {("test_scope", "test_denied"), ("test_summary", "test_safe")}
    assert security_result(good, 0, expected)["status"] == "pass"
    for xml, code in [
        ("<testsuites/>", 0),
        ('<testsuite tests="1"><testcase name="a"><skipped/></testcase></testsuite>', 0),
        ('<testsuite tests="1"><testcase name="a"><failure/></testcase></testsuite>', 0),
        ('<testsuite tests="2"><testcase name="a"/></testsuite>', 0),
        ('<testsuite tests="1"><testcase name="a"/></testsuite>', 1),
    ]:
        assert security_result(ET.fromstring(xml), code, expected)["status"] == "fail"
    assert security_result(None, None)["status"] == "not_run"


def test_self_consistent_partial_duplicate_or_unverified_security_runs_fail():
    from safer.evaluation import security_result

    expected = {("scope", "test_denied"), ("summary", "test_safe")}
    partial = ET.fromstring(
        '<testsuite tests="1"><testcase classname="scope" name="test_denied"/></testsuite>'
    )
    duplicate = ET.fromstring(
        '<testsuite tests="2"><testcase classname="scope" name="test_denied"/><testcase classname="scope" name="test_denied"/></testsuite>'
    )
    assert security_result(partial, 0, expected)["status"] == "fail"
    assert security_result(duplicate, 0, expected)["status"] == "fail"
    assert security_result(partial, 0)["status"] == "fail"


def test_security_runner_ignores_inherited_selection_and_checks_collection(tmp_path, monkeypatch):
    import subprocess

    from safer.evaluation import security_suite

    calls = []
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k test_safe")

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if "--collect-only" in args:
            kwargs["stdout"].write(
                "apps/api/tests/test_summaries.py::test_safe\napps/api/tests/test_extraction.py::test_denied\n"
            )
        else:
            (tmp_path / "security.xml").write_text(
                '<testsuite tests="1"><testcase classname="apps.api.tests.test_summaries" name="test_safe"/></testsuite>'
            )
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert security_suite(tmp_path)["status"] == "fail"
    assert len(calls) == 2
    assert all("PYTEST_ADDOPTS" not in kwargs["env"] for _, kwargs in calls)


def test_synthetic_gate_never_grants_pilot_and_missing_security_is_not_pass():
    from safer.evaluation import gates

    assert gates(0, 0, {"status": "not_run"}) == {"regression": "incomplete", "pilot": "blocked"}
    assert gates(0, 0, {"status": "pass"}) == {"regression": "pass", "pilot": "blocked"}
    assert gates(1, 0, {"status": "pass"})["regression"] == "fail"
    assert gates(0, 1, {"status": "pass"})["regression"] == "fail"


def test_summary_oracle_rejects_unknown_claims_and_misplaced_source_citations():
    from safer import summaries
    from safer.evaluation import check_summary, review_case

    case = review_case(
        {
            "id": "location",
            "claim": {
                "bank_name": "Synthetic Bank",
                "bank_reference": "000001",
                "principal_amount": "1.00",
                "issue_date": "2026-01-01",
                "maturity_date": "2027-01-01",
            },
            "status": "submitted",
            "evidence": [],
        }
    )
    original = summaries.build(case)
    extra = copy.deepcopy(original)
    extra["sections"][0]["facts"]["Authorized release amount"] = "1.00"
    assert check_summary(case, extra)["errors"]
    swapped = copy.deepcopy(original)
    swapped["sections"][0]["citations"], swapped["sections"][2]["citations"] = (
        swapped["sections"][2]["citations"],
        swapped["sections"][0]["citations"],
    )
    assert check_summary(case, swapped)["errors"]

    moved = copy.deepcopy(original)
    release = next(s for s in moved["sections"] if s["title"] == "Release request")
    release["citations"].extend(moved["sections"][0]["citations"])
    moved["sections"][0]["citations"] = []
    assert check_summary(case, moved)["errors"]

    # Correct-kind citations must also belong to this particular release.
    case["releases"].append({"id": "another-release", "effective_status": "open"})
    case["summary_state"] = summaries.state(case, True)
    two = summaries.build(case)
    releases = [s for s in two["sections"] if s["title"] == "Release request"]
    releases[0]["citations"], releases[1]["citations"] = (
        releases[1]["citations"],
        releases[0]["citations"],
    )
    assert check_summary(case, two)["errors"]
