export type RunRequest = {
  text: string;
  relation?: "auto" | "explicit" | "none";
  jaccard?: number;
  min_overlap?: number;
  use_llm?: boolean;
  llm_threshold?: number;
  llm_mode?: "augment" | "override";
  sem?: "grounded" | "preferred" | "stable" | "complete" | "stage" | "semi-stable" | "semistable" | "all";
  target?: string | null;
  max_pref_cards?: number;
  want_markdown?: boolean;
};

export type RepairRequest = RunRequest & {
  repair?: boolean;
  k?: number;
  fanout?: number;
  new_prefix?: string;
  llm_generate?: boolean;
  force?: boolean;
  min_coverage?: number | null;
  verify_relation?: "explicit" | "same";
};

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

async function postJSON<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${txt}`);
  }
  return await res.json();
}

export function runSemantics(req: RunRequest) {
  return postJSON("/api/run", req);
}

export function runRepair(req: RepairRequest) {
  return postJSON("/api/repair", req);
}
