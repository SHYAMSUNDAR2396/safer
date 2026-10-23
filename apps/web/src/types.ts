export type Me = {
  id: string;
  display_name: string;
  role: "institution_user" | "auditor" | "reviewer";
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
  audit: AuditEvent[];
};
export type Deadlines = {
  maturity_date: string;
  action_due_date: string | null;
  obligation_required_until: string | null;
  renewal_required: boolean;
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
