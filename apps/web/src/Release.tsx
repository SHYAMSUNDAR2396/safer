import { useEffect, useState } from "react";
import { Gavel, Landmark } from "lucide-react";
import { api, money } from "./api";
import { clearanceLabels } from "./Access";
import type { Me, Release } from "./types";
import { Notice, refreshedSession } from "./ui";

const statusText: Record<string, string> = {
  open: "Open · clearances in progress",
  on_hold: "On hold",
  returned: "Returned to institution",
  approved: "Approved",
  approval_invalidated: "Approval invalidated by a material change",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  closed: "Closed · executed and reconciled",
};
const eventText: Record<string, string> = {
  requested: "Requested",
  cleared: "Clearance recorded",
  held: "Put on hold",
  resumed: "Resumed",
  returned: "Returned",
  resubmitted: "Resubmitted",
  reopened: "Reopened after change",
  approved: "Approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  instructed: "Instruction issued",
  executed: "Bank execution recorded",
  closed: "Closed",
};

async function send(me: Me, path: string, body: unknown, key?: string) {
  const current = await refreshedSession(me);
  return api<Release>(
    path,
    {
      method: "POST",
      body: JSON.stringify(body),
      headers: key ? { "Idempotency-Key": key } : {},
    },
    current.csrf_token,
  );
}

