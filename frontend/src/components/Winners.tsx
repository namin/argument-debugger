// frontend/src/components/Winners.tsx
import React from "react";
import MarkdownDisplay from "./MarkdownDisplay";

type WinnersResult = {
  markdown?: string;
  stances?: any[];
  meta?: any;
};

export type WinnersState = {
  sem: "preferred"|"stable"|"grounded"|"complete"|"stage"|"semi-stable";
  useLLM: boolean;
  repair: boolean;
  limit: number;
  loading: boolean;
  resp: WinnersResult | null;
  error: string | null;
};

interface WinnersProps {
  value: string;
  winnersState: WinnersState;
  onUpdateWinnersState: (updates: Partial<WinnersState>) => void;
  onRunWinners: (params: {
    text: string;
    sem: string;
    useLLM: boolean;
    repair: boolean;
    limit: number;
  }) => Promise<void>;
}

export default function Winners({
  value,
  winnersState,
  onUpdateWinnersState,
  onRunWinners
}: WinnersProps) {
  const { sem, useLLM, repair, limit, loading, resp, error } = winnersState;

  async function run() {
    await onRunWinners({
      text: value,
      sem,
      useLLM,
      repair,
      limit
    });
  }

  return (
    <div className="panel" style={{display:"flex", flexDirection:"column", minHeight: 0}}>
      <div style={{display:"flex", gap:12, flexWrap:"wrap", alignItems:"center"}}>
        <label>Semantics:&nbsp;
          <select value={sem} onChange={e=>onUpdateWinnersState({sem: e.target.value as any})}>
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
            onChange={e=>onUpdateWinnersState({useLLM: e.target.checked})} 
          /> 
          use LLM edges
        </label>
        <label>
          <input 
            type="checkbox" 
            checked={repair} 
            onChange={e=>onUpdateWinnersState({repair: e.target.checked})} 
          /> 
          repair stance
        </label>
        <label>limit:&nbsp;
          <input 
            type="number" 
            min={1} 
            max={10} 
            value={limit} 
            onChange={e=>onUpdateWinnersState({limit: parseInt(e.target.value||"5",10)})} 
            style={{width:60}}
          />
        </label>
        <button onClick={run} disabled={loading || !value.trim()}>
          {loading ? "Analyzing..." : "Analyze winners (ad.py)"}
        </button>
      </div>

      <div style={{marginTop:12, flex:1, minHeight:0, overflow:"auto"}}>
        {error && <div style={{color:"#ff8a8a", marginBottom: 12}}>{error}</div>}
        {resp?.markdown ? (
          <MarkdownDisplay 
            content={resp.markdown}
            style={{flex: 1, minHeight: 0, overflow: "auto"}}
          />
        ) : (
          <div style={{opacity:0.7}}>
            No results yet. Paste arguments on the left, then click the button.
          </div>
        )}
      </div>
    </div>
  );
}