import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileCheck2,
  FilePlus2,
  FileText,
  Files,
  Fingerprint,
  Landmark,
  LockKeyhole,
  LogOut,
  Plus,
  Paperclip,
  Search,
  ShieldAlert,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { api, ApiError, day, money } from "./api";
import type {
  AuditEvent,
  DocumentFile,
  DocumentKind,
  Draft,
  Instrument,
  Me,
  Obligation,
  Register,
  Coverage,
  Deadlines,
  ReplacementView,
  Requirement,
} from "./types";
import "./styles.css";
import { Observations, ReplacementPanel, ReviewWorkspace } from "./Review";
import { AccessWorkspace } from "./Access";
import { InstitutionRelease } from "./Release";
import {
  events,
  documentStatus,
  scanStatus,
  documentBadge,
  kindLabels,
  MAX_UPLOAD,
  fileSize,
  Notice,
  refreshedSession,
  Recovery,
  Badge,
  DeadlinesPanel,
  Dialog,
  Inbox,
  Timeline,
} from "./ui";

function InstrumentForm({
  item,
  obligations,
  me,
  onClose,
  onSaved,
}: {
  item?: Instrument;
  obligations: Obligation[];
  me: Me;
  onClose: () => void;
  onSaved: (i: Instrument) => void;
}) {
  const [data, setData] = useState<Draft>(
    item
      ? {
          obligation_id: item.obligation_id,
          bank_name: item.bank_name,
          bank_reference: item.bank_reference,
          principal_amount: item.principal_amount,
          currency: "INR",
          issue_date: item.issue_date,
          maturity_date: item.maturity_date,
        }
      : {
          obligation_id: obligations[0]?.id || "",
          bank_name: "",
          bank_reference: "",
          principal_amount: "",
          currency: "INR",
          issue_date: "",
          maturity_date: "",
        },
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const change = (key: keyof Draft, value: string) =>
    setData((old) => ({ ...old, [key]: value }));
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const current = await refreshedSession(me);
      const result = await api<Instrument>(
        `/api/v1/instruments${item ? "/" + item.id : ""}`,
        {
          method: item ? "PATCH" : "POST",
          body: JSON.stringify(data),
          headers: item ? { "If-Match": `"${item.row_version}"` } : {},
        },
        current.csrf_token,
      );
      onSaved(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={item ? "Edit FDR draft" : "Add a new FDR"}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <p className="dialog-intro">
        Record the instrument details. You can review them before submitting.
      </p>
      <form onSubmit={save}>
        <fieldset disabled={busy}>
          <label>
            Approval obligation
            <select
              value={data.obligation_id}
              required
              onChange={(e) => change("obligation_id", e.target.value)}
            >
              {obligations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Bank name
            <input
              autoFocus
              value={data.bank_name}
              required
              maxLength={120}
              placeholder="e.g. Demo National Bank"
              onChange={(e) => change("bank_name", e.target.value)}
            />
          </label>
          <div className="form-grid">
            <label>
              FDR reference
              <input
                value={data.bank_reference}
                required
                maxLength={100}
                placeholder="Keep leading zeros"
                onChange={(e) => change("bank_reference", e.target.value)}
              />
            </label>
            <label>
              Principal amount (INR)
              <input
                value={data.principal_amount}
                required
                inputMode="decimal"
                pattern="(0|[1-9][0-9]{0,15})(\.[0-9]{1,2})?"
                placeholder="500000.00"
                onChange={(e) => change("principal_amount", e.target.value)}
              />
            </label>
          </div>
          <div className="form-grid">
            <label>
              Issue date
              <input
                type="date"
                value={data.issue_date}
                required
                onChange={(e) => change("issue_date", e.target.value)}
              />
            </label>
            <label>
              Maturity date
              <input
                type="date"
                value={data.maturity_date}
                required
                min={data.issue_date || undefined}
                onChange={(e) => change("maturity_date", e.target.value)}
              />
            </label>
          </div>
        </fieldset>
        {error && (
          <>
            <Notice message={error} />
            <Recovery />
          </>
        )}
        <div className="form-note">
          <LockKeyhole size={16} />
          <span>
            Saved only to {me.institution.name}. Use synthetic information.
          </span>
        </div>
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button className="primary" disabled={busy || !obligations.length}>
            {busy ? "Saving…" : item ? "Save changes" : "Save draft"}
            <ArrowRight size={17} />
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function Documents({
  item,
  me,
  onUploaded,
  onRequirements,
}: {
  item: Instrument;
  me: Me;
  onUploaded: () => void;
  onRequirements: (missing: string[]) => void;
}) {
  const [docs, setDocs] = useState<DocumentFile[] | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [kind, setKind] = useState<DocumentKind>("fdr_certificate");
  const suggested = useRef(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    api<{ items: DocumentFile[]; requirements: Requirement[] }>(
      `/api/v1/instruments/${item.id}/documents`,
    )
      .then((r) => {
        setDocs(r.items);
        setRequirements(r.requirements);
        onRequirements(
          r.requirements.filter((q) => !q.satisfied).map((q) => q.label),
        );
        // Suggest the first missing type once; later polls keep the user's choice.
        const next = r.requirements.find((q) => !q.document_id);
        if (next && !suggested.current) setKind(next.kind);
        suggested.current = true;
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, [item.id]);
  const scanning = !!docs?.some((d) => d.scan_status === "pending");
  const wasScanning = useRef(false);
  useEffect(() => {
    // Poll while the scanner works; refresh the audit trail once results land.
    if (wasScanning.current && !scanning) onUploaded();
    wasScanning.current = scanning;
    if (!scanning) return;
    const timer = setTimeout(load, 3000);
    return () => clearTimeout(timer);
  }, [docs]);
  async function upload(input: HTMLInputElement) {
    const file = input.files?.[0];
    if (!file) return;
    setError("");
    if (file.size > MAX_UPLOAD) {
      setError("Files must be 10 MB or smaller.");
      input.value = "";
      return;
    }
    setBusy(true);
    try {
      const current = await refreshedSession(me);
      await api(
        `/api/v1/instruments/${item.id}/documents?` +
          new URLSearchParams({ filename: file.name, kind }),
        {
          method: "POST",
          body: file,
          headers: { "Content-Type": file.type || "application/octet-stream" },
        },
        current.csrf_token,
      );
      onUploaded();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      await load();
      setBusy(false);
      input.value = "";
    }
  }
  const canUpload = item.status === "draft" && me.role === "institution_user";
  return (
    <section className="panel documents">
      <div className="section-title">
        <Paperclip size={19} />
        <h2>Supporting documents</h2>
      </div>
      <p className="muted small">
        PDF, JPEG or PNG · up to 10 MB · PDFs up to 30 pages, unencrypted.
      </p>
      {requirements.length > 0 && (
        <ul className="requirements" aria-label="Required before submission">
          {requirements.map((q) => (
            <li key={q.kind} className={q.satisfied ? "met" : ""}>
              {q.satisfied ? <Check size={14} /> : <Clock3 size={14} />}
              <span>
                <strong>{q.label}</strong>
                {q.satisfied
                  ? " · uploaded and scanned clean"
                  : q.document_id
                    ? " · current upload is not clean yet"
                    : " · required before submission"}
              </span>
            </li>
          ))}
        </ul>
      )}
      {error && <Notice message={error} />}
      {docs === null ? (
        <p role="status" className="doc-empty">
          Loading documents…
        </p>
      ) : docs.length ? (
        <ul className="doc-list">
          {docs.map((d) => (
            <li key={d.id} className={d.current ? "" : "replaced"}>
              <FileText size={18} />
              <div>
                <strong>{d.filename}</strong>
                <small>
                  {kindLabels[d.kind]}
                  {d.current ? "" : " · replaced by a newer upload"}
                </small>
                <small>
                  {d.media_type === "application/pdf"
                    ? `PDF · ${d.page_count} page${d.page_count === 1 ? "" : "s"}`
                    : d.media_type === "image/png"
                      ? "PNG image"
                      : "JPEG image"}{" "}
                  · {fileSize(d.size_bytes)}
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
                  onClick={() => setTimeout(onUploaded, 1000)}
                >
                  Download
                </a>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="doc-empty">No documents uploaded yet.</p>
      )}
      {canUpload && (
        <div className="upload-row">
          <label>
            Document type
            <select
              value={kind}
              disabled={busy}
              onChange={(e) => setKind(e.target.value as DocumentKind)}
            >
              {Object.entries(kindLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className={`secondary upload-button${busy ? " busy" : ""}`}>
            <Upload size={16} />
            {busy ? "Checking and uploading…" : "Upload document"}
            <input
              type="file"
              className="sr-only"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              disabled={busy}
              onChange={(e) => upload(e.currentTarget)}
            />
          </label>
        </div>
      )}
      <div className="info-note">
        <ShieldAlert size={18} />
        <p>
          Files stay quarantined until an isolated malware scan clears the exact
          stored version; only clean files can be downloaded, never previewed in
          the portal. A document is a claim, not bank confirmation.
        </p>
      </div>
    </section>
  );
}

function Details({
  item,
  me,
  onBack,
  onEdit,
  onSubmitted,
}: {
  item: Instrument;
  me: Me;
  onBack: () => void;
  onEdit: () => void;
  onSubmitted: (i: Instrument) => void;
}) {
  const [timeline, setTimeline] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uploads, setUploads] = useState(0);
  const [missing, setMissing] = useState<string[] | null>(null);
  const [deadlines, setDeadlines] = useState<Deadlines | null>(null);
  const [replacement, setReplacement] = useState<ReplacementView | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [links, setLinks] = useState(0);
  useEffect(() => {
    api<Deadlines>(`/api/v1/instruments/${item.id}/deadlines`)
      .then(setDeadlines)
      .catch(() => setDeadlines(null));
    api<ReplacementView>(`/api/v1/instruments/${item.id}/replacement`)
      .then(setReplacement)
      .catch(() => setReplacement(null));
    api<Coverage>(`/api/v1/obligations/${item.obligation_id}/coverage`)
      .then(setCoverage)
      .catch(() => setCoverage(null));
  }, [item.id, item.row_version, links]);
  const key = useRef(crypto.randomUUID());
  useEffect(() => {
    let active = true;
    setError("");
    api<{ items: AuditEvent[] }>(`/api/v1/instruments/${item.id}/audit`)
      .then((r) => {
        if (active) setTimeline(r.items);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [item.id, item.row_version, uploads]);
  async function submit() {
    setBusy(true);
    setError("");
    try {
      const current = await refreshedSession(me);
      await api(
        `/api/v1/instruments/${item.id}/submissions`,
        {
          method: "POST",
          body: "{}",
          headers: {
            "If-Match": `"${item.row_version}"`,
            "Idempotency-Key": key.current,
          },
        },
        current.csrf_token,
      );
      const updated = await api<Instrument>(`/api/v1/instruments/${item.id}`);
      setConfirm(false);
      onSubmitted(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} />
        Back to register
      </button>
      <div className="page-heading">
        <div>
          <p className="eyebrow">INSTRUMENT DETAILS</p>
          <h1>{item.bank_reference}</h1>
          <p className="muted">
            {item.bank_name} <span className="dot">·</span> Version{" "}
            {item.row_version}
          </p>
        </div>
        <Badge status={item.status} />
      </div>
      {error && !confirm && <Notice message={error} />}
      <div className="detail-grid">
        <section className="panel">
          <div className="section-title">
            <Landmark size={19} />
            <h2>Deposit information</h2>
          </div>
          <dl className="facts">
            <div>
              <dt>Principal amount</dt>
              <dd className="amount">{money(item.principal_amount)}</dd>
            </div>
            <div>
              <dt>Evidence status</dt>
              <dd>
                <span className="unverified">Not bank verified</span>
              </dd>
            </div>
            <div>
              <dt>Issue date</dt>
              <dd>{day(item.issue_date)}</dd>
            </div>
            <div>
              <dt>Maturity date</dt>
              <dd>{day(item.maturity_date)}</dd>
            </div>
            <div>
              <dt>Currency</dt>
              <dd>Indian rupee · INR</dd>
            </div>
            <div>
              <dt>Recorded on</dt>
              <dd>{new Date(item.created_at).toLocaleDateString("en-IN")}</dd>
            </div>
          </dl>
          <div className="info-note">
            <CircleHelp size={18} />
            <p>
              Submission covers metadata only. Documents open only after a clean
              malware scan; independent bank verification and regulatory
              approval are later milestones.
            </p>
          </div>
          {item.status === "draft" && me.role === "institution_user" && (
            <div className="record-actions">
              <button className="secondary" onClick={onEdit}>
                Edit draft
              </button>
              <button
                className="primary"
                disabled={missing === null || missing.length > 0}
                onClick={() => setConfirm(true)}
              >
                Submit metadata
                <ArrowRight size={16} />
              </button>
            </div>
          )}
          {item.status === "draft" && !!missing?.length && (
            <p className="submit-hint" role="status">
              Before submitting, upload and wait for a clean scan of:{" "}
              {missing.join(", ")}.
            </p>
          )}
          {item.status === "submitted" && (
            <div className="submitted-note">
              <Check size={18} />A submission snapshot has been preserved. This
              record is read-only.
            </div>
          )}
        </section>
        <section className="panel">
          <div className="section-title">
            <Fingerprint size={19} />
            <h2>Audit trail</h2>
          </div>
          <p className="muted small">A traceable history of this record.</p>
          <Timeline items={timeline} />
        </section>
      </div>
      <Documents
        item={item}
        me={me}
        onUploaded={() => setUploads((n) => n + 1)}
        onRequirements={setMissing}
      />
      {deadlines && <DeadlinesPanel data={deadlines} />}
      {replacement && item.status === "submitted" && (
        <ReplacementPanel
          view={replacement}
          coverage={coverage}
          me={me}
          item={item}
          focusId={item.id}
          onChange={() => {
            setLinks((n) => n + 1);
            setUploads((n) => n + 1);
          }}
        />
      )}
      {item.status === "submitted" && <Observations id={item.id} me={me} />}
      {item.status === "submitted" && (
        <InstitutionRelease id={item.id} me={me} />
      )}
      {confirm && (
        <Dialog
          title="Submit this metadata?"
          onClose={() => {
            if (!busy) setConfirm(false);
          }}
        >
          <p className="dialog-intro">
            The current details will become a read-only snapshot. This is a
            synthetic demonstration, not a verified regulatory submission.
          </p>
          <div className="confirm-summary">
            <strong>{item.bank_reference}</strong>
            <span>{money(item.principal_amount)}</span>
          </div>
          {error && (
            <>
              <Notice message={error} />
              <Recovery />
            </>
          )}
          <div className="dialog-actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              Keep draft
            </button>
            <button className="primary" disabled={busy} onClick={submit}>
              {busy ? "Submitting…" : "Confirm submission"}
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [error, setError] = useState("");
  const [register, setRegister] = useState<Register | null>(null);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [selected, setSelected] = useState<Instrument | null>(null);
  const [form, setForm] = useState<false | "new" | "edit">(false);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [guide, setGuide] = useState(false);
  useEffect(() => {
    api<Me>("/api/v1/me")
      .then(setMe)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) setMe(null);
        else setError(e.message);
      });
  }, []);
  async function load(cursor?: string) {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ q: query });
      if (cursor) params.set("cursor", cursor);
      const data = await api<Register>("/api/v1/instruments?" + params);
      setRegister((old) =>
        cursor && old
          ? { ...data, items: [...old.items, ...data.items] }
          : data,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (me && me.role !== "reviewer" && me.role !== "admin") {
      void load();
      api<{ items: Obligation[] }>("/api/v1/obligations")
        .then((r) => setObligations(r.items))
        .catch((e) => setError(e.message));
    }
  }, [me, query]);
  async function signout() {
    try {
      const current = await refreshedSession(me!);
      await api("/auth/logout", { method: "POST" }, current.csrf_token);
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) {
        setError((e as Error).message);
        return;
      }
    }
    setMe(null);
    setRegister(null);
    setSelected(null);
    setForm(false);
    setError("");
  }
  async function open(id: string) {
    setError("");
    try {
      setSelected(await api<Instrument>("/api/v1/instruments/" + id));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function saved(item: Instrument) {
    setForm(false);
    setSelected(item);
    void load();
  }
  const brand = (
    <div className="brand">
      <span className="brand-symbol">
        <ShieldCheck size={27} />
      </span>
      <span>
        SAFER<small>Institutional deposit management</small>
      </span>
    </div>
  );
  if (me === undefined)
    return (
      <main className="boot">
        {brand}
        <p role="status">Connecting to your workspace…</p>
        {error && (
          <>
            <Notice message={error} />
            <button className="secondary" onClick={() => location.reload()}>
              Retry connection
            </button>
          </>
        )}
      </main>
    );
  if (me === null)
    return (
      <main className="login-screen">
        <section className="login-story">
          {brand}
          <div>
            <p className="eyebrow">ONE REGISTER. A CLEARER RECORD.</p>
            <h1>
              Every deposit accounted for.
              <br />
              <em>Every action traceable.</em>
            </h1>
            <p>Secure Administration of FDRs through Electronic Review.</p>
            <div className="login-features">
              <span>
                <Files />
                Institution-scoped records
              </span>
              <span>
                <Fingerprint />
                Traceable submission history
              </span>
              <span>
                <LockKeyhole />
                Controlled access
              </span>
            </div>
          </div>
          <small>SIH 2026 · Problem Statement 26265</small>
        </section>
        <section className="login-side">
          <span className="demo-label">SYNTHETIC DEMONSTRATION</span>
          <div className="login-card">
            <div className="login-icon">
              <Building2 size={30} />
            </div>
            <h2>Your institutional workspace</h2>
            <p>
              Sign in with a provisioned account to manage your institution’s
              FDR records.
            </p>
            <a className="primary" href="/auth/login">
              Sign in securely
              <ArrowRight size={18} />
            </a>
            <div className="login-note">
              <ShieldCheck size={17} />
              <span>
                Access is limited to your assigned institution and role.
              </span>
            </div>
          </div>
          <p className="login-footer">
            Prototype only. No live bank integration or real financial
            transactions.
          </p>
        </section>
      </main>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        {brand}
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          <button
            className="nav-item active"
            onClick={() => {
              setSelected(null);
              setQuery("");
              setSearch("");
            }}
          >
            <Files size={19} />
            {me.role === "reviewer"
              ? "Review queue"
              : me.role === "admin"
                ? "Access management"
                : "Deposit register"}
            <ChevronRight size={16} />
          </button>
          <button className="nav-item" onClick={() => setGuide(true)}>
            <CircleHelp size={19} />
            Demo guide
          </button>
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={22} />
          <strong>Evidence before decisions</strong>
          <p>
            Submitted details remain unverified until independently confirmed.
          </p>
        </div>
        <div className="sidebar-footer">
          SAFER <span>v1.1 · Release decisions</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span className="workspace-title">
            <Building2 size={17} />
            {me.institution.name}
          </span>
          <div className="account">
            <Inbox me={me} />
            <span className="avatar">{me.display_name[0]}</span>
            <div>
              <strong>{me.display_name}</strong>
              <small>
                {me.role === "auditor"
                  ? "Read-only access"
                  : me.role === "reviewer"
                    ? "AICTE reviewer"
                    : me.role === "admin"
                      ? "Access administrator"
                      : "Institution officer"}
              </small>
            </div>
            <button
              className="icon-button"
              aria-label="Sign out"
              title="Sign out"
              onClick={signout}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <div className="demo-banner">
          <span className="demo-dot" />
          <strong>SIH prototype</strong>
          <span>
            Synthetic data only · Metadata submission · No bank verification
          </span>
        </div>
        <main className="main" id="main-content">
          {selected && error && <Notice message={error} />}{" "}
          {me.role === "admin" ? (
            <AccessWorkspace me={me} />
          ) : me.role === "reviewer" ? (
            <ReviewWorkspace me={me} />
          ) : selected ? (
            <Details
              key={selected.id}
              item={selected}
              me={me}
              onBack={() => setSelected(null)}
              onEdit={() => setForm("edit")}
              onSubmitted={saved}
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">INSTITUTION OVERVIEW</p>
                  <h1>Your deposit register</h1>
                  <p className="muted">
                    Manage your FDR records with a clear, accountable history.
                  </p>
                </div>
                {me.role === "institution_user" && (
                  <button
                    className="primary"
                    onClick={() => setForm("new")}
                    disabled={!obligations.length}
                  >
                    <Plus size={18} />
                    New FDR
                  </button>
                )}
              </div>
              <div className="stats">
                <div className="stat">
                  <span>
                    Total records
                    <Files size={17} />
                  </span>
                  <strong>{register?.summary.total ?? "—"}</strong>
                  <small>Within your institution</small>
                </div>
                <div className="stat">
                  <span>
                    Recorded principal
                    <Landmark size={17} />
                  </span>
                  <strong className="money-stat">
                    {register ? money(register.summary.recorded_amount) : "—"}
                  </strong>
                  <small>Includes drafts · Not verified coverage</small>
                </div>
                <div className="stat">
                  <span>
                    Drafts
                    <Clock3 size={17} />
                  </span>
                  <strong>{register?.summary.drafts ?? "—"}</strong>
                  <small>Ready for your review</small>
                </div>
                <div className="stat">
                  <span>
                    Submitted metadata
                    <FileCheck2 size={17} />
                  </span>
                  <strong>{register?.summary.submitted ?? "—"}</strong>
                  <small>Read-only snapshots preserved</small>
                </div>
              </div>
              <section className="panel register">
                <div className="register-heading">
                  <div>
                    <h2>FDR records</h2>
                    <p className="muted small">
                      Your institution’s instruments, in one place.
                    </p>
                  </div>
                  <form
                    className="search"
                    onSubmit={(e) => {
                      e.preventDefault();
                      setQuery(search);
                    }}
                  >
                    <Search size={17} />
                    <input
                      aria-label="Search FDR records"
                      placeholder="Search bank or reference"
                      value={search}
                      maxLength={100}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                    <button type="submit">Search</button>
                  </form>
                </div>
                {error && <Notice message={error} />}
                <div role="status" className="loading-status">
                  {loading ? "Loading records…" : ""}
                </div>
                {register?.items.length ? (
                  <>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>FDR reference / bank</th>
                            <th>Principal amount</th>
                            <th>Maturity date</th>
                            <th>Status</th>
                            <th>
                              <span className="sr-only">Open record</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {register.items.map((item) => (
                            <tr key={item.id}>
                              <td>
                                <button
                                  className="record-link"
                                  onClick={() => open(item.id)}
                                >
                                  {item.bank_reference}
                                </button>
                                <span className="bank-name">
                                  {item.bank_name}
                                </span>
                              </td>
                              <td className="numeric">
                                {money(item.principal_amount)}
                              </td>
                              <td>{day(item.maturity_date)}</td>
                              <td>
                                <Badge status={item.status} />
                              </td>
                              <td>
                                <button
                                  className="icon-button"
                                  aria-label={`Open ${item.bank_reference}`}
                                  onClick={() => open(item.id)}
                                >
                                  <ChevronRight size={18} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="table-footer">
                      <span>{register.items.length} records shown</span>
                      {register.next_cursor && (
                        <button
                          className="secondary"
                          disabled={loading}
                          onClick={() => load(register.next_cursor!)}
                        >
                          Load more
                        </button>
                      )}
                      <span>
                        <LockKeyhole size={13} />
                        Institution-scoped access
                      </span>
                    </div>
                  </>
                ) : (
                  !loading &&
                  register && (
                    <div className="empty">
                      <div className="empty-symbol">
                        <FilePlus2 size={33} />
                      </div>
                      <h3>
                        {query
                          ? "No matching records"
                          : "A clear record starts here"}
                      </h3>
                      <p>
                        {query
                          ? "Try a different bank name or FDR reference."
                          : "Add your first synthetic FDR to create a traceable deposit record."}
                      </p>
                      {!query && me.role === "institution_user" && (
                        <button
                          className="text-button"
                          onClick={() => setForm("new")}
                          disabled={!obligations.length}
                        >
                          Create your first draft
                          <ArrowRight size={16} />
                        </button>
                      )}
                    </div>
                  )
                )}
              </section>
              <p className="bottom-note">
                <ShieldCheck size={15} />
                Each saved change is recorded in the audit trail. Submission
                does not establish bank authenticity.
              </p>
            </>
          )}
        </main>
        <footer className="footer">
          SAFER · Secure Administration of FDRs through Electronic Review
          <span>SIH 2026 / PS26265</span>
        </footer>
      </div>
      {form && (
        <InstrumentForm
          item={form === "edit" && selected ? selected : undefined}
          obligations={obligations}
          me={me}
          onClose={() => setForm(false)}
          onSaved={saved}
        />
      )}
      {guide && (
        <Dialog
          title="About this demonstration"
          onClose={() => setGuide(false)}
        >
          <div className="guide">
            <p>
              This prototype supports sign-in, institution-scoped drafts,
              malware-scanned document upload and download, metadata submission
              and an audit trail.
            </p>
            <p>
              <strong>Next milestones:</strong> durable background jobs,
              maturity alerts, renewal, release approvals and AI assistance.
            </p>
            <p>
              Use synthetic data only. Amounts and policies shown in the demo
              are illustrative. The portal does not move money.
            </p>
            <button className="primary" onClick={() => setGuide(false)}>
              Got it
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
