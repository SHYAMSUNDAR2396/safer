# SAF-024 implementation plan and ledger

Scope: FR14, code-determined discrepancies with source-version citations, human authority unchanged.

Ruling: implement a deterministic local fallback, labelled explicitly, because no AI provider or privacy approval has been selected. No LLM adapter, outbound calls, fraud verdicts or authoritative writes. Provider-generated wording remains deferred; the fallback provides the usable manual path.

1. RED: API tests for scope/revocation, exact sources, evidence refresh, switch-off, simulator separation, document provenance, instruction-like source content and read-only behavior.
2. Implement read-only source-linked explanation envelope from authorized case snapshots and existing comparison rules. No migration or saved explanation cache.
3. Reviewer UI: show plain wording, structured values and source links; refresh with case state; independent flag.
4. GREEN: targeted and complete API suite, frontend build/lint/format, browser workflow, contract and documentation.

Source basis: immutable submission id/snapshot, evidence ids and values, clean submitted document version/hash and extraction run/field/page. A deterministic basis digest changes with source facts; generated on every request, never a persisted approval.

Progress: API RED observed (7 missing-route failures); GREEN observed (7 passed). Corrected test fixture to require its certificate, because metadata-only obligations do not freeze optional certificates. No change to submission inclusion policy.

API suite: 229 passed. Seven new regression tests cover mismatch/source identity, refresh basis, access/revocation, disabled fallback, simulation, frozen extraction provenance and instruction-like evidence text. Frontend build and format pass. Independent review completed with no important findings.

Completion: local fallback tasks 1–4 complete. Full browser suite: 13 passed (1.3m), screenshot inspected. Source-link interaction passes against actual evidence DOM anchor. OpenAPI, REQUIREMENTS, API/ARCHITECTURE/SECURITY/DEPLOYMENT/TESTING, README and parent backlog updated. No code-review minors deferred. Model/provider-generated wording is outstanding, not silently marked implemented. No changes committed or published.

## User decision — 24 October 2026

The user selected: "use the local fallback". Local deterministic explanations are the accepted SAF-024 mode, not an interim provider-selection blocker. SAF-024 is complete for the approved fallback scope with the verification above. Model-generated wording is an optional future enhancement. No runtime change is necessary: explanations_enabled already defaults to true and uses only deterministic local templates. SAF-025/026 are not started by this decision.
