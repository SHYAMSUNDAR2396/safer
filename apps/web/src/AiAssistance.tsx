import { useEffect, useRef, useState } from "react";
import { api } from "./api";

type Purpose = "summary" | "explanations";
type AiView = {
  enabled: boolean;
  purpose: Purpose;
  basis_sha256: string;
  case_basis_sha256: string;
  mode: "llm" | "deterministic_fallback";
  reason: string | null;
  model: string | null;
  blocks: {
    id: string;
    title: string;
    text: string;
    ai_text?: string;
    facts: Record<string, string | null>;
    citations: { kind: string; id: string; href: string }[];
  }[];
};

const reasons: Record<string, string> = {
  disabled: "AI is switched off.",
  feature_disabled: "This assistance feature is switched off.",
  egress_not_approved: "External processing is not approved.",
  source_not_approved:
    "These exact synthetic sources are not approved for external processing.",
  configuration_unavailable: "The provider configuration is unavailable.",
  provider_unavailable: "The provider could not answer.",
  input_too_large: "This case exceeds the bounded AI input size.",
  invalid_output: "The provider response did not pass validation.",
  budget_exhausted: "The configured AI allowance has been reached.",
  rate_limited: "The AI request limit has been reached.",
  busy: "Another AI request is running. Try again later.",
};

export function AiAssistance({
  id,
  csrf,
  source,
  refresh,
}: {
  id: string;
  csrf: string;
  source: { enabled: boolean; basis_sha256: string } | null;
  refresh: () => void;
}) {
  const [snapshot, setSnapshot] = useState<AiView | null>(null);
  const [busy, setBusy] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef<AbortController | null>(null);
  useEffect(() => () => generation.current?.abort(), [id]);
  const sourceBasis = source?.basis_sha256;
  const basis = snapshot?.basis_sha256;
  const purpose = snapshot?.purpose;
  const mode = snapshot?.mode;

  useEffect(() => {
    if (!sourceBasis || !basis || !purpose || busy) return;
    const controller = new AbortController();
    let pending = false;
    async function validate() {
      if (pending || controller.signal.aborted) return;
      pending = true;
      setValidating(true);
      const timeout = window.setTimeout(() => {
        controller.abort();
        setSnapshot(null);
        setError("AI draft hidden: source revalidation timed out.");
        setValidating(false);
      }, 10000);
      try {
        const current = await api<AiView>(
          `/api/v1/reviews/${id}/ai?purpose=${purpose}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          if (
            current.basis_sha256 !== basis ||
            (mode === "llm" && current.reason)
          ) {
            setSnapshot(null);
            setError(
              "AI draft hidden: sources or processing permission changed. Generate again.",
            );
          }
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setSnapshot(null);
          setError(`AI draft hidden: ${(e as Error).message}`);
        }
      } finally {
        window.clearTimeout(timeout);
        pending = false;
        if (!controller.signal.aborted) setValidating(false);
      }
    }
    const timer = window.setInterval(() => void validate(), 15000);
    window.addEventListener("focus", validate);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", validate);
    };
  }, [id, sourceBasis, basis, purpose, mode, busy]);

  async function generate(selected: Purpose) {
    generation.current?.abort();
    const controller = new AbortController();
    generation.current = controller;
    setBusy(true);
    setValidating(false);
    setSnapshot(null);
    setError("");
    const timeout = window.setTimeout(() => {
      controller.abort();
      setError(
        "AI request timed out. Local source-linked review remains available.",
      );
      setBusy(false);
    }, 35000);
    try {
      const current = await api<AiView>(
        `/api/v1/reviews/${id}/ai?purpose=${selected}`,
        { signal: controller.signal },
      );
      const result = await api<AiView>(
        `/api/v1/reviews/${id}/ai`,
        {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            purpose: selected,
            basis_sha256: current.basis_sha256,
          }),
        },
        csrf,
      );
      if (!controller.signal.aborted) {
        setSnapshot(result);
        refresh();
      }
    } catch (e) {
      if (!controller.signal.aborted)
        setError(`AI draft hidden: ${(e as Error).message}`);
    } finally {
      window.clearTimeout(timeout);
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  if (!source) return null;
  const stale = snapshot && snapshot.case_basis_sha256 !== source.basis_sha256;
  return (
    <section className="panel ai-assistance" aria-label="AI assistance">
      <h2>AI assistance</h2>
      <p className="muted small">
        Optional advisory wording. Original facts and verification rules remain
        authoritative. AI drafts may be inaccurate and require review.
      </p>
      <button
        className="secondary"
        disabled={busy}
        onClick={() => void generate("summary")}
      >
        Summarize with AI
      </button>{" "}
      <button
        className="secondary"
        disabled={busy}
        onClick={() => void generate("explanations")}
      >
        Explain discrepancies with AI
      </button>
      {busy && <p role="status">Preparing advisory wording…</p>}
      {validating && <p role="status">Rechecking source access…</p>}
      {error && <p role="alert">{error}</p>}
      {stale && (
        <p role="status">Case sources changed. Generate a fresh draft.</p>
      )}
      {snapshot && !busy && !validating && !stale && (
        <>
          <p className="muted small">
            {snapshot.mode === "llm"
              ? `AI draft · ${snapshot.model} · Not approval evidence.`
              : `Local fallback · ${reasons[snapshot.reason ?? ""] ?? "Manual review remains available."}`}
          </p>
          <p className="muted small">
            Sources rechecked every 15 seconds and on window focus.
          </p>
          <div className="summary-sections">
            {snapshot.blocks.map((block) => (
              <article key={block.id}>
                <h3>{block.title}</h3>
                {block.ai_text && <p>{block.ai_text}</p>}
                <p className="small muted">{block.text}</p>
                <dl>
                  {Object.entries(block.facts).map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value ?? "Not recorded"}</dd>
                    </div>
                  ))}
                </dl>
                <ul>
                  {block.citations.map((citation, i) => (
                    <li key={i}>
                      <a href={citation.href}>
                        {citation.kind} · {citation.id}
                      </a>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
