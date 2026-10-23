import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { BookCheck, KeyRound, ShieldCheck, UserCheck } from "lucide-react";
import { api } from "./api";
import type { Grant, Me, PolicyVersion } from "./types";
import { Notice, refreshedSession } from "./ui";

const authorities = {
  review: "Case review",
  release_approve: "Release approval · sensitive",
};
const statuses: Record<Grant["status"], string> = {
  pending: "Awaiting second administrator",
  active: "Active",
  rejected: "Rejected",
  revoked: "Revoked",
  expired: "Expired",
};
const inMonths = (n: number) =>
  new Date(Date.now() + n * 30 * 86400000).toISOString().slice(0, 10);

async function send(me: Me, path: string, body: unknown) {
  const current = await refreshedSession(me);
  return api<Grant>(
    path,
    { method: "POST", body: JSON.stringify(body) },
    current.csrf_token,
  );
}

function GrantRow({ g, actions }: { g: Grant; actions?: ReactNode }) {
  return (
    <li className="grant">
      <div>
        <strong>
          {g.user} · {authorities[g.authority]}
        </strong>
        <span>
          {g.institution.name} ·{" "}
          {g.valid_until
            ? `until ${new Date(g.valid_until).toLocaleDateString("en-IN")}`
            : "no end date"}
          {g.delegated_from ? " · delegated" : ""}
        </span>
        <small>
          Requested by {g.requested_by || "migration"}
          {g.approved_by ? ` · approved by ${g.approved_by}` : ""}
          {g.revoked_by ? ` · revoked by ${g.revoked_by}` : ""} · {g.reason}
        </small>
      </div>
      <span className={`badge grant-${g.effective ? "active" : g.status}`}>
        <span />
        {g.status === "active" && !g.effective ? "Expired" : statuses[g.status]}
      </span>
      {actions}
    </li>
  );
}

export function AccessWorkspace({ me }: { me: Me }) {
  const [grants, setGrants] = useState<Grant[]>([]);
  const [people, setPeople] = useState<
    { id: string; name: string; role: string; organisation: string }[]
  >([]);
  const [institutions, setInstitutions] = useState<
    { id: string; name: string }[]
  >([]);
  const [form, setForm] = useState({
    user_id: "",
    authority: "review",
    institution_id: "",
    valid_until: inMonths(6),
    reason: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    api<{ items: Grant[] }>("/api/v1/admin/grants")
      .then((r) => setGrants(r.items))
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
    api<{
      users: typeof people;
      institutions: typeof institutions;
    }>("/api/v1/admin/users")
      .then((r) => {
        setPeople(r.users);
        setInstitutions(r.institutions);
      })
      .catch((e) => setError(e.message));
  }, []);
  async function act(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      await send(me, path, body);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function create(e: FormEvent) {
    e.preventDefault();
    await act("/api/v1/admin/grants", {
      ...form,
      valid_until: new Date(form.valid_until + "T23:59:00+05:30").toISOString(),
    });
    setForm((f) => ({ ...f, reason: "" }));
  }
  const reviewers = people.filter((p) => p.role === "reviewer");
  const pending = grants.filter((g) => g.status === "pending");
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ACCESS MANAGEMENT</p>
          <h1>Authority and delegation</h1>
          <p className="muted">
            Scoped, time-limited authority. Release approval needs a second
            administrator; nobody can grant authority to themselves.
          </p>
        </div>
      </div>
      {error && <Notice message={error} />}
      <section className="panel documents">
        <div className="section-title">
          <UserCheck size={19} />
          <h2>Awaiting approval</h2>
        </div>
        {pending.length ? (
          <ul className="grants">
            {pending.map((g) => (
              <GrantRow
                key={g.id}
                g={g}
                actions={
                  g.requested_by === me.display_name ? (
                    <span className="row-actions">
                      <small className="hint">
                        Another administrator must approve
                      </small>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          act(`/api/v1/admin/grants/${g.id}/reject`, {
                            reason: "Withdrawn by requester",
                          })
                        }
                      >
                        Withdraw
                      </button>
                    </span>
                  ) : (
                    <span className="row-actions">
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          act(`/api/v1/admin/grants/${g.id}/reject`, {
                            reason: "Not approved",
                          })
                        }
                      >
                        Reject
                      </button>
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() =>
                          act(`/api/v1/admin/grants/${g.id}/approve`, {})
                        }
                      >
                        Approve
                      </button>
                    </span>
                  )
                }
              />
            ))}
          </ul>
        ) : (
          <p className="doc-empty">Nothing is waiting for approval.</p>
        )}
      </section>
      <Policies me={me} />
      <section className="panel documents">
        <div className="section-title">
          <KeyRound size={19} />
          <h2>Grant authority</h2>
        </div>
        <form onSubmit={create}>
          <fieldset disabled={busy}>
            <div className="form-grid">
              <label>
                Reviewer
                <select
                  required
                  value={form.user_id}
                  onChange={(e) =>
                    setForm({ ...form, user_id: e.target.value })
                  }
                >
                  <option value="">Choose…</option>
                  {reviewers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Authority
                <select
                  value={form.authority}
                  onChange={(e) =>
                    setForm({ ...form, authority: e.target.value })
                  }
                >
                  {Object.entries(authorities).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="form-grid">
              <label>
                Institution
                <select
                  required
                  value={form.institution_id}
                  onChange={(e) =>
                    setForm({ ...form, institution_id: e.target.value })
                  }
                >
                  <option value="">Choose…</option>
                  {institutions.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Valid until
                <input
                  type="date"
                  required
                  min={inMonths(0)}
                  max={inMonths(12)}
                  value={form.valid_until}
                  onChange={(e) =>
                    setForm({ ...form, valid_until: e.target.value })
                  }
                />
              </label>
            </div>
            <label>
              Reason
              <input
                required
                minLength={3}
                maxLength={300}
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
              />
            </label>
          </fieldset>
          <div className="dialog-actions">
            <button className="primary" disabled={busy}>
              {form.authority === "release_approve"
                ? "Request (needs second approval)"
                : "Grant authority"}
            </button>
          </div>
        </form>
      </section>
      <section className="panel documents">
        <div className="section-title">
          <ShieldCheck size={19} />
          <h2>All grants</h2>
        </div>
        <ul className="grants">
          {grants.map((g) => (
            <GrantRow
              key={g.id}
              g={g}
              actions={
                g.effective && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      act(`/api/v1/admin/grants/${g.id}/revoke`, {
                        reason: "Revoked by administrator",
                      })
                    }
                  >
                    Revoke
                  </button>
                )
              }
            />
          ))}
        </ul>
      </section>
    </>
  );
}

