import type { ExplanationView } from "./types";

export function Explanations({
  data,
  refresh,
}: {
  data: ExplanationView;
  refresh: () => void;
}) {
  if (!data.enabled) return null;
  return (
    <details className="panel documents explanations">
      <summary>Source-linked explanations</summary>
      <p className="muted small">
        Rule-based fallback. Code determines differences; no AI model is used.
        These explanations do not verify a bank instrument, resolve an
        observation or authorize release.
      </p>
      <button type="button" className="secondary" onClick={refresh}>
        Refresh sources
      </button>
      <ul className="evidence-log">
        {data.items.map((row) => (
          <li key={row.field}>
            <strong>
              {row.label}
              {row.simulated ? " · simulated" : ""}
            </strong>
            <p>{row.text}</p>
            <span>
              Submitted: {row.claimed} ·{" "}
              {row.simulated ? "Simulated" : "Recorded evidence"}:{" "}
              {row.evidence_value ?? "Not recorded"}
            </span>
            {row.document_value !== null && (
              <span>Institution document proposal: {row.document_value}</span>
            )}
            <details>
              <summary>Sources and versions</summary>
              {row.citations.map((source) => (
                <div
                  key={`${source.kind}-${source.id}`}
                  className="explanation-source"
                >
                  <a href={source.href}>
                    {source.kind === "submission"
                      ? "Submission"
                      : source.kind === "evidence"
                        ? "Evidence"
                        : "Institution document"}{" "}
                    {source.id.slice(0, 8)}
                  </a>
                  {source.kind === "extraction" && (
                    <small>
                      Page {source.page} ({source.x}, {source.y}) ·{" "}
                      {source.extractor} · run {source.run_id} · object version{" "}
                      {source.object_version} · SHA-256 {source.sha256}
                    </small>
                  )}
                </div>
              ))}
            </details>
          </li>
        ))}
      </ul>
      <small className="muted">
        Source basis: {data.basis_sha256}. Recomputed when this case is
        refreshed.
      </small>
    </details>
  );
}
