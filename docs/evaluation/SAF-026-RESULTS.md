# SAF-026 local assistance evaluation

Generated: 2026-10-24T21:50:50.438827+00:00
Corpus: `saf026-synthetic-regression-2` / SHA-256 `1ab9df228a7e196880f42d8e0b77f06ef175a9c72762315cd9de28a77520d598`
Mode: synthetic_only / synthetic_regression
Regression gate: **pass**; pilot gate: **blocked**.

| Stratum | Fields | Exact match among answerable | Wrong proposals | Abstention |
|---|---:|---:|---:|---:|
| clean_text | 30 | 100.00% | 0 | 0.00% |
| noisy_text | 5 | 60.00% | 0 | 40.00% |
| missing_page | 5 | 60.00% | 0 | 40.00% |
| conflicting_text | 15 | 100.00% | 0 | 20.00% |
| invalid_value | 15 | 100.00% | 0 | 20.00% |
| instruction_text | 5 | 100.00% | 0 | 0.00% |
| scan_no_ocr | 10 | 0.00% | 0 | 100.00% |
| multilingual_scan_no_ocr | 5 | 0.00% | 0 | 100.00% |
| varied_scan_no_ocr | 75 | 0.00% | 0 | 100.00% |
| varied_text | 525 | 100.00% | 0 | 0.00% |

Exact match = correct proposals / answerable fields. Abstentions are not correct answers. Critical error = wrong proposals / all proposals, including unsafe proposals on unanswerable fields. N/A means no denominator.

Summary facts checked: 264; citations checked: 69; errors: 0.
Comparison precision: 100.00%; recall: 100.00%.
Security suite: pass (26 executed tests).

## Local measurements

```json
{
  "extraction_p50_ms": 103.17175003001466,
  "extraction_p95_ms": 150.51154204411432,
  "summary_p95_ms": 0.32404199009761214,
  "external_ai_calls": 0,
  "external_inference_cost_inr": "0.00",
  "hosting_cpu_storage_cost": "not_measured",
  "queue_latency": "not_measured_offline_runner",
  "manual_baseline_time": "not_measured_requires_human_study",
  "human_correction_rate": "not_measured_requires_reviewer_dispositions"
}
```

## Limits and remaining acceptance

- No bank-supplied or representative real FDRs.
- Layout families differ from preexisting extraction test fixtures; no statistical generalization claim.
- If outputs inform parser changes, this corpus becomes regression evidence, not an independent post-change holdout.
- Scanned/multilingual images exercise explicit manual fallback; no OCR or multilingual text recognition is configured.
- Initial text-rules-1 run found 2 unsafe proposals (overprecision and out-of-range amounts). text-rules-2 fixes these; this observed corpus is now regression evidence.
- Representative layout/noise thresholds and human time/correction baselines require approved samples and named owner acceptance.
- Local parser/service runtimes exclude queue wait and network transfer; zero external inference fees excludes infrastructure/operations costs.
- JUnit/logs and source/library versions are recorded with the machine-readable report. No production security, statistical generalization or cloud performance certification.
