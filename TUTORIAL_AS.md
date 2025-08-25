# Argumentation Semantics Toolkit

This tutorial documents a compact toolkit for **Dung-style argumentation semantics** that goes
from **natural language** → **abstract argumentation framework (AF)** → **semantics + explanations**.
The single entry point is **`argsem.py`**.

> **At a glance**
> - **`argsem.py`** — End‑to‑end runner: extract AF from text (`nl2apx.py`) → compute semantics (`af_clingo.py`) → output **Markdown** and/or **JSON**, optional **APX**/**DOT**, queries + insights.
> - **`nl2apx.py`** — Natural language → AF (IDs, edges) and **APX** encoder; supports **explicit**, **heuristic**, and **LLM** edges, with provenance.
> - **`af_clingo.py`** — In‑process **clingo** encodings for grounded / preferred / stable / complete / stage / semi‑stable; CLI included.
> - *(optional)* **`apxsolve.py`** — Small, dependency‑free reference solver (subset enumeration) for small AFs.

---

## 0) Repository dependencies

**Python deps**
- `clingo` (Python bindings) — required by `af_clingo.py` and used by `argsem.py`.
- *(optional)* `google.genai` — only if you want **LLM edges** and/or **LLM narrative**.

**LLM credentials (optional)**
- Set `GEMINI_API_KEY`, **or** `GOOGLE_CLOUD_PROJECT` (+ optional `GOOGLE_CLOUD_LOCATION`, default `us-central1`).

**Graphviz (optional)**
- If you export DOT (`--dot af.dot`), render with: `dot -Tpng af.dot -o af.png`.

---

## 1) Input format (text blocks)

- Each **argument** is one **block**, separated by a **blank line**.
- Optional directives inside a block:
  - `ID: A1` — explicit identifier (else auto‑labels `A1, A2, …`)
  - `ATTACKS: A2, A3` — explicit attacks **by ID**
  - `ATTACKS: #2 #3` — explicit attacks **by 1‑based index**

**Example (explicit)**
```
ID: A1
We should adopt a 3‑day in‑office policy to boost collaboration.

ID: A2
ATTACKS: A1
Fully remote work increases productivity for focused tasks.
```

**Example (implicit → heuristics/LLM)**
```
We should adopt a 3‑day in‑office policy to boost collaboration.

Fully remote work increases productivity for focused tasks.
```

> **Important:** Keep a **blank line** between blocks. `ATTACKS:` entries must be on the **same line** as `ATTACKS:`.

---

## 2) Unified runner — `argsem.py`

`argsem.py` combines extraction, solving, reporting, and JSON export.

### Quick start

**Human‑readable Markdown (explicit edges)**

```bash
python argsem.py arguments.txt --relation explicit --target A1 --md-out report.md
```

**LLM edges + JSON + APX + DOT**

```bash
python argsem.py examples_llm_messy.txt \
  --use-llm --sem all \
  --json-out result.json \
  --apx-out graph.apx \
  --dot af.dot
```

**Both Markdown and JSON to stdout**

```bash
python argsem.py arguments.txt --use-llm --md --json
```

**Credulous acceptance query** (preferred is used when `--sem all`)

```bash
python argsem.py arguments.txt --use-llm --query A2 --mode credulous --json
```

### Flag cheat‑sheet

**Extraction (via `nl2apx`)**
- `--relation {auto,explicit,none}` — default `auto` (use `ATTACKS:` if present; otherwise heuristics).
- `--use-llm` — enable LLM edge inference.
- `--llm-threshold 0.55` — drop low‑confidence LLM edges.
- `--llm-mode {augment,override}` — union with other edges or replace them.
- Heuristics knobs: `--jaccard 0.45`, `--min-overlap 3`.

**Semantics (via `af_clingo`)**
- `--sem {grounded,preferred,stable,complete,stage,semi-stable,all}`.

**Outputs**
- Markdown: `--md` (stdout) or `--md-out report.md`.
- JSON: `--json` (stdout) or `--json-out result.json`.
- APX: `--apx-out graph.apx` (includes mapping & provenance as comments).
- DOT: `--dot af.dot`.
- JSON name scheme: `--names {apx,ids,both}`.

**Queries & insights**
- `--query A2 --mode {credulous, skeptical}`.
- `--target A1` — focus for “why‑not” analysis.
- `--llm-summarize` — adds a short LLM narrative to the Markdown (optional).
- `--max-pref-cards 4` — limit preferred “stance cards” printed in Markdown.

### What the Markdown report shows

- **Arguments**: `ID → APX atom` with 1‑line text snippets.
- **Attacks** with provenance: `[exp]` (explicit), `[heu]` (heuristic), `[llm]` (LLM).
- **Semantics table (per argument)**:
  - In Grounded? (`✓`)
  - Counts like `Pref 2/3`, `Stable 1/2`, `Complete 3/4`, `Stage`, `SemiSt`
  - **Defense depth** (# of iterations to enter the grounded fixpoint)
- **Preferred “stance cards”**: each preferred extension with a short textual preview of its members.
- **Why‑not (target)**:
  - **Grounded roadblocks**: attackers not counter‑attacked by the grounded set.
  - Across **preferred**: **persistent** attackers (in all stances) and **soft** attackers (in some stances).
- *(Optional)* **LLM narrative**: 4–6 sentences summarizing core, stances, and blockers.

### What the JSON includes

- `input`: your IDs, `id_to_atom` mapping, and edge provenance from extraction.
- `af`: APX atoms and `attacks` (APX names); if `--names ids` or `both`, also `(id,id)` edges.
- `semantics`: the requested semantics family, using APX names or IDs (per `--names`).
- `insights`: target, grounded core, defense depth, grounded roadblocks, preferred persistent/soft attackers.
- `query` (if used): `YES/NO` for credulous/skeptical acceptance.

---

## 3) Extraction internals — `nl2apx.py`

- Reads blocks and emits AF (arguments and directed attacks). Optionally writes **APX** facts:
  ```
  arg(a1).
  arg(a2).
  att(a2,a1).
  ```
- Edge sources (provenance):
  - **explicit** — from `ATTACKS:` lines
  - **heuristic** — token overlap + negation cues (used if `auto` and no `ATTACKS:` anywhere)
  - **LLM** — model proposes attacks; filtered by confidence
- `argsem.py` carries these provenance tags forward into reports and APX comments.

---

## 4) Solving internals — `af_clingo.py`

- Uses **clingo** with small embedded programs (no legacy wrappers) to compute:
  - **grounded**, **complete**, **preferred**, **stable**, **stage**, **semi‑stable**.
- Programmatic use:
  ```python
  from af_clingo import grounded, preferred, stable
  G  = grounded(atoms, attacks)
  PR = preferred(atoms, attacks)
  ST = stable(atoms, attacks)
  ```
- CLI is available too (`python af_clingo.py graph.apx --sem preferred`).

---

## 5) Interpreting semantics (one‑paragraph refresher)

- **Conflict‑free**: no internal attacks.  
- **Admissible**: conflict‑free + defends all members.  
- **Complete**: admissible and contains all arguments it defends.  
- **Grounded**: **least** complete extension (skeptical core).  
- **Preferred**: ⊆‑maximal admissible sets (**stances**).  
- **Stable**: conflict‑free and attacks everything outside (may not exist).  
- **Stage / Semi‑stable**: maximize **range** over conflict‑free / complete sets.

---

## 6) Debugging tips & gotchas

- **No edges appear?** Ensure **blank lines** between blocks. `ATTACKS:` must have entries **on the same line**.
- **Heuristics not firing?** In `--relation auto`, heuristics are used **only if no explicit edges** exist anywhere.
- **LLM returns nothing?** Lower `--llm-threshold` (e.g., `0.3`) and verify env vars. Prefer `--llm-mode augment`.
- **Stable is empty?** That’s normal on some AFs (odd cycles). Check **preferred** or **semi‑stable**.
- **Query name mismatch?** APX atoms are sanitized (lowercase). `argsem.py` maps IDs↔atoms; pass either (`A2` or `a2`).

---

## 7) Reproducible mini example

Create `examples_dual_preferred.txt`:
```
ID: A1
ATTACKS: A2
Approve this quarter to seize first‑mover advantage.

ID: A2
ATTACKS: A1
Do not approve; compliance review is incomplete.

ID: A3
ATTACKS: A2
Critical compliance items are cleared; residual risk is small.

ID: A4
ATTACKS: A1
Rushing approval increases defect risk.
```

Run:
```bash
python argsem.py examples_dual_preferred.txt --relation explicit --target A1 --md-out report.md
python argsem.py examples_dual_preferred.txt --relation explicit --sem all --json-out result.json
```

You should see **two preferred stances** in both Markdown and JSON, plus a small grounded core.

---

## 8) Programmatic pipelines (if you don’t want Markdown)

- **Everything in one JSON**:
  ```bash
  python argsem.py your.txt --use-llm --sem all --json > result.json
  ```
- **APX for external solvers + DOT for visualization**:
  ```bash
  python argsem.py your.txt --use-llm --apx-out graph.apx --dot af.dot
  ```
- **Direct library use** (bypass APX):
  ```python
  import nl2apx, af_clingo
  ids, id2text, atoms, id2atom, atom2id, attacks, meta = ... # via nl2apx.build_edges + mapping
  prefs = af_clingo.preferred(atoms, attacks)
  ```

---

## 9) Roadmap / ideas

- Carry **LLM confidence** per edge into reports (`[llm 0.72]`).
- Add **CF2 semantics** (SCC‑recursive) for odd cycles.
- `--self-test` target that runs a bundled example and emits `report.md`, `graph.apx`.
- Minimal **Argdown** subset parser → APX for fully deterministic authoring.

---

## 10) One‑liners you’ll reuse

```bash
# LLM extraction → readable report
python argsem.py your.txt --use-llm --target A1 --md-out report.md

# Deterministic explicit edges
python argsem.py your.txt --relation explicit --target A1 --md

# Programmatic: semantics + insights to JSON
python argsem.py your.txt --use-llm --sem all --json > result.json

# Pure solving on APX (no extraction)
python af_clingo.py graph.apx --sem all --json > sem.json
```
