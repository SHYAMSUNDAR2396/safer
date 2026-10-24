# API v1

Live OpenAPI: `http://localhost:8000/openapi.json`; interactive docs: `/docs`. Snapshot: `contracts/openapi.json`. All business endpoints require opaque session cookie `safer_session`. GET `/api/v1/me` returns CSRF token. Mutations require `Origin: http://localhost:5173` and `X-CSRF-Token`.

| Method | Path | Result |
|---|---|---|
| GET | /auth/login | OIDC redirect |
| GET | /auth/callback | Validates identity; establishes app session |
| POST | /auth/logout | Revokes app session, 204 |
| GET | /api/v1/me | Current identity, local grant, CSRF |
| GET | /api/v1/obligations | Scoped obligations |
| GET | /api/v1/instruments | Register; q, cursor, limit 1–100; institution summary |
| POST | /api/v1/instruments | New draft, 201 + ETag |
| GET | /api/v1/instruments/{id} | Scoped record + ETag |
| PATCH | /api/v1/instruments/{id} | Full draft payload, If-Match required |
| POST | /api/v1/instruments/{id}/submissions | Body {}, If-Match and Idempotency-Key; 201 new / 200 replay |
| GET | /api/v1/instruments/{id}/audit | Scoped history |
| GET | /api/v1/instruments/{id}/documents | Scoped document metadata (no storage keys), `current` flag and `requirements` checklist |
| POST | /api/v1/instruments/{id}/documents?filename=&kind= | kind fdr_certificate, bank_letter or other; raw file body, Content-Type application/pdf, image/png or image/jpeg; draft only; 201 quarantined |
| GET | /api/v1/documents/{id}/download | Clean files only; attachment with sandbox CSP; audited |
| GET | /api/v1/reviews | Reviewer queue: assigned institutions' submitted cases |
| GET | /api/v1/reviews/{id} | Claim, field comparison, evidence log, documents, observations, audit |
| POST | /api/v1/reviews/{id}/evidence | field, value, source, method, observed_at (timezone required, not future), note |
| POST | /api/v1/reviews/{id}/discrepancies | field (or null for general), message |
| GET | /api/v1/instruments/{id}/discrepancies | Observations on the institution's own record |
| POST | /api/v1/discrepancies/{id}/replies | message, resolve (reviewers only); 409 once resolved |
| POST | /api/v1/reviews/{id}/bank-requests | Body {}; asks the SIMULATED bank; 201 with outcome confirmed, not_found, timeout, rejected or stale |
| GET | /api/v1/instruments/{id}/deadlines | Maturity, action and obligation dates, schedule version, generated reminders, upcoming steps, escalation owners |
| GET | /api/v1/notifications | Own in-app notifications (latest 50) and unread count |
| POST | /api/v1/notifications/{id}/read | Mark own notification read; 204 |
| GET | /api/v1/instruments/{id}/replacement | Outgoing/incoming link and eligible successors |
| POST | /api/v1/instruments/{id}/replacement | Body {successor_id}; institution officer proposes; 201 |
| POST | /api/v1/replacements/{id}/decision | Body {accept, note}; assigned reviewer; 409 once decided |
| GET | /api/v1/obligations/{id}/coverage | Required, counted, proposed and gap amounts with per-FDR state |
| GET | /api/v1/admin/users, /api/v1/admin/grants | Admin: people, organisations and grant history |
| POST | /api/v1/admin/grants | Admin: user_id, authority, institution_id, valid_until, reason; review active at once, release_approve pending |
| POST | /api/v1/admin/grants/{id}/approve, /reject, /revoke | Admin: second-admin approval; reject or withdraw; revoke (cascades to delegations) |
| GET | /api/v1/grants/mine, /api/v1/grants/delegates | Reviewer: own grants and delegations; possible delegates |
| POST | /api/v1/grants/{id}/delegate, /api/v1/grants/{id}/revoke | Reviewer: delegate own grant; end a delegation |
| GET | /api/v1/admin/policies | Admin: all versions |
| POST | /api/v1/admin/policies | Admin: draft code, applies_to, effective_from/until, rules, note |
| POST | /api/v1/admin/policies/{id}/publish | A different admin publishes; 409 if already published |
| GET | /api/v1/obligations/{id}/policy?on=YYYY-MM-DD | Release policy in force for an own obligation |
| POST | /api/v1/instruments/{id}/release-requests | Institution: reason; 409 not_eligible / no_policy / already_requested |
| GET | /api/v1/instruments/{id}/release-requests, /api/v1/release-requests/{id} | Requests with policy snapshot, clearances, events, basis, validity |
| POST | /api/v1/release-requests/{id}/withdraw, /resubmit | Institution |
| POST | /api/v1/release-requests/{id}/clearances, /hold, /resume, /return, /reopen | Reviewer with review authority |
| POST | /api/v1/release-requests/{id}/decision | Holder of release authority: approve, note, basis; Idempotency-Key required |
| GET | /api/v1/releases/pending | Approver: open requests within release authority |
| POST | /api/v1/release-requests/{id}/instruction | Holder of release authority; valid approval required; one per request |
| POST | /api/v1/release-requests/{id}/execution | Reviewer (not approver/instructor): executed_amount, executed_on, bank_transaction_ref, source, method, observed_at, note |
| POST | /api/v1/release-requests/{id}/close | Reviewer: needs valid approval and matched reconciliation; FDR becomes closed |
| GET | /api/v1/dashboard | Scoped metrics (key, group, label, grain, count, amount) and per-obligation cover |
| GET | /api/v1/dashboard/{key} | The FDRs a metric counts |
| GET | /health/live | Process liveness |
| GET | /health/ready | Database connection readiness |

