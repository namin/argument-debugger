import React, { useEffect, useState } from "react";
import "./styles.css";

type UnifiedResult = {
  markdown: string;
  af: any;
  semantics: any;
  insights: any;
  winners: any;
  ad_available: boolean;
};

export default function App() {
  const [text, setText] = useState("");
  const [relation, setRelation] = useState<"auto"|"explicit"|"none">("auto");
  const [useLLM, setUseLLM] = useState(false);
  const [winners, setWinners] = useState<"preferred"|"stable"|"grounded"|"complete"|"stage"|"semi-stable">("stable");
  const [repair, setRepair] = useState(false);
  const [target, setTarget] = useState<string>("");

  const [resp, setResp] = useState<UnifiedResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(()=>{
    const saved = localStorage.getItem("argdebugger:text");
    if (saved) setText(saved);
  }, []);
  useEffect(()=>{
    localStorage.setItem("argdebugger:text", text || "");
  }, [text]);

  async function run() {
    setLoading(true); setError(null);
    try {
      const r = await fetch("/api/unified", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          text, relation, use_llm: useLLM,
          winners, repair, target: target || null
        })
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setResp(j);
    } catch (e:any) {
      setError(e?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  // Derive IDs from last response (to populate target dropdown)
  const ids: string[] = resp?.af?.ids || [];

  return (
    <div className="app">
      <header className="appbar">
        <div className="brand">Argument Debugger</div>
        <div className="spacer" />
        <a className="link" href="https://github.com/namin/argument-debugger" target="_blank" rel="noreferrer">
        <img 
            src="/github-mark.png" 
            alt="GitHub" 
            style={{width: 16, height: 16}}
          />
        </a>
      </header>

      <main className="main">
        <div className="workspace two-col">
          {/* Left: Editor + controls */}
          <div className="left-col">
            <div className="toolbar">
              <label>Relation:&nbsp;
                <select value={relation} onChange={e=>setRelation(e.target.value as any)}>
                  <option value="auto">auto</option>
                  <option value="explicit">explicit</option>
                  <option value="none">none</option>
                </select>
              </label>
              <label><input type="checkbox" checked={useLLM} onChange={e=>setUseLLM(e.target.checked)} /> use LLM edges</label>
              <label>Winners:&nbsp;
                <select value={winners} onChange={e=>setWinners(e.target.value as any)}>
                  <option value="stable">stable</option>
                  <option value="preferred">preferred</option>
                  <option value="grounded">grounded</option>
                  <option value="complete">complete</option>
                  <option value="stage">stage</option>
                  <option value="semi-stable">semi-stable</option>
                </select>
              </label>
              <label><input type="checkbox" checked={repair} onChange={e=>setRepair(e.target.checked)} /> repair stance</label>
              <label>Target:&nbsp;
                <select value={target} onChange={(e)=>setTarget(e.target.value)}>
                  <option value="">(none)</option>
                  {ids.map(i=><option key={i} value={i}>{i}</option>)}
                </select>
              </label>
              <button onClick={run} disabled={loading || !text.trim()}>
                {loading ? "Analyzing…" : "Analyze"}
              </button>
              {error && <span className="error">{error}</span>}
            </div>
            <textarea
              className="editor"
              value={text}
              onChange={e=>setText(e.target.value)}
              placeholder="Paste your arguments here (blocks separated by a blank line)…"
            />
          </div>

          {/* Right: Unified Markdown */}
          <div className="right-col">
            <div className="card scroll code">
              {resp?.markdown
                ? <div style={{whiteSpace:"pre-wrap"}}>{resp.markdown}</div>
                : <div className="muted">No report yet. Paste arguments and click Analyze.</div>
              }
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