export function ReleaseCard({
  req,
  me,
  canReview,
  canDecide,
  onChange,
}: {
  req: Release;
  me: Me;
  canReview: boolean;
  canDecide: boolean;
  onChange: () => void;
}) {
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [key] = useState(() => crypto.randomUUID());
  async function act(action: string, body: object, idem?: string) {
    setBusy(true);
    setError("");
    try {
      await send(
        me,
        `/api/v1/release-requests/${req.id}/${action}`,
        body,
        idem,
      );
      setNote("");
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const s = req.status;
  const institution = me.role === "institution_user";
  const withNote = (action: string) => () => act(action, { note });
  const open = s === "open" || s === "on_hold";
  const valid = s === "approved" && req.approval_valid;
  const canInstruct = canDecide && valid && !req.instruction;
  const canExecute = canReview && s === "approved" && !!req.instruction;
  const canClose =
    canReview && valid && req.reconciliation?.status === "matched";
  const hasActions =
    (canReview && (open || (s === "approved" && !req.approval_valid))) ||
    (canDecide && s === "open") ||
    canInstruct ||
    canClose ||
    (institution && ["open", "on_hold", "returned"].includes(s));
  return (
    <div className={`release-card ${req.effective_status}`}>
      <div className="thread-head">
        <strong>
          Release of {req.bank_reference} · policy v{req.policy.version}
          {req.policy.owner_validated ? "" : " (illustrative)"}
        </strong>
        <span className={`badge release-${req.effective_status}`}>
          <span />
          {req.ready_for_decision
            ? "Ready for decision"
            : statusText[req.effective_status] || req.effective_status}
        </span>
      </div>
      <p>{req.reason}</p>
      <ul className="requirements">
        {req.clearances.map((c) => (
          <li key={c.clearance} className={c.done ? "met" : ""}>
            <span>
              <strong>{clearanceLabels[c.clearance]}</strong>
              {c.done ? ` · cleared by ${c.cleared_by}` : " · pending"}
            </span>
            {canReview && !c.done && (s === "open" || s === "on_hold") && (
              <button
                className="text-button"
                disabled={busy || !note.trim()}
                onClick={() =>
                  act("clearances", { clearance: c.clearance, note })
                }
              >
                Record clearance
              </button>
            )}
          </li>
        ))}
      </ul>
      {error && <Notice message={error} />}
      {hasActions && (
        <div className="reply-form">
          <label>
            Note for this action
            <input
              value={note}
              maxLength={500}
              disabled={busy}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <div className="simulator-actions">
            {canReview && s === "open" && (
              <button
                className="secondary"
                disabled={busy || !note.trim()}
                onClick={withNote("hold")}
              >
                Put on hold
              </button>
            )}
            {canReview && s === "on_hold" && (
              <button
                className="secondary"
                disabled={busy || !note.trim()}
                onClick={withNote("resume")}
              >
                Resume
              </button>
            )}
            {canReview && (s === "open" || s === "on_hold") && (
              <button
                className="secondary"
                disabled={busy || !note.trim()}
                onClick={withNote("return")}
              >
                Return to institution
              </button>
            )}
            {canReview && s === "approved" && !req.approval_valid && (
              <button
                className="secondary"
                disabled={busy || !note.trim()}
                onClick={withNote("reopen")}
              >
                Reopen for a new decision
              </button>
            )}
            {institution && s === "returned" && (
              <button
                className="primary"
                disabled={busy || !note.trim()}
                onClick={withNote("resubmit")}
              >
                Resubmit
              </button>
            )}
            {institution && ["open", "on_hold", "returned"].includes(s) && (
              <button
                className="secondary"
                disabled={busy || !note.trim()}
                onClick={withNote("withdraw")}
              >
                Withdraw request
              </button>
            )}
            {canInstruct && (
              <button
                className="primary"
                disabled={busy || !note.trim()}
                onClick={withNote("instruction")}
              >
                Issue release instruction
              </button>
            )}
            {canClose && (
              <button
                className="primary"
                disabled={busy || !note.trim()}
                onClick={withNote("close")}
              >
                Close case
              </button>
            )}
            {canDecide && s === "open" && (
              <>
                <button
                  className="secondary"
                  disabled={busy || !note.trim()}
                  onClick={() =>
                    act(
                      "decision",
                      { approve: false, note, basis: req.basis },
                      key,
                    )
                  }
                >
                  Reject release
                </button>
                <button
                  className="primary"
                  disabled={busy || !note.trim() || !req.ready_for_decision}
                  title={
                    req.ready_for_decision
                      ? ""
                      : "All clearances must be recorded first"
                  }
                  onClick={() =>
                    act(
                      "decision",
                      { approve: true, note, basis: req.basis },
                      key,
                    )
                  }
                >
                  Approve release
                </button>
              </>
            )}
          </div>
        </div>
      )}
      {req.instruction && (
        <p className="link-line">
          Instruction <strong>{req.instruction.reference}</strong> to{" "}
          {req.instruction.addressed_to} for {money(req.instruction.amount)} ·
          issued by {req.instruction.issued_by}
        </p>
      )}
      {req.executions.map((e, i) => (
        <p key={i} className="link-line">
          Bank executed {money(e.executed_amount)} on {e.executed_on} · ref{" "}
          {e.bank_transaction_ref} · {e.source} · recorded by {e.observer}
        </p>
      ))}
      {req.reconciliation && <Reconciliation r={req.reconciliation} />}
      {canExecute && <ExecutionForm req={req} me={me} onChange={onChange} />}
      <ol className="release-events">
        {req.events.map((e, i) => (
          <li key={i}>
            <strong>{eventText[e.kind] || e.kind}</strong> · {e.actor} ·{" "}
            {new Date(e.created_at).toLocaleString("en-IN")}
            {e.note && (
              <span>
                {" "}
                —{" "}
                {e.kind === "cleared"
                  ? `${clearanceLabels[e.note.split(": ")[0]] ?? ""}: ${e.note.split(": ").slice(1).join(": ")}`
                  : e.note}
              </span>
            )}
          </li>
        ))}
      </ol>
      <p className="muted small">
        Approval records an administrative decision only. No money is moved by
        this portal; release execution is a separate step.
      </p>
    </div>
  );
}

export function InstitutionRelease({ id, me }: { id: string; me: Me }) {
  const [items, setItems] = useState<Release[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    api<{ items: Release[] }>(`/api/v1/instruments/${id}/release-requests`)
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, [id]);
  const live = items.some((r) =>
    ["open", "on_hold", "returned", "approved"].includes(r.status),
  );
  async function ask() {
    setBusy(true);
    setError("");
    try {
      await send(me, `/api/v1/instruments/${id}/release-requests`, { reason });
      setReason("");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel documents">
      <div className="section-title">
        <Landmark size={19} />
        <h2>Release of this deposit</h2>
      </div>
      <p className="muted small">
        Release follows the published release policy: required clearances, then
        a decision by an official with release authority.
      </p>
      {error && <Notice message={error} />}
      {items.map((r) => (
        <ReleaseCard
          key={r.id}
          req={r}
          me={me}
          canReview={false}
          canDecide={false}
          onChange={load}
        />
      ))}
      {!live && me.role === "institution_user" && (
        <div className="upload-row">
          <label>
            Reason for release
            <input
              value={reason}
              maxLength={500}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <button
            className="secondary"
            disabled={busy || !reason.trim()}
            onClick={ask}
          >
            Request release
          </button>
        </div>
      )}
    </section>
  );
}

export function ReleaseDecisions({ me }: { me: Me }) {
  const [items, setItems] = useState<Release[] | null>(null);
  const load = () =>
    api<{ items: Release[] }>("/api/v1/releases/pending")
      .then((r) => setItems(r.items))
      .catch(() => setItems([]));
  useEffect(() => {
    void load();
  }, []);
  if (!items?.length) return null;
  return (
    <section className="panel documents">
      <div className="section-title">
        <Gavel size={19} />
        <h2>Release decisions</h2>
      </div>
      <p className="muted small">
        Requests within your release authority. You cannot decide a request on
        which you recorded a clearance.
      </p>
      {items.map((r) => (
        <ReleaseCard
          key={r.id}
          req={r}
          me={me}
          canReview={false}
          canDecide
          onChange={load}
        />
      ))}
    </section>
  );
}

function Reconciliation({ r }: { r: NonNullable<Release["reconciliation"]> }) {
  const short = r.difference.startsWith("-");
  return (
    <p className={`reconcile ${r.status}`} role="status">
      Reconciliation:{" "}
      {r.status === "matched"
        ? "executed amount matches the instruction"
        : `${money(r.difference.replace("-", ""))} ${short ? "short of" : "more than"} the instruction`}
    </p>
  );
}

function ExecutionForm({
  req,
  me,
  onChange,
}: {
  req: Release;
  me: Me;
  onChange: () => void;
}) {
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
  const [f, setF] = useState({
    executed_amount: req.instruction?.amount ?? "",
    executed_on: now.slice(0, 10),
    bank_transaction_ref: "",
    source: "",
    method: "bank_letter",
    observed_at: now,
    note: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f, v: string) => setF((o) => ({ ...o, [k]: v }));
  async function save() {
    setBusy(true);
    setError("");
    try {
      await send(me, `/api/v1/release-requests/${req.id}/execution`, {
        ...f,
        observed_at: new Date(f.observed_at).toISOString(),
      });
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="all-cover">
      <summary>Record the bank's execution evidence</summary>
      <fieldset disabled={busy} className="policy-form">
        <div className="form-grid">
          <label>
            Amount the bank released (INR)
            <input
              inputMode="decimal"
              value={f.executed_amount}
              onChange={(e) => set("executed_amount", e.target.value)}
            />
          </label>
          <label>
            Executed on
            <input
              type="date"
              value={f.executed_on}
              onChange={(e) => set("executed_on", e.target.value)}
            />
          </label>
        </div>
        <div className="form-grid">
          <label>
            Bank transaction reference
            <input
              value={f.bank_transaction_ref}
              maxLength={100}
              onChange={(e) => set("bank_transaction_ref", e.target.value)}
            />
          </label>
          <label>
            Source (bank, branch or contact)
            <input
              value={f.source}
              maxLength={200}
              onChange={(e) => set("source", e.target.value)}
            />
          </label>
        </div>
        <div className="form-grid">
          <label>
            Method
            <select
              value={f.method}
              onChange={(e) => set("method", e.target.value)}
            >
              <option value="bank_letter">Letter received from the bank</option>
              <option value="bank_email">Email from the bank's domain</option>
              <option value="bank_portal">Bank portal</option>
              <option value="phone_callback">Call-back to the bank</option>
            </select>
          </label>
          <label>
            Observed at
            <input
              type="datetime-local"
              max={now}
              value={f.observed_at}
              onChange={(e) => set("observed_at", e.target.value)}
            />
          </label>
        </div>
        <label>
          Evidence note
          <input
            value={f.note}
            maxLength={500}
            onChange={(e) => set("note", e.target.value)}
          />
        </label>
        {error && <Notice message={error} />}
        <div className="dialog-actions">
          <button
            className="primary"
            disabled={busy || !f.bank_transaction_ref || !f.source || !f.note}
            onClick={save}
          >
            Record execution evidence
          </button>
        </div>
      </fieldset>
    </details>
  );
}
