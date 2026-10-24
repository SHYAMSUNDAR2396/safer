import { useEffect, useState } from "react";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { api, day, money } from "./api";
import type { Coverage } from "./types";
import { Dialog, Notice } from "./ui";

type Metric = {
  key: string;
  group: string;
  label: string;
  grain: string;
  count: number;
  amount: string;
};
type DashboardData = {
  metrics: Metric[];
  coverage: Omit<Coverage, "instruments">[];
};
type Drill = {
  key: string;
  label: string;
  grain: string;
  items: {
    id: string;
    bank_reference: string;
    bank_name: string;
    institution: string;
    principal_amount: string;
    maturity_date: string;
    status: string;
  }[];
};
const attention = new Set([
  "matured_uncovered",
  "action_overdue",
  "escalated",
  "open_observations",
]);

function CoverMeter({ c }: { c: DashboardData["coverage"][number] }) {
  const required = Number(c.required_amount);
  const covered = Number(c.covered_amount);
  const ratio = required ? Math.min(covered / required, 1) : 1;
  const short = Number(c.gap_amount) > 0;
  return (
    <div className="cover-meter">
      <div className="cover-head">
        <strong>{c.title}</strong>
        <span>
          {money(c.covered_amount)} of {money(c.required_amount)} counted
          {short ? ` · gap ${money(c.gap_amount)}` : " · fully covered"}
        </span>
      </div>
      <div
        className={`meter ${short ? "short" : "full"}`}
        role="meter"
        aria-label={`Counted cover for ${c.title}`}
        aria-valuemin={0}
        aria-valuemax={required}
        aria-valuenow={covered}
        aria-valuetext={`${Math.round(ratio * 100)} percent of required cover`}
      >
        <span style={{ width: `${ratio * 100}%` }} />
      </div>
      {c.proposed_amount !== "0.00" && (
        <small>
          {money(c.proposed_amount)} more proposed as replacement, not yet
          counted.
        </small>
      )}
    </div>
  );
}

export function Overview({ onOpen }: { onOpen: (id: string) => void }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [drill, setDrill] = useState<Drill | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<DashboardData>("/api/v1/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  async function open(key: string) {
    setError("");
    try {
      setDrill(await api<Drill>(`/api/v1/dashboard/${key}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!data) return error ? <Notice message={error} /> : null;
  const groups = [...new Set(data.metrics.map((m) => m.group))];
  return (
    <section className="overview" aria-label="Overview">
      {error && <Notice message={error} />}
      {groups.map((g) => (
        <div key={g} className="metric-group">
          <h2 className="subhead">{g}</h2>
          <div className="metric-row">
            {data.metrics
              .filter((m) => m.group === g)
              .map((m) => {
                const flagged = attention.has(m.key) && m.count > 0;
                return (
                  <button
                    key={m.key}
                    className={`metric${flagged ? " flagged" : ""}`}
                    onClick={() => open(m.key)}
                    aria-label={`${m.label}: ${m.count} FDRs, ${money(m.amount)}. Show list`}
                  >
                    <span className="metric-label">
                      {flagged && <AlertTriangle size={14} aria-hidden />}
                      {m.label}
                    </span>
                    <strong>{m.count}</strong>
                    <small>{money(m.amount)}</small>
                  </button>
                );
              })}
          </div>
        </div>
      ))}
      {data.coverage.length > 0 && (
        <div className="metric-group">
          <h2 className="subhead">Counted cover by obligation</h2>
          {data.coverage.map((c) => (
            <CoverMeter key={c.obligation_id} c={c} />
          ))}
        </div>
      )}
      <p className="muted small">
        {data.metrics[0]?.grain} Cover counts submitted claims, not
        independently confirmed deposits.
      </p>
      {drill && (
        <Dialog title={drill.label} onClose={() => setDrill(null)}>
          <p className="dialog-intro">
            {drill.items.length} FDRs · {drill.grain}
          </p>
          {drill.items.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>FDR reference</th>
                    <th>Institution</th>
                    <th>Principal</th>
                    <th>Maturity</th>
                    <th>
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {drill.items.map((i) => (
                    <tr key={i.id}>
                      <td>
                        {i.bank_reference}
                        <span className="bank-name">{i.bank_name}</span>
                      </td>
                      <td>{i.institution}</td>
                      <td className="numeric">{money(i.principal_amount)}</td>
                      <td>{day(i.maturity_date)}</td>
                      <td>
                        <button
                          className="icon-button"
                          aria-label={`Open ${i.bank_reference}`}
                          onClick={() => {
                            setDrill(null);
                            onOpen(i.id);
                          }}
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
            <p className="doc-empty">Nothing here.</p>
          )}
        </Dialog>
      )}
    </section>
  );
}
