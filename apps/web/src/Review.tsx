import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  Landmark,
  Repeat2,
  FlaskConical,
  ChevronRight,
  FileText,
  Fingerprint,
  Inbox,
  MessageSquareWarning,
  Plus,
  Scale,
} from "lucide-react";
import { api, day, money } from "./api";
import { MyAuthority } from "./Access";
import { ReleaseCard, ReleaseDecisions } from "./Release";
import { Overview } from "./Dashboard";
import type {
  BankExchange,
  CaseField,
  Coverage,
  Instrument,
  ReplacementView,
  Comparison,
  Discrepancy,
  Evidence,
  Me,
  ReviewCase,
  ReviewItem,
} from "./types";
import {
  DeadlinesPanel,
  Dialog,
  Notice,
  Recovery,
  Timeline,
  documentBadge,
  fileSize,
  kindLabels,
  refreshedSession,
} from "./ui";

const fields: Record<CaseField, string> = {
  bank_name: "Bank name",
  bank_reference: "FDR reference",
  principal_amount: "Principal amount",
  issue_date: "Issue date",
  maturity_date: "Maturity date",
};
const manualMethods = {
  bank_portal: "Bank portal (verified login)",
  bank_email: "Email from the bank's official domain",
  bank_letter: "Letter received directly from the bank",
  phone_callback: "Call-back to an independently sourced bank number",
};
const methods: Record<Evidence["method"], string> = {
  ...manualMethods,
  bank_simulator: "SIMULATED bank answer (synthetic)",
};
const outcomes: Record<BankExchange["outcome"], string> = {
  pending: "Awaiting answer",
  confirmed: "Answered · values recorded as simulated evidence",
  not_found: "No deposit with this reference",
  timeout: "No answer in time · fields stay unconfirmed",
  rejected: "Answer rejected",
  stale: "Answer ignored · case changed after request",
};
const results: Record<Comparison["status"], string> = {
  match: "Match",
  mismatch: "Mismatch",
  unconfirmed: "Not yet confirmed",
};
function shown(field: CaseField, value: string | null) {
  if (value === null) return "—";
  if (field === "principal_amount") return money(value);
  if (field.endsWith("_date")) return day(value);
  return value;
}

async function post<T>(me: Me, path: string, body: unknown) {
  const current = await refreshedSession(me);
  return api<T>(
    path,
    { method: "POST", body: JSON.stringify(body) },
    current.csrf_token,
  );
}

