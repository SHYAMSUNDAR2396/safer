# Local alert response and future operational ownership

These are tested local contracts, not a staffed SOC or real SIEM integration.
`security-service-owner` is a placeholder. AICTE must assign a named primary/backup,
approve retention and exercise the actual destinations before pilot. High alerts
target acknowledgement within 15 minutes; medium within 60 minutes. These are proposed
response targets, not measured staffing guarantees. Capture-only delivery is Mailpit.

For every alert, record UTC time, rule and request correlation ID without copying
passwords, cookies, tokens, receipt contents or unnecessary personal information.
Preserve original evidence and independently held checkpoints before corrective work.
The local archive contains a minimal event projection; source DB audit remains the
business record. Do not treat its hash chain as independent immutable retention.

## Repeated access denials

Rule `repeated-access-denials`: at least ten application access-denial events in a
bounded five-minute window. Check for an expired grant, stale session or automated
probing using scoped metadata. Revoke compromised sessions/users through authorized
procedures; inspect adjacent authority changes. Real rate-limit/WAF escalation waits
for the selected hosting platform. Do not reveal another institution's record to
diagnose a denial.

## Privileged MFA reset

Rule `privileged-mfa-reset`: any identity MFA-reset event. Verify an independently
approved reset request and administrator identity; if unexpected, contain the account,
revoke app and IdP sessions, preserve identity logs and investigate grant changes.
The test-factor cleanup script applies only to fixed labelled synthetic accounts and
does not define the production recovery procedure.

## Key deletion attempt

Rule `key-deletion-attempt`: any KMS deletion attempt. Preserve provider audit records,
deny destructive changes, revoke the suspicious credential and involve the independent
key custodian. Check affected key versions and decryptability in isolation. Do not
rotate, delete or restore keys casually: restoring ciphertext without its correct
wrapping keys does not recover documents. Runtime Transit policy cannot rotate/delete.

## Backup freshness

Rule `backup-freshness`: backup freshness signal supplied by the future scheduler.
Inspect failed jobs and last independently recoverable checkpoint; rerun a backup into
a new protected destination and verify restore before clearing the alert. The current
local drill is manual, not an operational backup schedule or whole-system RPO monitor.

## Audit checkpoint gap

Rule `audit-checkpoint-gap`: missing, reordered or altered projection/checkpoint signal.
Preserve both copies and source database logs, suspend suspect export credentials,
compare against an independently administered destination. Never rewrite the checkpoint
to match suspect data. The local single-custodian checkpoint cannot resist a custodian
rewriting both archive and manifest; pilot needs independent retention lock and holds.

## Sensitive authority change

Rule `sensitive-authority-change`: any sensitive grant-change signal. Confirm initiator,
second approver, institution scope, expiry and reason against the approved authority
matrix. Revoke unauthorized authority and sessions; inspect decisions during exposure.
Re-evaluate material approval bases without deleting historical decisions.

## Recovery and external effects

Contain and preserve evidence first. Keep relays, workers, bank adapters and notification
senders paused against any restored database. Restore into a **new** isolated database,
then verify immutable history, object version/hash bindings, identity memberships,
wrapping-key availability and authority validity. Reconcile already delivered messages,
bank instructions/execution evidence and uncertain jobs against external sources before
enabling delivery. Never replay payment-like effects from a backup. SAFER currently
records release instructions/evidence only and has no payment API. Record incident
timeline, exposure, corrections and owner authorization for resumption.