export function MyAuthority({ me }: { me: Me }) {
  const [held, setHeld] = useState<Grant[]>([]);
  const [given, setGiven] = useState<Grant[]>([]);
  const [delegates, setDelegates] = useState<{ id: string; name: string }[]>(
    [],
  );
  const [target, setTarget] = useState("");
  const [until, setUntil] = useState(inMonths(1));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    api<{ held: Grant[]; delegated: Grant[] }>("/api/v1/grants/mine")
      .then((r) => {
        setHeld(r.held);
        setGiven(r.delegated);
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
    api<{ items: typeof delegates }>("/api/v1/grants/delegates")
      .then((r) => setDelegates(r.items))
      .catch(() => undefined);
  }, []);
  async function act(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      await send(me, path, body);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="panel documents my-authority">
      <summary>
        <KeyRound size={17} /> My authority (
        {held.filter((g) => g.effective).length} active)
      </summary>
      {error && <Notice message={error} />}
      <ul className="grants">
        {held.map((g) => (
          <GrantRow
            key={g.id}
            g={g}
            actions={
              g.effective &&
              !g.delegated_from && (
                <span className="row-actions">
                  <select
                    aria-label={`Delegate ${authorities[g.authority]} to`}
                    value={target}
                    onChange={(e) => setTarget(e.target.value)}
                  >
                    <option value="">Delegate to…</option>
                    {delegates.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="date"
                    aria-label="Delegate until"
                    value={until}
                    onChange={(e) => setUntil(e.target.value)}
                  />
                  <button
                    className="secondary"
                    disabled={busy || !target}
                    onClick={() =>
                      act(`/api/v1/grants/${g.id}/delegate`, {
                        user_id: target,
                        valid_until: new Date(
                          until + "T23:59:00+05:30",
                        ).toISOString(),
                        reason: "Delegated cover",
                      })
                    }
                  >
                    Delegate
                  </button>
                </span>
              )
            }
          />
        ))}
      </ul>
      {given.length > 0 && (
        <>
          <h3 className="subhead">Delegated by me</h3>
          <ul className="grants">
            {given.map((g) => (
              <GrantRow
                key={g.id}
                g={g}
                actions={
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      act(`/api/v1/grants/${g.id}/revoke`, {
                        reason: "Delegation ended",
                      })
                    }
                  >
                    End delegation
                  </button>
                }
              />
            ))}
          </ul>
        </>
      )}
    </details>
  );
}

