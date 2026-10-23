import { useEffect, useState } from "react";
import { Gavel, Landmark } from "lucide-react";
import { api } from "./api";
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
  const hasActions =
    (canReview && (open || (s === "approved" && !req.approval_valid))) ||
    (canDecide && s === "open") ||
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
