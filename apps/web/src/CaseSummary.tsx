import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { CaseSummaryView, ReviewCase } from "./types";

export function CaseSummary({
  id,
  source,
  refresh,
}: {
  id: string;
  source: ReviewCase["summary_state"] | null;
  refresh: () => void;
}) {
  const [snapshot, setSnapshot] = useState<CaseSummaryView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef<AbortController | null>(null);
  useEffect(() => () => generation.current?.abort(), [id]);
  const basis = snapshot?.basis_sha256;
  const status = snapshot?.status;
  const enabled = source?.enabled;
  const sourceBasis = source?.basis_sha256;

  useEffect(() => {
    if (!enabled || !sourceBasis || !basis || busy || status !== "current")
      return;
    const controller = new AbortController();
    let pending = false;
    async function validate() {
      if (pending || controller.signal.aborted) return;
      pending = true;
      const timeout = window.setTimeout(() => {
        if (!controller.signal.aborted) {
          setSnapshot(null);
          setError(
            "Summary hidden: revalidation timed out. Try generating again.",
          );
          controller.abort();
        }
      }, 10000);
      try {
        const result = await api<CaseSummaryView>(
          `/api/v1/reviews/${id}/summary?basis_sha256=${basis}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          if (result.status !== "current") setSnapshot(result);
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setSnapshot(null);
          setError(`Summary hidden: ${(e as Error).message}`);
        }
      } finally {
        window.clearTimeout(timeout);
        pending = false;
      }
    }
    const timer = window.setInterval(() => void validate(), 15000);
    window.addEventListener("focus", validate);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", validate);
    };
  }, [id, enabled, sourceBasis, basis, busy, status]);

  async function generate() {
    generation.current?.abort();
    const controller = new AbortController();
    generation.current = controller;
    setBusy(true);
    setError("");
    try {
      const result = await api<CaseSummaryView>(
        `/api/v1/reviews/${id}/summary`,
        {
          signal: controller.signal,
        },
      );
      if (!controller.signal.aborted) {
        setSnapshot(result);
        refresh(); // Reload the cited panels, including changes made in another session.
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        setSnapshot(null);
        setError(`Summary hidden: ${(e as Error).message}`);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  if (!source) return null; // Hide facts while loading or when case access fails.
  const disabled = !source.enabled || snapshot?.status === "disabled";
  const stale =
    snapshot &&
    (snapshot.status === "stale" ||
      snapshot.basis_sha256 !== source.basis_sha256);
  return (
    <section className="panel case-summary" aria-label="Case summary">
      <div className="section-title">
        <h2>Case summary</h2>
      </div>
      <p className="muted small">
        Local rule-based summary · Advisory only; never approval evidence.
      </p>
      {disabled ? (
        <p>
          Case summaries are disabled. Manual case review remains available.
        </p>
      ) : (
        <>
          {error && <p role="alert">{error}</p>}
          {stale && (
            <p role="status">
              Summary stale — case facts have changed. Regenerate before
              reading.
            </p>
          )}
          <button
            className="secondary"
            disabled={busy}
            onClick={() => void generate()}
          >
            {busy
              ? "Generating summary…"
              : snapshot
                ? "Regenerate summary"
                : "Generate case summary"}
          </button>
          {snapshot && !stale && !busy && (
            <>
              <p className="muted small">
                Revalidated every 15 seconds and on window focus. Regenerate to
                refresh sources.
              </p>
              <div className="summary-sections">
                {snapshot.sections.map((section, index) => (
                  <article key={index}>
                    <h3>{section.title}</h3>
                    <p className="small muted">{section.text}</p>
                    <dl>
                      {Object.entries(section.facts).map(([label, value]) => (
                        <div key={label}>
                          <dt>{label}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                    {section.citations.length > 0 && (
                      <details>
                        <summary>Sources and versions</summary>
                        <ul>
                          {section.citations.map((citation, i) => (
                            <li key={i}>
                              <a href={citation.href}>
                                {citation.kind} · {citation.id}
                              </a>
                              {citation.sha256 && (
                                <small>SHA-256: {citation.sha256}</small>
                              )}
                              {citation.object_version && (
                                <small>
                                  Object version: {citation.object_version}
                                </small>
                              )}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </article>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
