import React, { useState } from "react";

type WinnersResult = {
  markdown?: string;
  stances?: any[];
  meta?: any;
};

export default function Winners({
  value,
  defaultWinners = "preferred",
}: {
  value: string;
  defaultWinners?:
    | "preferred"
    | "stable"
    | "grounded"
    | "complete"
    | "stage"
    | "semi-stable";
}) {
  const [sem, setSem] = useState(defaultWinners);
  const [useLLM, setUseLLM] = useState(false);
  const [repair, setRepair] = useState(false);
  const [limit, setLimit] = useState(5);
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<WinnersResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/ad/winners", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: value,
          relation: "auto",
          use_llm: useLLM,
          llm_mode: "augment",
          llm_threshold: 0.55,
          winners: sem,
          limit_stances: limit,
          repair_stance: repair,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setResp(j);
    } catch (e: any) {
      setError(e?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      <div className="toolbar">
        <label>
          Semantics:&nbsp;
          <select value={sem} onChange={(e) => setSem(e.target.value as any)}>
            <option value="preferred">preferred</option>
            <option value="stable">stable</option>
            <option value="grounded">grounded</option>
            <option value="complete">complete</option>
            <option value="stage">stage</option>
            <option value="semi-stable">semi-stable</option>
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
          <input
            type="checkbox"
            checked={repair}
            onChange={(e) => setRepair(e.target.checked)}
          />{" "}
          repair stance
        </label>
        <label>
          limit:&nbsp;
          <input
            type="number"
            min={1}
            max={10}
            value={limit}
            onChange={(e) =>
              setLimit(parseInt(e.target.value || "5", 10) || 5)
            }
            style={{ width: 60 }}
          />
        </label>
        <button onClick={run} disabled={loading || !value.trim()}>
          {loading ? "Analyzing..." : "Analyze winners (ad.py)"}
        </button>
      </div>

      <div className="code scroll">
        {error && <div className="error">{error}</div>}
        {resp?.markdown ? (
          <div style={{ whiteSpace: "pre-wrap" }}>{resp.markdown}</div>
        ) : (
          <div className="muted">
            No results yet. Paste arguments on the left, then click the button.
          </div>
        )}
      </div>
    </div>
  );
}