Draft: obligation_id UUID, bank_name string, bank_reference string (leading zeros preserved), principal_amount decimal string, currency INR, issue_date and maturity_date ISO dates. Maturity must be later than issue. Institution, status and verification cannot be supplied by clients.

Use `If-Match: "1"` matching row_version. Missing precondition =428, stale=412, submitted-state conflict=409. Authentication=401, permission/CSRF=403, out-of-scope/missing=404, invalid input=422, temporary storage failure=503. Problems use application/problem+json with code/detail/request_id and safe field_errors where applicable. Never treat submission success as bank confirmation.

Pagination is keyset based on creation time and UUID. Summary covers all authorized institution records, independent of search. Audit history is not paginated yet. Endpoint rate limiting is a pilot gate, not implemented. Readiness does not check Keycloak or migration version.

Upload errors: 413 file_too_large (>10 MB), 415 unsupported_type (signature/type mismatch or other format), 422 file_rejected (encrypted, page/pixel limit, unreadable) or invalid_filename, 409 already_submitted / document_limit, 503 storage_unavailable. The body is the file itself, not multipart; it is read only after authentication and streamed with a hard cap. There is deliberately no download endpoint until SAF-009 scanning.

Document views carry `scan_status`: pending, clean, infected, rejected (stored bytes did not match the upload hash), failed (3 scanner errors) or null for incomplete uploads. Download returns 404 outside the institution, 409 not_available unless clean, 409 integrity_failed if stored bytes no longer match, 503 storage_unavailable. It is a GET so a plain link works; the side effect is an audit record only.

Submission returns 409 `documents_required` until each required kind's current document is scanned clean. The snapshot gains `documents`: id, kind, filename, sha256, object_version. Obligations include `required_documents`.

Case views include `bank_requests` and each comparison row's `simulated` flag; the queue reports `simulated_fields` separately from `confirmed_fields`.

Review case views include `deadlines`; queue rows include `escalated`.

Deadline reminders include `deliveries`: per-recipient email status (pending, sent, failed, uncertain) and detail.

Release views now include `instruction`, `executions` and `reconciliation`. Instrument status may be `closed`. Review case views include the FDR `status` and remain readable after closure.
