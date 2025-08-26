# Argumentation Semantics — Unified Toolkit

This tutorial documents the **unified** pipeline that powers both the CLI and the web app:
a **single AF** is extracted once from your text and then reused for
semantics ([cheatsheet](ARGUMENTATION_SEMANTICS.md)) **and** for **ad.py** (issue-finder/repair) on the winning sets.

> **Modules at a glance**
>
> - `unified_core.py` — the one-graph engine (NL → AF → semantics → winners → ad.py) that also builds the **unified Markdown**.
> - `run_unified.py` — CLI wrapper that prints the same **unified Markdown** and can also emit JSON.
> - `server.py` — thin FastAPI wrapper (one endpoint: `/api/unified`) calling `unified_core`.
> - `frontend/` — tiny two‑pane UI: editor on the left; unified Markdown on the right.
> - Core deps you already had: `nl2apx.py`, `af_clingo.py`, `ad.py`.

---

## 0) Install

**Python**
```bash
pip install clingo fastapi uvicorn google-genai
# google-genai is only needed if you enable --use-llm
```

**Node (frontend)**
- Node 18+ recommended.
- In `frontend/`, install and run (Vite + React + TS):
  ```bash
  npm install
  npm run dev
  ```

> If you use LLM edges or ad.py repairs, set **one** of:
> - `export GEMINI_API_KEY=...`  
> - or `export GOOGLE_CLOUD_PROJECT=...` (and optional `GOOGLE_CLOUD_LOCATION`, default `us-central1`).

---

## 1) Input format (text → AF)

Your input is a plain text file with **blocks** separated by a **blank line**. Each block is one argument.

**Directives (optional, per block)**
- `ID: A1` — explicit identifier; otherwise auto‑labels `A1, A2, …`.
- `ATTACKS: A2, A3` — outgoing attacks by **ID**.
- `ATTACKS: #2 #3` — outgoing attacks by **1‑based index**.

**Example**
```
ID: A1
We should adopt a 3‑day in‑office policy to boost collaboration.

ID: A2
ATTACKS: A1
Remote work increases productivity for focused tasks.
```

> **Important**: keep a **blank line** between blocks; keep the `ATTACKS:` list **on the same line**.

**Edge sources (provenance)**
- **explicit** — taken from `ATTACKS:`.
- **heuristic** — token overlap + simple negation cues (used only if `relation=auto` and **no** explicit edges anywhere).
- **llm** — proposed by an LLM when `--use-llm` is on (filtered by `--llm-threshold`).

The unified report carries these tags through as `[exp]`, `[heu]`, `[llm]` next to each attack.

---

## 2) CLI (one command)

```bash
python run_unified.py your_arguments.txt \
  --relation auto \
  --use-llm \            # optional
  --winners stable \     # preferred|stable|grounded|complete|stage|semi-stable
  --repair \             # ask ad.py to propose fixes per stance
  --target A1 \          # why (not) diagnostics for a focal ID
  --md-out report.md \
  --json-out result.json
```

- **Single AF**: The graph is extracted once and reused for **both** semantics and ad.py stance analysis.
- **Output**: A single **unified Markdown** report (also printed to stdout if `--md-out` is omitted) + optional JSON.

---

## 3) Server (thin wrapper)

Start the API:
```bash
uvicorn server:app --reload --port 8000
```

**Endpoint**
```
POST /api/unified
{
  "text": "...",            // your blocks
  "relation": "auto",       // auto|explicit|none
  "use_llm": false,         // enable LLM edges
  "winners": "stable",      // semantics used to form stances
  "repair": false,          // run ad.py repair on each stance
  "target": "A1"            // optional focus for 'why (not)'
}
```

**Response**
```json
{
  "markdown": "...",            // the same unified Markdown as the CLI
  "af": { "ids": [...], "id2atom": {...}, "attacks_by_tag": {...}, "id_attacks": [["A2","A1"], ...] },
  "semantics": { "grounded": [...], "preferred": [[...]], ... },
  "insights": { "grounded_ids": [...], "defense_depth": {...}, "preferred_cards": [...], "why": {...} },
  "winners": { "name": "stable", "count": 1, "sets_atoms": [[...]] },
  "ad_available": true
}
```

---

## 4) Frontend (two panes, one graph)

- Left: editable text area + a compact toolbar (relation, LLM, winners, repair, target).
- Right: the **unified Markdown** (AF + stances analyzed by ad.py) — always consistent with the **same** extracted graph.

The UI calls just one endpoint: `POST /api/unified`.

---

## 5) What the unified Markdown shows

1. **AF Report**
   - **Arguments**: `ID → atom` with one‑line text.
   - **Attacks** with provenance: `[exp]`, `[heu]`, `[llm]`.
   - **Semantics table**: grounded ✓, and counts like `Pref 1/2`, `Stable 0/1`.
   - **Defense depth**: iteration at which each node enters the grounded fixpoint.
   - **Preferred “stance cards”**: a few preferred extensions with short previews.
   - **Why (not)** for a `target`: grounded roadblocks; across preferred, **persistent** vs **soft** attackers.

2. **Winners analyzed by ad.py** (same graph)
   - For each winning set (by your `--winners` semantics):
     - **Members** (IDs + short text previews).
     - **ad.py parse**: claims, inferences, goal.
     - **Issues**: missing links, unsupported premises, circularity, etc.
     - **(Optional) Repair excerpt** if `--repair`.

---

## 6) Semantics refresher

- **Conflict‑free**: no internal attacks.
- **Admissible**: conflict‑free and defends all members.
- **Complete**: admissible and contains every argument it defends.
- **Grounded**: least complete set (skeptical core).
- **Preferred**: ⊆‑maximal admissible sets (stances).
- **Stable**: conflict‑free and attacks everything outside (may not exist).
- **Stage / Semi‑stable**: maximize range over conflict‑free / complete sets.

---

## 7) Troubleshooting

- **No edges appear**: in `relation=auto`, heuristics run only if **no** block uses `ATTACKS:`. You can enable `--use-llm` or use `relation=explicit`.
- **LLM returns nothing**: lower `--llm-threshold` (e.g., `0.35`); verify env vars; prefer `llm_mode=augment`.
- **Stable empty**: expected on some graphs (odd cycles). Try `preferred` or `semi-stable`.
- **Target not listed**: IDs are discovered after extraction. Use an existing ID (e.g., `A1`) or omit.
- **CORS**: the dev server sets permissive CORS for local use; trim it before deploying.
- **Performance**: for very large inputs, start with `relation=explicit`, then add LLM edges selectively.

---

## 8) One‑liners you’ll reuse

```bash
# CLI — unified Markdown + JSON
python run_unified.py examples/as_arguments_messy.txt \
  --relation auto --winners stable --repair --target A1 \
  --md-out report.md --json-out result.json

# API — same pipeline
curl -sS localhost:8000/api/unified \
  -H 'Content-Type: application/json' \
  -d '{"text":"ID: A1\nA...\n\nID: A2\nATTACKS: A1\nB...", "relation":"explicit", "winners":"preferred"}' \
  | jq '.markdown' -r
```

---

## 9) Roadmap ideas

- CF2 / SCC‑recursive semantics (odd cycles).
- Edge weights + “most stable” stance selection.
- Confidence‑aware LLM edges (carry scores into Markdown).
- Deterministic Argdown → AF path (for authoring).
- Rich stance comparison (what flips an argument between stances?).

---

Happy debugging!
