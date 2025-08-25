import React, { useMemo, useState } from "react"
import Graph from "./components/Graph"
import MarkdownDisplay from "./components/MarkdownDisplay"
import Winners, { WinnersState } from "./components/Winners";
import { runSemantics, runRepair, RunRequest, RepairRequest } from "./api"

const SAMPLE = `ID: A1
We should adopt a 3-day in-office policy to boost collaboration and team cohesion.

ID: A2
ATTACKS: A1
Mandatory office days harm inclusion for caregivers and colleagues with long commutes.

ID: A3
ATTACKS: A1
Remote work often increases productivity for focused tasks and reduces burnout.

ID: A4
Providing travel stipends and flexible hours can mitigate some commute burdens, but not for everyone.`

type RunResponse = any

export default function App() {
  const [text, setText] = useState<string>(SAMPLE)
  const [relation, setRelation] = useState<"auto"|"explicit"|"none">("explicit")
  const [useLLM, setUseLLM] = useState(false)
  const [target, setTarget] = useState<string>("A1")
  const [llmMode, setLLMMode] = useState<"augment"|"override">("augment")
  const [jaccard, setJaccard] = useState(0.45)
  const [minOverlap, setMinOverlap] = useState(3)
  const [activeTab, setActiveTab] = useState<"overview"|"graph"|"markdown"|"json"|"winners">("overview")
  const [loading, setLoading] = useState(false)
  const [resp, setResp] = useState<RunResponse | null>(null)

  const [repairK, setRepairK] = useState(1)
  const [repairFanout, setRepairFanout] = useState(0)
  const [repairMinCov, setRepairMinCov] = useState<number | undefined>(undefined)
  const [repairResult, setRepairResult] = useState<any | null>(null)
  const [apiKey, setApiKey] = useState<string>("")
  const [winnersState, setWinnersState] = useState<WinnersState>({
    sem: "stable",
    useLLM: false,
    repair: false,
    limit: 5,
    loading: false,
    resp: null,
    error: null
  })

  const nodes = resp?.nodes || []
  const edges = resp?.edges || []
  const cards = resp?.preferred_cards || []
  const extraction = resp?.insights?.extraction

  async function onRun() {
    setLoading(true); setActiveTab("overview"); setRepairResult(null)
    try {
      const body: RunRequest = {
        text, relation, use_llm: useLLM, llm_mode: llmMode,
        jaccard, min_overlap: minOverlap, sem: "all", target, want_markdown: true
      }
      const out = await runSemantics(body, apiKey || null)
      setResp(out)
    } catch (e:any) {
      handleError(e)
    } finally { setLoading(false) }
  }

  async function onRepair() {
    setLoading(true); setActiveTab("overview")
    try {
      const body: RepairRequest = {
        text, relation, use_llm: useLLM, llm_mode: llmMode,
        jaccard, min_overlap: minOverlap, sem: "all", target, want_markdown: true,
        repair: true, k: repairK, fanout: repairFanout,
        min_coverage: repairMinCov, verify_relation: "explicit"
      }
      const out = await runRepair(body, apiKey || null)
      setRepairResult(out)
      // also refresh baseline run panel from the result.before
      if (out?.before) setResp(out.before)
      setActiveTab("graph")
    } catch (e:any) {
      handleError(e)
    } finally { setLoading(false) }
  }

  function download(filename: string, text: string) {
    const a = document.createElement("a")
    a.href = URL.createObjectURL(new Blob([text], {type: "text/plain"}))
    a.download = filename; a.click(); URL.revokeObjectURL(a.href)
  }

  const after = repairResult?.after
  const newClaims = repairResult?.new_claims?.join("\n\n")

  function handleError(error: any) {
    let message = "An unexpected error occurred."
    
    if (error?.message) {
      const errorMsg = error.message
      
      // Parse API error responses
      if (errorMsg.includes("400 Bad Request:") && errorMsg.includes("LLM requested but not available")) {
        message = "🤖 Action requires a Gemini API key.\n\n" +
                 "You can:\n" +
                 "1. Get a free API key: https://aistudio.google.com/app/apikey\n" +
                 "2. Enter it in the 'API Key' field\n" +
                 "3. Try again!"
      } else if (errorMsg.includes("400 Bad Request:")) {
        // Extract the detail from the JSON response
        try {
          const match = errorMsg.match(/{"detail":"([^"]+)"/)
          if (match) {
            message = match[1]
          } else {
            message = errorMsg.replace("400 Bad Request: ", "")
          }
        } catch {
          message = errorMsg
        }
      } else {
        message = errorMsg
      }
    }
    
    alert(message)
  }

  function updateWinnersState(updates: Partial<WinnersState>) {
    setWinnersState(prev => ({ ...prev, ...updates }));
  }

  async function runWinners(params: {
    text: string;
    sem: string;
    useLLM: boolean;
    repair: boolean;
    limit: number;
  }) {
    setWinnersState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json"
      };
      
      if (apiKey) {
        headers["X-Gemini-API-Key"] = apiKey;
      }
      
      const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";
      const r = await fetch(`${API_BASE}/api/ad/winners`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          text: params.text,
          relation: "auto",
          use_llm: params.useLLM,
          llm_mode: "augment",
          llm_threshold: 0.55,
          winners: params.sem,
          limit_stances: params.limit,
          repair_stance: params.repair,
        })
      });
      if (!r.ok) {
        const errorText = await r.text();
        throw new Error(`${r.status} ${r.statusText}: ${errorText}`);
      }
      const j = await r.json();
      setWinnersState(prev => ({ ...prev, resp: j, loading: false }));
    } catch (e: any) {
      setWinnersState(prev => ({ 
        ...prev, 
        error: null, 
        loading: false 
      }));
      handleError(e);
    }
  }

  return (
      <div style={{ padding: 16, maxWidth: 1200, margin: "0 auto", minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>🧭 Argumentation Semantics Playground</h2>
        <div className="row">
          <button className="btn secondary" onClick={() => download("arguments.txt", text)}>Download input</button>
          {resp?.apx && <button className="btn secondary" onClick={() => download("graph_before.apx", resp.apx)}>APX (before)</button>}
          {resp?.dot && <button className="btn secondary" onClick={() => download("af_before.dot", resp.dot)}>DOT (before)</button>}
          {after?.apx && <button className="btn secondary" onClick={() => download("graph_after.apx", after.apx)}>APX (after)</button>}
          {after?.dot && <button className="btn secondary" onClick={() => download("af_after.dot", after.dot)}>DOT (after)</button>}
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 12, flex: 1, minHeight: 0 }}>
        <div className="panel">
          <div className="section-title">Input arguments.txt</div>
          <textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Paste or type your argument blocks here..." />

          <div className="section-title">Extraction & semantics</div>
          <div className="row">
            <label>Relation</label>
            <select value={relation} onChange={e=>setRelation(e.target.value as any)}>
              <option value="auto">auto</option>
              <option value="explicit">explicit</option>
              <option value="none">none</option>
            </select>
            <label>use‑LLM</label>
            <input type="checkbox" checked={useLLM} onChange={e=>setUseLLM(e.target.checked)} />
            <label>LLM mode</label>
            <select disabled={!useLLM} value={llmMode} onChange={e=>setLLMMode(e.target.value as any)}>
              <option value="augment">augment</option>
              <option value="override">override</option>
            </select>
          </div>
          <div className="row">
            <label>API Key</label>
            <input 
              type="password" 
              value={apiKey} 
              onChange={e=>setApiKey(e.target.value)} 
              placeholder="Optional: Gemini API key" 
              style={{width: 200}}
              title="Enter your Gemini API key for AI-powered analysis"
            />
            {!apiKey && (
              <a 
                href="https://aistudio.google.com/app/apikey" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{fontSize: '12px', marginLeft: '8px', color: '#666'}}
              >
              Get API key
              </a>
            )}
            <label>target</label>
            <input type="text" value={target} onChange={e=>setTarget(e.target.value)} style={{ width: 80 }}/>
          </div>
          <div className="row">
            <label>jaccard</label><input type="number" step="0.05" value={jaccard} onChange={e=>setJaccard(parseFloat(e.target.value))} style={{width:90}}/>
            <label>minOverlap</label><input type="number" value={minOverlap} onChange={e=>setMinOverlap(parseInt(e.target.value))} style={{width:90}}/>
          </div>

          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={onRun} disabled={loading}>{loading ? "Running..." : "Run semantics"}</button>
            <div className="pill small">APX atoms, preferred/grounded/stable/…</div>
          </div>

          <div className="section-title">Repair (preferred‑credulous)</div>
          <div className="row">
            <label>k</label><input type="number" value={repairK} onChange={e=>setRepairK(parseInt(e.target.value))} style={{width:80}}/>
            <label>fanout</label><input type="number" value={repairFanout} onChange={e=>setRepairFanout(parseInt(e.target.value))} style={{width:80}}/>
            <label>min‑coverage</label><input type="number" step="0.1" placeholder="(optional)" value={(repairMinCov as any) ?? ""} onChange={e=>setRepairMinCov(e.target.value === "" ? undefined : parseFloat(e.target.value))} style={{width:120}}/>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={onRepair} disabled={loading}>{loading ? "Planning..." : "Run repair"}</button>
            <div className="pill small">Adds R‑nodes to attack blockers of target</div>
          </div>
        </div>

        <div className="panel">
          <div className="tabs">
            <div className={`tab ${activeTab==='overview'?'active':''}`} onClick={()=>setActiveTab('overview')}>Overview</div>
            <div className={`tab ${activeTab==='graph'?'active':''}`} onClick={()=>setActiveTab('graph')}>Graph</div>
            <div className={`tab ${activeTab==='winners'?'active':''}`} onClick={()=>setActiveTab('winners')}>Winners</div>
            <div className={`tab ${activeTab==='markdown'?'active':''}`} onClick={()=>setActiveTab('markdown')}>Markdown</div>
            <div className={`tab ${activeTab==='json'?'active':''}`} onClick={()=>setActiveTab('json')}>JSON</div>
          </div>

          {activeTab === "overview" && (
            <div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div>
                  <div className="section-title">Extraction summary</div>
                  {extraction ? (
                    <div className="small">
                      <div>explicit: {extraction.explicit}, heuristic: {extraction.heuristic}, llm: {extraction.llm}</div>
                      <div>total edges: {extraction.total_edges} {extraction.total_edges===0 && <span className="warn">— no attacks extracted</span>}</div>
                      {extraction.auto_note && <div>auto: {extraction.auto_note}</div>}
                    </div>
                  ) : <div className="small">Run semantics to see extraction stats.</div>}
                </div>
                <div>
                  {resp?.insights?.target?.id && (
                    <div className="small">
                      <div>Target: <b>{resp.insights.target.id}</b></div>
                      <div>Grounded roadblocks: {resp.insights.grounded_roadblocks?.join(", ") || "(none)"}</div>
                    </div>
                  )}
                </div>
              </div>

              <div className="section-title" style={{marginTop:12}}>Preferred stance cards</div>
              {cards?.length ? cards.map((c:any) => (
                <div key={c.name} className="panel" style={{padding:8, marginBottom:6}}>
                  <div><b>{c.name}</b> = {'{'}{c.members.join(", ")}{'}'}</div>
                  <div className="small">preview: {c.preview}</div>
                </div>
              )) : <div className="small">No preferred stances yet.</div>}

              {repairResult && (
                <div style={{ marginTop: 12 }}>
                  <div className="section-title">Repair result</div>
                  <div className="small">Preferred credulous after? <b className={repairResult?.after?.insights?.preferred_credulous ? "success":"danger"}>{repairResult?.after?.insights?.preferred_credulous ? "YES" : "NO"}</b></div>
                  <div className="small">Coverage after: {repairResult?.after?.insights?.preferred_coverage?.k}/{repairResult?.after?.insights?.preferred_coverage?.n} ≈ {Number(repairResult?.after?.insights?.preferred_coverage?.frac||0).toFixed(2)}</div>
                  <div className="section-title">New claims</div>
                  <div className="code small" style={{whiteSpace:"pre-wrap"}}>{newClaims || "(none)"}</div>
                </div>
              )}
            </div>
          )}

          {activeTab === "graph" && (
            <div>
              <div className="section-title">Graph (BEFORE)</div>
              <Graph nodes={nodes} edges={edges} highlightId={target} />
              {after && (
                <div>
                  <div className="section-title">Graph (AFTER)</div>
                  <Graph nodes={after.nodes} edges={after.edges} highlightId={target} />
                </div>
              )}
            </div>
          )}

          {activeTab === "winners" && (
            <Winners 
              value={text} 
              winnersState={winnersState}
              onUpdateWinnersState={updateWinnersState}
              onRunWinners={runWinners}
            />
          )}

          {activeTab === "markdown" && (
            <MarkdownDisplay 
              content={repairResult?.markdown?.integrated || resp?.markdown || "(no markdown)"}
              style={{whiteSpace:"pre-wrap"}}
            />
          )}

          {activeTab === "json" && (
            <div className="code small">{JSON.stringify(resp, null, 2)}</div>
          )}
        </div>
      </div>

      <div style={{marginTop:12}} className="small">
        Tip: In <b>auto</b>, if you get zero edges, try lowering jaccard/minOverlap or enable <b>use‑LLM</b>.
      </div>
    </div>
  )
}
