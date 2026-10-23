import { useEffect, useRef, useState, type ReactNode } from "react";
import { Bell, BellRing, CalendarClock, Check, X } from "lucide-react";
import { api, day } from "./api";
import type {
  AuditEvent,
  Deadlines,
  Inbox as InboxData,
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
  "deadline.maturity_reminder": "Maturity reminder generated",
  "deadline.action_due": "Renewal action due",
  "deadline.escalation": "Escalated to reviewer",
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

const reminderLabels: Record<Deadlines["reminders"][number]["kind"], string> = {
  maturity_reminder: "Maturity reminder",
  action_due: "Renewal action due",
  escalation: "Escalated to reviewer",
};

const deliveryLabels = {
  pending: "sending",
  sent: "sent (local capture)",
  failed: "failed",
  uncertain: "uncertain — may not have arrived",
};

function stepLabel(step: string) {
  if (step.startsWith("reminder:")) return `${step.slice(9)}-day notice`;
  return step === "action_due" ? "Action due" : "Escalation";
}

export function DeadlinesPanel({ data }: { data: Deadlines }) {
  return (
    <section className="panel documents">
      <div className="section-title">
        <CalendarClock size={19} />
        <h2>Deadlines and reminders</h2>
      </div>
      <p className="muted small">
        Maturity, the action date and the obligation's own cover are tracked
        separately.
        {data.schedule_version &&
          ` Reminder schedule v${data.schedule_version} · illustrative policy.`}
      </p>
      <dl className="facts deadline-dates">
        <div>
          <dt>FDR maturity</dt>
          <dd>{day(data.maturity_date)}</dd>
        </div>
        <div>
          <dt>Renewal action due</dt>
          <dd>
            {data.action_due_date
              ? day(data.action_due_date)
              : "Not needed · cover ends before maturity"}
          </dd>
        </div>
        <div>
          <dt>Obligation cover required until</dt>
          <dd>
            {data.obligation_required_until
              ? day(data.obligation_required_until)
              : "Until formally released"}
          </dd>
        </div>
      </dl>
      {data.reminders.length > 0 && (
        <ul className="evidence-log">
          {data.reminders.map((r) => (
            <li key={r.step} className={`reminder ${r.kind}`}>
              <strong>
                <BellRing size={13} /> {reminderLabels[r.kind]}
                {r.late ? " · generated late" : ""}
              </strong>
              <span>{r.message}</span>
              {r.kind === "escalation" && (
                <span>
                  Owner:{" "}
                  {data.escalation_owners.length
                    ? data.escalation_owners.join(", ")
                    : "no reviewer assigned"}
                </span>
              )}
              <small>
                Due {new Date(r.due_at).toLocaleString("en-IN")} · generated{" "}
                {new Date(r.generated_at).toLocaleString("en-IN")}
              </small>
              {r.deliveries.length > 0 && (
                <span className="deliveries">
                  {r.deliveries.map((d) => (
                    <span
                      key={d.recipient}
                      className={`badge delivery-${d.status}`}
                      title={d.detail}
                    >
                      <span />
                      Email to {d.recipient}: {deliveryLabels[d.status]}
                    </span>
                  ))}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {data.upcoming.length > 0 && (
        <p className="doc-empty">
          Next:{" "}
          {data.upcoming
            .slice(0, 3)
            .map(
              (u) =>
                `${stepLabel(u.step)} on ${new Date(u.due_at).toLocaleDateString("en-IN")}`,
            )
            .join(" · ")}
        </p>
      )}
    </section>
  );
}

export function Inbox({ me }: { me: Me }) {
  const [data, setData] = useState<InboxData | null>(null);
  const [open, setOpen] = useState(false);
  const load = () =>
    api<InboxData>("/api/v1/notifications")
      .then(setData)
      .catch(() => undefined);
  useEffect(() => {
    void load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, []);
  async function read(id: string) {
    try {
      const current = await refreshedSession(me);
      await api(
        `/api/v1/notifications/${id}/read`,
        { method: "POST" },
        current.csrf_token,
      );
    } finally {
      void load();
    }
  }
  const unread = data?.unread_count ?? 0;
  return (
    <div className="inbox">
      <button
        className="icon-button"
        aria-label={`Notifications, ${unread} unread`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell size={18} />
        {unread > 0 && <span className="unread">{unread}</span>}
      </button>
      {open && (
        <div className="inbox-panel" role="region" aria-label="Notifications">
          <strong>Notifications</strong>
          {data?.items.length ? (
            <ul>
              {data.items.map((n) => (
                <li key={n.id} className={n.read ? "read" : ""}>
                  <b>{n.subject}</b>
                  <span>{n.body.split("\n")[0]}</span>
                  <small>
                    {n.body.split("\n")[1]} ·{" "}
                    {new Date(n.created_at).toLocaleString("en-IN")}
                  </small>
                  {!n.read && (
                    <button className="text-button" onClick={() => read(n.id)}>
                      Mark as read
                    </button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="doc-empty">No notifications yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
