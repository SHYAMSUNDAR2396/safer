export type Me = {
  id: string;
  display_name: string;
  role: "institution_user" | "auditor" | "reviewer" | "admin";
  institution: { id: string; name: string };
  csrf_token: string;
  demo: boolean;
};
export type Obligation = {
  id: string;
  title: string;
  required_amount: string;
  currency: string;
  required_documents: DocumentKind[];
};
export type Draft = {
  obligation_id: string;
  bank_name: string;
  bank_reference: string;
  principal_amount: string;
  currency: "INR";
  issue_date: string;
  maturity_date: string;
};
export type Instrument = Draft & {
  id: string;
  institution_id: string;
  status: "draft" | "submitted";
  verification_status: "unverified";
  row_version: number;
  created_at: string;
};
export type Register = {
  items: Instrument[];
  next_cursor: string | null;
  summary: {
    total: number;
    drafts: number;
    submitted: number;
    recorded_amount: string;
  };
};
export type AuditEvent = {
  id: string;
  action: string;
  actor: string;
  row_version: number;
  created_at: string;
  request_id: string;
};
export type DocumentKind = "fdr_certificate" | "bank_letter" | "other";
export type Requirement = {
  kind: DocumentKind;
  label: string;
  document_id: string | null;
  satisfied: boolean;
};
export type DocumentFile = {
  id: string;
  kind: DocumentKind;
  current: boolean;
  filename: string;
  media_type: "application/pdf" | "image/png" | "image/jpeg";
  size_bytes: number;
  page_count: number | null;
  sha256: string;
  status: "pending" | "quarantined" | "failed";
  scan_status: "pending" | "clean" | "infected" | "rejected" | "failed" | null;
  created_at: string;
};
export type CaseField =
  | "bank_name"
  | "bank_reference"
  | "principal_amount"
  | "issue_date"
  | "maturity_date";
export type ReviewItem = {
  instrument_id: string;
  institution: { id: string; name: string };
  bank_name: string;
  bank_reference: string;
  principal_amount: string;
  maturity_date: string;
  submitted_at: string;
  confirmed_fields: number;
  mismatched_fields: number;
  simulated_fields: number;
  escalated: boolean;
  open_discrepancies: number;
};
export type Comparison = {
  field: CaseField;
  label: string;
  claimed: string;
  confirmed: string | null;
  status: "match" | "mismatch" | "unconfirmed";
  simulated: boolean;
};
export type BankExchange = {
  id: string;
  provider: "simulator";
  simulated: boolean;
  outcome:
    "pending" | "confirmed" | "not_found" | "timeout" | "rejected" | "stale";
  detail: string;
  requested_at: string;
  answered_at: string | null;
};
export type Evidence = {
  id: string;
  field: CaseField;
  label: string;
  value: string;
  source: string;
  method:
    | "bank_portal"
    | "bank_email"
    | "bank_letter"
    | "phone_callback"
    | "bank_simulator";
  observer: string;
  observed_at: string;
  note: string;
};
export type Discrepancy = {
  id: string;
  field: CaseField | null;
  label: string;
  message: string;
  raised_by: string;
  created_at: string;
  status: "open" | "resolved";
  replies: {
    id: string;
    kind: "response" | "resolution";
    author: string;
    message: string;
    created_at: string;
  }[];
};
export type ReviewCase = {
  instrument_id: string;
  institution: { id: string; name: string };
  submitted_at: string;
  claim: Record<CaseField, string>;
  comparison: Comparison[];
  evidence: Evidence[];
  documents: DocumentFile[];
  submitted_documents: { id: string }[];
  discrepancies: Discrepancy[];
  bank_requests: BankExchange[];
  deadlines: Deadlines;
  replacement: ReplacementView;
  coverage: Coverage;
  releases: Release[];
  audit: AuditEvent[];
};
export type Deadlines = {
  maturity_date: string;
  action_due_date: string | null;
  obligation_required_until: string | null;
  renewal_required: boolean;
  replacement_status: "proposed" | "accepted" | null;
  schedule_version: number | null;
  reminders: {
    step: string;
    kind: "maturity_reminder" | "action_due" | "escalation";
    owner_role: "institution" | "reviewer";
    message: string;
    due_at: string;
    generated_at: string;
    late: boolean;
    deliveries: {
      recipient: string;
      channel: "email";
      status: "pending" | "sent" | "failed" | "uncertain";
      detail: string;
    }[];
  }[];
  upcoming: { step: string; kind: string; due_at: string }[];
  escalation_owners: string[];
};
export type Inbox = {
  unread_count: number;
  items: {
    id: string;
    instrument_id: string;
    subject: string;
    body: string;
    created_at: string;
    read: boolean;
  }[];
};
export type ReplacementLink = {
  id: string;
  predecessor_id: string;
  predecessor_reference: string;
  successor_id: string;
  successor_reference: string;
  status: "proposed" | "accepted" | "rejected";
  proposed_by: string;
  proposed_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string;
};
export type ReplacementView = {
  outgoing: ReplacementLink | null;
  incoming: ReplacementLink | null;
  candidates?: {
    id: string;
    bank_reference: string;
    maturity_date: string;
    principal_amount: string;
  }[];
};
export type Coverage = {
  obligation_id: string;
  title: string;
  required_amount: string;
  covered_amount: string;
  proposed_amount: string;
  gap_amount: string;
  basis: string;
  instruments: {
    id: string;
    bank_reference: string;
    principal_amount: string;
    maturity_date: string;
    state: "counting" | "superseded" | "proposed_successor";
  }[];
};
export type Grant = {
  id: string;
  user_id: string;
  user: string;
  authority: "review" | "release_approve";
  institution: { id: string; name: string };
  status: "pending" | "active" | "rejected" | "revoked" | "expired";
  effective: boolean;
  valid_from: string;
  valid_until: string | null;
  requested_by: string | null;
  approved_by: string | null;
  delegated_from: string | null;
  reason: string;
  created_at: string;
  revoked_by: string | null;
  revoke_reason: string;
};
export type PolicyVersion = {
  id: string;
  policy_id: string;
  code: "release";
  version: number;
  applies_to: string;
  effective_from: string;
  effective_until: string | null;
  rules: {
    clearances: string[];
    release_not_before: "obligation_end" | "any_time";
  };
  note: string;
  status: "draft" | "published";
  owner_validated: boolean;
  drafted_by: string;
  published_by: string | null;
};
export type Release = {
  id: string;
  instrument_id: string;
  bank_reference: string;
  status:
    "open" | "on_hold" | "returned" | "approved" | "rejected" | "withdrawn";
  effective_status: string;
  approval_valid: boolean;
  reason: string;
  requested_by: string;
  created_at: string;
  policy: {
    policy_id: string;
    version: number;
    owner_validated: boolean;
    rules: { clearances: string[]; release_not_before: string };
  };
  clearances: { clearance: string; done: boolean; cleared_by: string | null }[];
  ready_for_decision: boolean;
  decided_by: string | null;
  decision_note: string;
  basis: string;
  events: { kind: string; actor: string; note: string; created_at: string }[];
};
