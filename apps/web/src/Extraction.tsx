import { useState } from "react";
import { api, day, money } from "./api";
import type { DocumentFile, Draft } from "./types";
import { Notice } from "./ui";

type Field = {
  field: keyof Draft;
  status: "proposed" | "abstained";
  value: string | null;
  reason: string;
  page: number | null;
  snippet: string;
};
type Run = {
  status: "pending" | "completed" | "manual_required" | "failed";
  extractor: string;
  error?: string;
  fields: Field[];
};
const labels: Record<string, string> = {
  bank_reference: "FDR reference",
  principal_amount: "Principal amount",
  issue_date: "Issue date",
  maturity_date: "Maturity date",
  bank_name: "Bank name",
};
function shown(f: Field) {
  if (!f.value) return "";
  if (f.field === "principal_amount") return money(f.value);
  if (f.field.endsWith("_date")) return day(f.value);
  return f.value;
}

export function DocumentValues({
  doc,
  canUse,
  onUse,
}: {
  doc: DocumentFile;
  canUse: boolean;
  onUse: (values: Partial<Draft>) => void;
}) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");
  async function load() {
    if (run && run.status !== "pending") return;
    try {
      setRun(await api<Run>(`/api/v1/documents/${doc.id}/extraction`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const proposed = run?.fields.filter((f) => f.status === "proposed") ?? [];
  return (
    <details
      className="doc-values"
      onToggle={(e) => e.currentTarget.open && load()}
    >
      <summary>Read values from document</summary>
      {error && <Notice message={error} />}
      {run?.status === "pending" && (
        <p className="doc-empty">Reading the document… reopen in a moment.</p>
      )}
      {run?.status === "failed" && (
        <p className="doc-empty">The document could not be read: {run.error}</p>
      )}
      {run && run.fields.length > 0 && (
        <ul className="requirements">
          {run.fields.map((f) => (
            <li key={f.field} className={f.status === "proposed" ? "met" : ""}>
              <span>
                <strong>{labels[f.field]}</strong>
                {f.status === "proposed"
                  ? ` · ${shown(f)} (page ${f.page}: “${f.snippet}”)`
                  : ` · not read: ${f.reason}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {run && run.status !== "pending" && (
        <p className="muted small">
          Read by fixed rules ({run.extractor}). These are suggestions from your
          own document, not bank confirmation; nothing changes until you save.
        </p>
      )}
      {canUse && proposed.length > 0 && (
        <button
          className="secondary"
          onClick={() =>
            onUse(Object.fromEntries(proposed.map((f) => [f.field, f.value])))
          }
        >
          Review these values in the edit form
        </button>
      )}
    </details>
  );
}