export const clearanceLabels: Record<string, string> = {
  no_dues_certificate: "No-dues certificate",
  closure_approval_letter: "Closure or approval letter",
  bank_lien_release: "Bank lien release",
  audit_confirmation: "Audit confirmation",
};

function Policies({ me }: { me: Me }) {
  const [items, setItems] = useState<PolicyVersion[]>([]);
  const [clearances, setClearances] = useState<string[]>([
    "no_dues_certificate",
  ]);
  const [notBefore, setNotBefore] = useState("obligation_end");
  const [from, setFrom] = useState(inMonths(1));
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    api<{ items: PolicyVersion[] }>("/api/v1/admin/policies")
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, []);
  async function act(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      await send(me, path, body);
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
        <BookCheck size={19} />
        <h2>Release policy versions</h2>
      </div>
      <p className="muted small">
        Published versions are immutable; a change is a new version with its own
        effective date. A different administrator must publish each draft.
      </p>
      {error && <Notice message={error} />}
      <ul className="grants">
        {items.map((p) => (
          <li key={p.id} className="grant">
            <div>
              <strong>
                Release policy v{p.version} ·{" "}
                {p.applies_to === "*" ? "all obligations" : p.applies_to}
              </strong>
              <span>
                From {p.effective_from}
                {p.effective_until ? ` until ${p.effective_until}` : ""} ·
                clearances:{" "}
                {p.rules.clearances.map((c) => clearanceLabels[c]).join(", ")} ·
                release{" "}
                {p.rules.release_not_before === "obligation_end"
                  ? "only after the obligation ends"
                  : "at any time"}
              </span>
              <span>{p.note}</span>
              <small>
                Drafted by {p.drafted_by}
                {p.published_by
                  ? ` · published by ${p.published_by}`
                  : ""} ·{" "}
                {p.owner_validated
                  ? "validated by policy owner"
                  : "illustrative · not validated by the policy owner"}
              </small>
            </div>
            <span
              className={`badge grant-${p.status === "published" ? "active" : "pending"}`}
            >
              <span />
              {p.status === "published" ? "Published" : "Draft"}
            </span>
            {p.status === "draft" &&
              (p.drafted_by === me.display_name ? (
                <small className="hint">
                  Another administrator must publish
                </small>
              ) : (
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    act(`/api/v1/admin/policies/${p.id}/publish`, {})
                  }
                >
                  Publish
                </button>
              ))}
          </li>
        ))}
      </ul>
      <details className="all-cover">
        <summary>Draft a new version</summary>
        <fieldset disabled={busy} className="policy-form">
          <legend className="sr-only">Required clearances</legend>
          {Object.entries(clearanceLabels).map(([value, label]) => (
            <label key={value} className="check">
              <input
                type="checkbox"
                checked={clearances.includes(value)}
                onChange={(e) =>
                  setClearances((old) =>
                    e.target.checked
                      ? [...old, value]
                      : old.filter((c) => c !== value),
                  )
                }
              />
              {label}
            </label>
          ))}
          <div className="form-grid">
            <label>
              Release allowed
              <select
                value={notBefore}
                onChange={(e) => setNotBefore(e.target.value)}
              >
                <option value="obligation_end">
                  Only after the obligation ends
                </option>
                <option value="any_time">At any time with clearances</option>
              </select>
            </label>
            <label>
              Effective from
              <input
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              />
            </label>
          </div>
          <label>
            Note
            <input
              value={note}
              maxLength={300}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <div className="dialog-actions">
            <button
              className="secondary"
              disabled={busy || !clearances.length || note.trim().length < 3}
              onClick={() =>
                act("/api/v1/admin/policies", {
                  code: "release",
                  applies_to: "*",
                  effective_from: from,
                  rules: { clearances, release_not_before: notBefore },
                  note,
                })
              }
            >
              Save draft version
            </button>
          </div>
        </fieldset>
      </details>
    </section>
  );
}
