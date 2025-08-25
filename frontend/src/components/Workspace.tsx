import React, { useState } from "react";
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

// Component to display AF edges/attacks
function EdgesDisplay({ attacks, meta }: { 
  attacks: [string, string][]; 
  meta: { explicit_edges?: any[]; heuristic_edges?: any[]; llm_edges?: any[] } 
}) {
  if (!attacks.length) {
    return <div className="muted">No attacks found.</div>;
  }

  const explicitCount = meta.explicit_edges?.length ?? 0;
  const heuristicCount = meta.heuristic_edges?.length ?? 0;
  const llmCount = meta.llm_edges?.length ?? 0;

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: '12px', opacity: 0.7, marginBottom: 6 }}>
        {attacks.length} attack{attacks.length !== 1 ? 's' : ''} 
        {explicitCount > 0 && ` (${explicitCount} explicit`}
        {heuristicCount > 0 && `, ${heuristicCount} heuristic`}
        {llmCount > 0 && `, ${llmCount} LLM`}
        {(explicitCount > 0 || heuristicCount > 0 || llmCount > 0) && ')'}
      </div>
      <div style={{ 
        display: 'flex', 
        flexWrap: 'wrap', 
        gap: 6, 
        fontSize: '12px',
        fontFamily: 'ui-monospace, monospace' 
      }}>
        {attacks.map(([src, dst], i) => (
          <span key={i} style={{ 
            background: '#f0f0f0', 
            padding: '2px 6px', 
            borderRadius: 4,
            border: '1px solid #ddd'
          }}>
            {src} → {dst}
          </span>
        ))}
      </div>
    </div>
  );
}

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

  const [af, setAf] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Manual analyze function
  const handleAnalyze = async () => {
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
  };

  const ids: string[] = af?.input?.ids ?? [];
  const id2atom: Record<string, string> = af?.input?.id2atom ?? {};
  const attacks: [string, string][] = af?.input?.attacks ?? [];
  const meta = af?.input?.meta ?? {};
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
          <button 
            className="btn secondary" 
            onClick={handleAnalyze} 
            disabled={loading || !text.trim()}
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
          {err && <span className="error">{err}</span>}
        </div>

        <textarea
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          className="editor"
          placeholder="Paste your arguments here (blocks separated by a blank line)…"
        />
      </div>

      {/* Right: semantics table + winners deep-dive */}
      <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div className="section-title">Semantics snapshot</div>
        <div className="card scroll">
          {af ? (
            <>
              <EdgesDisplay attacks={attacks} meta={meta} />
              {semantics ? (
                <SemanticsTable ids={ids} id2atom={id2atom} semantics={semantics} />
              ) : (
                <div className="muted">Semantics computation failed.</div>
              )}
            </>
          ) : (
            <div className="muted">No analysis yet.</div>
          )}
        </div>

        <div className="section-title" style={{ marginTop: 12 }}>
          Winners (ad.py) — deep dive
        </div>
        <div className="card scroll">
          <Winners value={text} defaultWinners="stable" />
        </div>
      </div>
    </div>
  );
}
