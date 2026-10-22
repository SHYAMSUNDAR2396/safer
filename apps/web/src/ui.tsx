import { useEffect, useRef, type ReactNode } from "react";
import { Check, X } from "lucide-react";
import { api } from "./api";
import type {
  AuditEvent,
  DocumentFile,
  DocumentKind,
  Instrument,
  Me,
} from "./types";

export const events: Record<string, string> = {
  "instrument.created": "Draft created",
  "instrument.updated": "Draft updated",
  "instrument.submitted": "Metadata submitted",
  "document.uploaded": "Document uploaded · quarantined",
  "document.scanned": "Malware scan completed",
  "document.scan_failed": "Malware scan failed",
  "document.downloaded": "Document downloaded",
  "review.evidence_recorded": "Independent evidence recorded",
  "review.discrepancy_raised": "Observation raised",
  "review.discrepancy_answered": "Observation answered",
  "review.discrepancy_resolved": "Observation resolved",
  "review.bank_requested": "Simulated bank confirmation requested",
  "review.bank_answered": "Simulated bank answer recorded",
};
export const documentStatus: Record<DocumentFile["status"], string> = {
  pending: "Uploading",
  quarantined: "Quarantined · awaiting scan",
  failed: "Upload incomplete",
};
export const scanStatus: Record<
  NonNullable<DocumentFile["scan_status"]>,
  string
> = {
  pending: "Quarantined · scanning",
  clean: "Scanned clean",
  infected: "Blocked · malware found",
  rejected: "Blocked · integrity check failed",
  failed: "Scan failed · stays quarantined",
};
export function documentBadge(d: DocumentFile): [string, string] {
  if (!d.scan_status) return [d.status, documentStatus[d.status]];
  const tone = ["pending", "clean"].includes(d.scan_status)
    ? d.scan_status
    : "failed";
  return [tone, scanStatus[d.scan_status]];
}
export const kindLabels: Record<DocumentKind, string> = {
  fdr_certificate: "FDR certificate",
  bank_letter: "Bank covering letter",
  other: "Other supporting document",
};
export const MAX_UPLOAD = 10 * 1024 * 1024;
export function fileSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function Notice({ message }: { message: string }) {
  return (
    <div className="error" role="alert">
      {message}
    </div>
  );
}
export async function refreshedSession(expected: Me) {
  const current = await api<Me>("/api/v1/me");
  if (
    current.id !== expected.id ||
    current.institution.id !== expected.institution.id ||
    current.role !== expected.role
  )
    throw new Error(
      "The signed-in account or permissions changed. Sign back in with the original account before saving.",
    );
  return current;
}
export function Recovery() {
  return (
    <p className="dialog-intro">
      Session expired?{" "}
      <a href="/auth/login" target="_blank" rel="noopener noreferrer">
        <strong>Sign in again in a new tab</strong>
      </a>
      , then return here and retry. Your entered details stay in this tab.
    </p>
  );
}
export function Badge({ status }: { status: Instrument["status"] }) {
  return (
    <span className={`badge ${status}`}>
      <span />
      {status === "draft" ? "Draft" : "Submitted"}
    </span>
  );
}
export function Dialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current!;
    d.showModal();
    return () => {
      d.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-labelledby="dialog-title"
    >
      <div className="dialog-head">
        <h2 id="dialog-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export function Timeline({ items }: { items: AuditEvent[] }) {
  return (
    <ol className="timeline">
      {items.map((e) => (
        <li key={e.id}>
          <span className="timeline-mark">
            <Check size={12} />
          </span>
          <strong>{events[e.action] || e.action}</strong>
          <span>{e.actor}</span>
          <time dateTime={e.created_at}>
            {new Date(e.created_at).toLocaleString("en-IN")}
          </time>
          <small>Version {e.row_version}</small>
        </li>
      ))}
    </ol>
  );
}
