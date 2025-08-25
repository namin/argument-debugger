import React, { useEffect, useMemo, useState } from "react";
import Winners from "./Winners";
import SemanticsTable from "./SemanticsTable";

type SemanticsPayload = {
  grounded: string[];
  preferred: string[][];
  stable: string[][];
  complete: string[][];
  stage: string[][];
  semi_stable: string[][];
};

export default function Workspace({
  text,
  onTextChange,
}: {
  text: string;
  onTextChange: (s: string) => void;
}) {
  const [relation, setRelation] =
    useState<"auto" | "explicit" | "none">("auto");
  const [useLLM, setUseLLM] = useState(false);
  const [target, setTarget] = useState<string>("");

  const [af, setAf] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Keep target valid as IDs change
  const ids: string[] = af?.input?.ids ?? [];
  useEffect(() => {
    if (!ids.includes(target)) {
      setTarget(ids[0] || "");
    }
  }, [ids]); // eslint-disable-line

  // Debounce /api/run/af
  useEffect(() => {
    const t = setTimeout(() => {
      (async () => {
        if (!text.trim()) {
          setAf(null);
          return;
        }
        setLoading(true);
        setErr(null);
        try {
          const r = await fetch("/api/run/af", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              text,
              relation,
              use_llm: useLLM,
              llm_mode: "augment",
              llm_threshold: 0.55,
              target: target || null,
              include_markdown: true,
              max_pref_cards: 4,
            }),
          });
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          const j = await r.json();
          setAf(j);
        } catch (e: any) {
          setErr(e?.message || "request failed");
        } finally {
          setLoading(false);
        }
      })();
    }, 350);
    return () => clearTimeout(t);
  }, [text, relation, useLLM, target]);

  const id2atom: Record<string, string> = af?.input?.id2atom ?? {};
  const semantics: SemanticsPayload | undefined = af?.semantics;

  return (
    <div
      className="workspace"
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(380px, 1fr) 1fr",
        gap: 12,
        height: "100%",
        minHeight: 0,
      }}
    >
      {/* Left: editor + controls */}
      <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div className="toolbar">
          <label>
            Relation:&nbsp;
            <select
              value={relation}
              onChange={(e) => setRelation(e.target.value as any)}
            >
              <option value="auto">auto</option>
              <option value="explicit">explicit</option>
              <option value="none">none</option>
            </select>
          </label>
          <label>
            <input
              type="checkbox"
              checked={useLLM}
              onChange={(e) => setUseLLM(e.target.checked)}
            />{" "}
            use LLM edges
          </label>
          <label>
            Target:&nbsp;
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              disabled={!ids.length}
            >
              {ids.length === 0 ? (
                <option value="">—</option>
              ) : (
                ids.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))
              )}
            </select>
          </label>
          {loading && <span className="muted">Analyzing…</span>}
          {err && <span className="error">{err}</span>}
        </div>

        <textarea
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          className="editor"
          placeholder="Paste your arguments here (blocks separated by a blank line)…"
        />
      </div>

      {/* Right: semantics table + rich AF report + winners deep-dive */}
      <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div className="section-title">Semantics snapshot</div>
        <div className="card scroll" style={{ marginBottom: 12 }}>
          {semantics ? (
            <SemanticsTable ids={ids} id2atom={id2atom} semantics={semantics} />
          ) : (
            <div className="muted">No AF yet.</div>
          )}
        </div>

        <div className="section-title">AF report (argsem‑style)</div>
        <div className="card scroll" style={{ marginBottom: 12 }}>
          {af?.report_markdown ? (
            <div className="code" style={{ whiteSpace: "pre-wrap" }}>
              {af.report_markdown}
            </div>
          ) : (
            <div className="muted">No report yet.</div>
          )}
        </div>

        <div className="section-title">Winners (ad.py) — deep dive</div>
        <div className="card scroll">
          <Winners value={text} defaultWinners="stable" />
        </div>
      </div>
    </div>
  );
}