export function Thread({
  item,
  me,
  onChange,
}: {
  item: Discrepancy;
  me: Me;
  onChange: () => void;
}) {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canReply =
    item.status === "open" &&
    (me.role === "reviewer" || me.role === "institution_user");
  async function send(resolve: boolean) {
    setBusy(true);
    setError("");
    try {
      await post(me, `/api/v1/discrepancies/${item.id}/replies`, {
        message,
        resolve,
      });
      setMessage("");
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <li className={`thread ${item.status}`}>
      <div className="thread-head">
        <strong>{item.label}</strong>
        <span className={`badge obs-${item.status}`}>
          <span />
          {item.status === "open" ? "Open" : "Resolved"}
        </span>
      </div>
      <p>{item.message}</p>
      <small>
        {item.raised_by} · {new Date(item.created_at).toLocaleString("en-IN")}
      </small>
      {item.replies.map((r) => (
        <div key={r.id} className={`reply ${r.kind}`}>
          <p>{r.message}</p>
          <small>
            {r.kind === "resolution" ? "Resolved by " : ""}
            {r.author} · {new Date(r.created_at).toLocaleString("en-IN")}
          </small>
        </div>
      ))}
      {canReply && (
        <div className="reply-form">
          <label>
            {me.role === "reviewer" ? "Reply or resolve" : "Your response"}
            <textarea
              value={message}
              maxLength={1000}
              rows={2}
              disabled={busy}
              onChange={(e) => setMessage(e.target.value)}
            />
          </label>
          {error && (
            <>
              <Notice message={error} />
              <Recovery />
            </>
          )}
          <div className="dialog-actions">
            {me.role === "reviewer" && (
              <button
                className="secondary"
                disabled={busy || !message.trim()}
                onClick={() => send(true)}
              >
                Resolve
              </button>
            )}
            <button
              className="primary"
              disabled={busy || !message.trim()}
              onClick={() => send(false)}
            >
              {busy ? "Sending…" : "Send reply"}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

export function Observations({ id, me }: { id: string; me: Me }) {
  const [items, setItems] = useState<Discrepancy[]>([]);
  const [error, setError] = useState("");
  const load = () =>
    api<{ items: Discrepancy[] }>(`/api/v1/instruments/${id}/discrepancies`)
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, [id]);
  if (!items.length && !error) return null;
  return (
    <section className="panel documents">
      <div className="section-title">
        <MessageSquareWarning size={19} />
        <h2>Reviewer observations</h2>
      </div>
      <p className="muted small">
        Questions from the AICTE reviewer. Your responses are kept with the case
        history.
      </p>
      {error && <Notice message={error} />}
      <ul className="threads">
        {items.map((d) => (
          <Thread key={d.id} item={d} me={me} onChange={load} />
        ))}
      </ul>
    </section>
  );
}

function EvidenceForm({
  data,
  me,
  onClose,
  onSaved,
}: {
  data: ReviewCase;
  me: Me;
  onClose: () => void;
  onSaved: () => void;
}) {
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
  const [form, setForm] = useState({
    field: "bank_reference" as CaseField,
    value: "",
    source: "",
    method: "bank_portal" as Evidence["method"],
    observed_at: now,
    note: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof form, value: string) =>
    setForm((old) => ({ ...old, [key]: value }));
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post(me, `/api/v1/reviews/${data.instrument_id}/evidence`, {
        ...form,
        observed_at: new Date(form.observed_at).toISOString(),
      });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const dateField = form.field.endsWith("_date");
  return (
    <Dialog title="Record independent evidence" onClose={onClose}>
      <p className="dialog-intro">
        Record what the bank confirmed through a channel you reached
        independently. Documents uploaded by the institution are claims, not
        confirmation.
      </p>
      <form onSubmit={save}>
        <fieldset disabled={busy}>
          <div className="form-grid">
            <label>
              Field
              <select
                value={form.field}
                onChange={(e) => {
                  set("field", e.target.value);
                  set("value", "");
                }}
              >
                {Object.entries(fields).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Value confirmed by the bank
              <input
                required
                type={dateField ? "date" : "text"}
                inputMode={
                  form.field === "principal_amount" ? "decimal" : undefined
                }
                maxLength={120}
                value={form.value}
                placeholder={
                  form.field === "principal_amount" ? "500000.00" : ""
                }
                onChange={(e) => set("value", e.target.value)}
              />
            </label>
          </div>
          <p className="claim-hint">
            Institution claimed:{" "}
            <strong>{shown(form.field, data.claim[form.field])}</strong>
          </p>
          <label>
            Method
            <select
              value={form.method}
              onChange={(e) => set("method", e.target.value)}
            >
              {Object.entries(manualMethods).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <div className="form-grid">
            <label>
              Source (bank, branch or contact)
              <input
                required
                maxLength={200}
                value={form.source}
                placeholder="e.g. Demo National Bank, Fort branch"
                onChange={(e) => set("source", e.target.value)}
              />
            </label>
            <label>
              Observed at
              <input
                required
                type="datetime-local"
                max={now}
                value={form.observed_at}
                onChange={(e) => set("observed_at", e.target.value)}
              />
            </label>
          </div>
          <label>
            Note (optional)
            <textarea
              rows={2}
              maxLength={500}
              value={form.note}
              onChange={(e) => set("note", e.target.value)}
            />
          </label>
        </fieldset>
        {error && (
          <>
            <Notice message={error} />
            <Recovery />
          </>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Saving…" : "Record evidence"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function ObservationForm({
  data,
  me,
  onClose,
  onSaved,
}: {
  data: ReviewCase;
  me: Me;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [field, setField] = useState<CaseField | "">("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post(me, `/api/v1/reviews/${data.instrument_id}/discrepancies`, {
        field: field || null,
        message,
      });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Raise an observation" onClose={onClose}>
      <p className="dialog-intro">
        The institution sees this and can respond. Only you can resolve it.
      </p>
      <form onSubmit={save}>
        <fieldset disabled={busy}>
          <label>
            Concerning
            <select
              value={field}
              onChange={(e) => setField(e.target.value as CaseField | "")}
            >
              <option value="">General</option>
              {Object.entries(fields).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Observation
            <textarea
              required
              rows={4}
              maxLength={1000}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </label>
        </fieldset>
        {error && (
          <>
            <Notice message={error} />
            <Recovery />
          </>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button className="primary" disabled={busy || !message.trim()}>
            {busy ? "Saving…" : "Raise observation"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function BankSimulator({
  data,
  me,
  onChange,
}: {
  data: ReviewCase;
  me: Me;
  onChange: () => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function ask() {
    setBusy(true);
    setError("");
    try {
      await post(me, `/api/v1/reviews/${data.instrument_id}/bank-requests`, {});
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel documents simulator">
      <span className="simulator-label">SIMULATED BANK · NOT A REAL BANK</span>
      <div className="section-title">
        <FlaskConical size={19} />
        <h2>Bank confirmation simulator</h2>
      </div>
      <p className="muted small">
        Synthetic responses for demonstration. No bank is contacted, and
        simulated answers never count as confirmation. Each answer is signed and
        accepted only for this request and case version.
      </p>
      {error && <Notice message={error} />}
      {data.bank_requests.length > 0 && (
        <ul className="evidence-log">
          {data.bank_requests.map((r) => (
            <li key={r.id}>
              <strong>{outcomes[r.outcome]}</strong>
              {r.detail && <span>{r.detail}</span>}
              <small>
                Requested {new Date(r.requested_at).toLocaleString("en-IN")}
              </small>
            </li>
          ))}
        </ul>
      )}
      <div className="simulator-actions">
        <button className="secondary" disabled={busy} onClick={ask}>
          <FlaskConical size={16} />
          {busy ? "Asking simulator…" : "Request simulated confirmation"}
        </button>
        <small>
          Scenarios: an FDR reference ending in -MISMATCH, -NOTFOUND, -TIMEOUT,
          -TAMPER or -REPLAY triggers that response.
        </small>
      </div>
    </section>
  );
}

function CaseView({
  id,
  me,
  onBack,
}: {
  id: string;
  me: Me;
  onBack: () => void;
}) {
  const [data, setData] = useState<ReviewCase | null>(null);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"" | "evidence" | "observation">("");
  const load = () =>
    api<ReviewCase>(`/api/v1/reviews/${id}`)
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, [id]);
  const saved = () => {
    setDialog("");
    void load();
  };
  const submitted = new Set(data?.submitted_documents.map((d) => d.id));
  return (
    <>
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} />
        Back to review queue
      </button>
      {error && <Notice message={error} />}
      {!data ? (
        !error && <p role="status">Loading case…</p>
      ) : (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">CASE REVIEW</p>
              <h1>{data.claim.bank_reference}</h1>
              <p className="muted">
                {data.institution.name} <span className="dot">·</span> Submitted{" "}
                {new Date(data.submitted_at).toLocaleDateString("en-IN")}
              </p>
            </div>
            {data.status === "closed" ? (
              <span className="badge closed">
                <span />
                Closed
              </span>
            ) : (
              <div className="heading-actions">
                <button
                  className="secondary"
                  onClick={() => setDialog("observation")}
                >
                  <MessageSquareWarning size={16} />
                  Raise observation
                </button>
                <button
                  className="primary"
                  onClick={() => setDialog("evidence")}
                >
                  <Plus size={16} />
                  Record evidence
                </button>
              </div>
            )}
          </div>
          <div className="detail-grid">
            <section className="panel">
              <div className="section-title">
                <Scale size={19} />
                <h2>Claim and independent evidence</h2>
              </div>
              <p className="muted small">
                Each field is compared by fixed rules with the latest evidence
                recorded for it.
              </p>
              <div className="table-wrap">
                <table className="compare">
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Institution claim</th>
                      <th>From institution document</th>
                      <th>Independent evidence</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.comparison.map((row) => (
                      <tr key={row.field}>
                        <td>{row.label}</td>
                        <td>{shown(row.field, row.claimed)}</td>
                        <td>
                          {row.extracted
                            ? shown(row.field, row.extracted)
                            : "—"}
                          {row.extracted_differs && (
                            <span className="differs">
                              {" "}
                              · differs from claim
                            </span>
                          )}
                        </td>
                        <td>{shown(row.field, row.confirmed)}</td>
                        <td>
                          <span className={`badge cmp-${row.status}`}>
                            <span />
                            {results[row.status]}
                            {row.simulated ? " · simulated" : ""}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3 className="subhead">Evidence log</h3>
              {data.evidence.length ? (
                <ul className="evidence-log">
                  {data.evidence.map((e) => (
                    <li key={e.id}>
                      <strong>
                        {e.label}: {shown(e.field, e.value)}
                      </strong>
                      <span>
                        {methods[e.method]} · {e.source}
                      </span>
                      <small>
                        Observed by {e.observer} on{" "}
                        {new Date(e.observed_at).toLocaleString("en-IN")}
                      </small>
                      {e.note && <small>{e.note}</small>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="doc-empty">
                  No independent evidence recorded yet.
                </p>
              )}
            </section>
            <section className="panel">
              <div className="section-title">
                <Fingerprint size={19} />
                <h2>Audit trail</h2>
              </div>
              <Timeline items={data.audit} />
            </section>
          </div>
          <DeadlinesPanel data={data.deadlines} />
          <ReplacementPanel
            view={data.replacement}
            coverage={data.coverage}
            me={me}
            focusId={data.instrument_id}
            onChange={load}
          />
          {data.status !== "closed" && (
            <BankSimulator data={data} me={me} onChange={load} />
          )}
          {data.releases.length > 0 && (
            <section className="panel documents">
              <div className="section-title">
                <Landmark size={19} />
                <h2>Release requests</h2>
              </div>
              {data.releases.map((r) => (
                <ReleaseCard
                  key={r.id}
                  req={r}
                  me={me}
                  canReview
                  canDecide={false}
                  onChange={load}
                />
              ))}
            </section>
          )}
          <section className="panel documents">
            <div className="section-title">
              <MessageSquareWarning size={19} />
              <h2>Observations</h2>
            </div>
            {data.discrepancies.length ? (
              <ul className="threads">
                {data.discrepancies.map((d) => (
                  <Thread key={d.id} item={d} me={me} onChange={load} />
                ))}
              </ul>
            ) : (
              <p className="doc-empty">No observations raised.</p>
            )}
          </section>
          <section className="panel documents">
            <div className="section-title">
              <FileText size={19} />
              <h2>Institution documents</h2>
            </div>
            <p className="muted small">
              Supporting claims from the institution. Only clean files can be
              downloaded.
            </p>
            <ul className="doc-list">
              {data.documents.map((d) => (
                <li key={d.id} className={d.current ? "" : "replaced"}>
                  <FileText size={18} />
                  <div>
                    <strong>{d.filename}</strong>
                    <small>
                      {kindLabels[d.kind]}
                      {submitted.has(d.id) ? " · in submission" : ""}
                      {d.current ? "" : " · replaced"} ·{" "}
                      {fileSize(d.size_bytes)}
                    </small>
                  </div>
                  <span className={`badge doc-${documentBadge(d)[0]}`}>
                    <span />
                    {documentBadge(d)[1]}
                  </span>
                  {d.scan_status === "clean" && (
                    <a
                      className="text-button"
                      href={`/api/v1/documents/${d.id}/download`}
                      download
                      aria-label={`Download ${d.filename}`}
                    >
                      Download
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </section>
          {dialog === "evidence" && (
            <EvidenceForm
              data={data}
              me={me}
              onClose={() => setDialog("")}
              onSaved={saved}
            />
          )}
          {dialog === "observation" && (
            <ObservationForm
              data={data}
              me={me}
              onClose={() => setDialog("")}
              onSaved={saved}
            />
          )}
        </>
      )}
    </>
  );
}

export function ReviewWorkspace({ me }: { me: Me }) {
  const [queue, setQueue] = useState<ReviewItem[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) return;
    setError("");
    api<{ items: ReviewItem[] }>("/api/v1/reviews")
      .then((r) => setQueue(r.items))
      .catch((e) => setError(e.message));
  }, [open]);
  if (open)
    return (
      <CaseView key={open} id={open} me={me} onBack={() => setOpen(null)} />
    );
  const items = queue || [];
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">REVIEW QUEUE</p>
          <h1>Cases awaiting review</h1>
          <p className="muted">
            Submitted FDRs from institutions you hold review authority for,
            oldest first.
          </p>
        </div>
      </div>
      <MyAuthority me={me} />
      <ReleaseDecisions me={me} />
      <Overview me={me} onOpen={setOpen} />
      <section className="panel register">
        <div className="register-heading">
          <div>
            <h2>Submitted cases</h2>
            <p className="muted small">
              Claims stay unverified until you record independent evidence.
            </p>
          </div>
        </div>
        {error && <Notice message={error} />}
        {queue === null ? (
          !error && (
            <p role="status" className="loading-status">
              Loading cases…
            </p>
          )
        ) : items.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>FDR reference / institution</th>
                  <th>Claimed amount</th>
                  <th>Submitted</th>
                  <th>Evidence</th>
                  <th>Observations</th>
                  <th>
                    <span className="sr-only">Open case</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((q) => (
                  <tr key={q.instrument_id}>
                    <td>
                      <button
                        className="record-link"
                        onClick={() => setOpen(q.instrument_id)}
                      >
                        {q.bank_reference}
                      </button>
                      <span className="bank-name">
                        {q.institution.name} · {q.bank_name}
                      </span>
                    </td>
                    <td className="numeric">{money(q.principal_amount)}</td>
                    <td>
                      {new Date(q.submitted_at).toLocaleDateString("en-IN")}
                    </td>
                    <td>
                      {q.confirmed_fields} of 5 confirmed
                      {q.mismatched_fields
                        ? ` · ${q.mismatched_fields} mismatch`
                        : ""}
                      {q.simulated_fields
                        ? ` · ${q.simulated_fields} simulated`
                        : ""}
                    </td>
                    <td>
                      {q.open_discrepancies
                        ? `${q.open_discrepancies} open`
                        : "None open"}
                      {q.escalated && (
                        <span className="badge cmp-mismatch escalated">
                          <span />
                          Escalated
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`Open case ${q.bank_reference}`}
                        onClick={() => setOpen(q.instrument_id)}
                      >
                        <ChevronRight size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">
            <div className="empty-symbol">
              <Inbox size={33} />
            </div>
            <h3>No cases waiting</h3>
            <p>Submitted FDRs from your assigned institutions appear here.</p>
          </div>
        )}
      </section>
    </>
  );
}

const coverageStates = {
  counting: "Counts as cover",
  superseded: "Replaced",
  proposed_successor: "Proposed replacement · not yet cover",
};
const linkStatus = {
  proposed: "Proposed · awaiting reviewer",
  accepted: "Accepted",
  rejected: "Rejected",
};

export function ReplacementPanel({
  view,
  coverage,
  me,
  item,
  focusId,
  onChange,
}: {
  view: ReplacementView;
  coverage: Coverage | null;
  me: Me;
  item?: Instrument;
  focusId: string;
  onChange: () => void;
}) {
  const [choice, setChoice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function act(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      await post(me, path, body);
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const out = view.outgoing;
  const related = new Set([
    focusId,
    out?.successor_id,
    view.incoming?.predecessor_id,
  ]);
  const chain = coverage?.instruments.filter((i) => related.has(i.id)) ?? [];
  const canPropose =
    item?.status === "submitted" && me.role === "institution_user" && !out;
  return (
    <section className="panel documents">
      <div className="section-title">
        <Repeat2 size={19} />
        <h2>Replacement and coverage</h2>
      </div>
      {error && <Notice message={error} />}
      {out && (
        <p className="link-line">
          Replaced by <strong>{out.successor_reference}</strong> ·{" "}
          {linkStatus[out.status]}
          {out.decided_by && ` by ${out.decided_by}`}
        </p>
      )}
      {view.incoming && (
        <p className="link-line">
          Replaces <strong>{view.incoming.predecessor_reference}</strong> ·{" "}
          {linkStatus[view.incoming.status]}
        </p>
      )}
      {out?.status === "proposed" && me.role === "reviewer" && (
        <div className="simulator-actions">
          <button
            className="secondary"
            disabled={busy}
            onClick={() =>
              act(`/api/v1/replacements/${out.id}/decision`, { accept: false })
            }
          >
            Reject replacement
          </button>
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              act(`/api/v1/replacements/${out.id}/decision`, { accept: true })
            }
          >
            Accept replacement
          </button>
        </div>
      )}
      {canPropose &&
        (view.candidates?.length ? (
          <div className="upload-row">
            <label>
              Renewed or replacement FDR
              <select
                value={choice}
                disabled={busy}
                onChange={(e) => setChoice(e.target.value)}
              >
                <option value="">Choose a submitted FDR…</option>
                {view.candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.bank_reference} · {money(c.principal_amount)} · matures{" "}
                    {day(c.maturity_date)}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="secondary"
              disabled={busy || !choice}
              onClick={() =>
                act(`/api/v1/instruments/${item!.id}/replacement`, {
                  successor_id: choice,
                })
              }
            >
              Propose as replacement
            </button>
          </div>
        ) : (
          <p className="doc-empty">
            To renew, submit the new FDR first. It must cover the same
            obligation, mature later and be for at least the same amount.
          </p>
        ))}
      {coverage && (
        <>
          <dl className="facts deadline-dates">
            <div>
              <dt>Required for {coverage.title}</dt>
              <dd>{money(coverage.required_amount)}</dd>
            </div>
            <div>
              <dt>Counted cover</dt>
              <dd>{money(coverage.covered_amount)}</dd>
            </div>
            <div>
              <dt>Gap</dt>
              <dd>{money(coverage.gap_amount)}</dd>
            </div>
          </dl>
          {coverage.proposed_amount !== "0.00" && (
            <p className="doc-empty">
              {money(coverage.proposed_amount)} more is proposed as replacement
              and is not counted until a reviewer accepts it.
            </p>
          )}
          <ul className="doc-list chain">
            {chain.map((i) => (
              <li
                key={i.id}
                className={i.state === "counting" ? "" : "replaced"}
              >
                <div>
                  <strong>{i.bank_reference}</strong>
                  <small>
                    {money(i.principal_amount)} · matures {day(i.maturity_date)}
                  </small>
                </div>
                <span className={`badge cov-${i.state}`}>
                  <span />
                  {coverageStates[i.state]}
                </span>
              </li>
            ))}
          </ul>
          <details className="all-cover">
            <summary>
              All {coverage.instruments.length} submitted FDRs for this
              obligation
            </summary>
            <ul className="doc-list">
              {coverage.instruments.map((i) => (
                <li
                  key={i.id}
                  className={i.state === "counting" ? "" : "replaced"}
                >
                  <div>
                    <strong>{i.bank_reference}</strong>
                    <small>
                      {money(i.principal_amount)} · matures{" "}
                      {day(i.maturity_date)}
                    </small>
                  </div>
                  <span className={`badge cov-${i.state}`}>
                    <span />
                    {coverageStates[i.state]}
                  </span>
                </li>
              ))}
            </ul>
          </details>
          <p className="muted small">{coverage.basis}</p>
        </>
      )}
    </section>
  );
}
