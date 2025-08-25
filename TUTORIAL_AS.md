# Argumentation Semantics Toolkit (AS)

This tutorial documents a compact toolkit for **Dung-style argumentation semantics** that goes
from **natural language** → **abstract argumentation framework (AF)** → **semantics + explanations** → *(optional)* **repairs**.
The single entry point is **`argsem.py`**.

> **At a glance**
> - **`argsem.py`** — End‑to‑end runner: extract AF from text (`nl2apx.py`) → compute semantics (`af_clingo.py`) → output **Markdown** and/or **JSON**, optional **APX**/**DOT**, acceptance queries & insights. Also supports **`--repair`** to plan/generate/verify preferred‑credulous, **add‑nodes‑only** repairs with an integrated BEFORE/AFTER report.
> - **`nl2apx.py`** — Natural language → AF (IDs, edges) and **APX** encoder; supports **explicit**, **heuristic**, and **LLM** edges with provenance.
> - **`af_clingo.py`** — In‑process **clingo** encodings for grounded / preferred / stable / complete / stage / semi‑stable; small, modern, dependency‑light.
> - *(optional)* **`apxsolve.py`** — Tiny, dependency‑free reference solver for small AFs (subset enumeration).

---

## 0) Repository dependencies

**Python deps**
- `clingo` (Python bindings) — required by `af_clingo.py` and used by `argsem.py`.
- *(optional)* `google.genai` — only if you want **LLM edges** (`--use-llm`) and/or **LLM narrative** (`--llm-summarize`) or **LLM defender text** (`--llm-generate`).

**LLM credentials (optional)**
- Set `GEMINI_API_KEY`, **or** `GOOGLE_CLOUD_PROJECT` (+ optional `GOOGLE_CLOUD_LOCATION`, default `us-central1`).

**Graphviz (optional)**
- If you export a DOT graph (`--dot af.dot`), render with: `dot -Tpng af.dot -o af.png`.

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

`argsem.py` combines extraction, solving, reporting, JSON export, and (optionally) repairs.

### Quick start (reports without repair)

**Human‑readable Markdown (explicit edges)**

```bash
python argsem.py as_arguments_explicit.txt --relation explicit --target A1 --md-out report.md
```

**LLM edges + JSON + APX + DOT**

```bash
python argsem.py as_arguments_messy.txt \
  --use-llm --sem all \
  --json-out result.json \
  --apx-out graph.apx \
  --dot af.dot
```

**Both Markdown and JSON to stdout**

```bash
python argsem.py as_arguments_explicit.txt --use-llm --md --json
```

**Credulous acceptance query** (preferred is used when `--sem all`)

```bash
python argsem.py as_arguments_explicit.txt --use-llm --query A2 --mode credulous --json
```

### 🔧 Repair quick start (preferred‑credulous, add‑nodes‑only)

**Make target `A1` credulously accepted under preferred by adding one defender node that attacks all its blockers:**
```bash
python argsem.py as_arguments_explicit.txt \
  --relation explicit \
  --repair --target A1 --k 1 \
  --md-out repair_report.md --json-out repair_plan.json
```
This produces an **integrated report** with:
- **BEFORE** semantics & insights,
- the proposed **new claims** (explicit `ATTACKS:`),
- **Verification** (credulous? coverage),
- **AFTER** semantics on the combined file.

**Stronger goal** (appear in **all** preferred stances = skeptical under preferred):
```bash
python argsem.py as_arguments_explicit.txt \
  --relation explicit \
  --repair --target A1 --k 2 --min-coverage 1.0 \
  --md-out repair_report.md
```

**Already credulous?** The tool **skips** by default. To proceed anyway (e.g., to increase coverage):
```bash
python argsem.py as_arguments_explicit.txt --relation explicit --repair --target A1 --force
```

> In **repair** mode, `--apx-out` and `--dot` refer to the **AFTER** graph.  
> If you also want BEFORE artifacts, use `--apx-out-before` / `--dot-before`.

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

**Repair (preferred‑credulous, add‑nodes‑only)**
- `--repair` — enable repair flow.
- `--target A1` — which argument to make credulously accepted (required with `--repair`).
- `--k 1` — max number of **new defender nodes** to add.
- `--fanout 0` — how many blockers a single new node can attack (0 = unlimited; 1 = one blocker per node).
- `--llm-generate` — use LLM to write defender claim sentences (else deterministic templates).
- `--force` — proceed even if already credulous before repair.
- `--min-coverage 1.0` — require target to appear in at least this fraction of preferred stances (e.g., **1.0** for skeptical‑under‑preferred).
- `--apx-out-before`, `--dot-before` — export BEFORE AF (AFTER uses `--apx-out` / `--dot`).

### What the Markdown report shows

- **Arguments**: `ID → APX atom` with 1‑line text snippets.
- **Attacks** with provenance tags: `[exp]` (explicit), `[heu]` (heuristic), `[llm]` (LLM).
- **Semantics table (per argument)**:
  - In Grounded? (`✓`)
  - Counts like `Pref 2/3`, `Stable 1/2`, `Complete 3/4`, `Stage`, `SemiSt`
  - **Defense depth** (# of iterations to enter the grounded fixpoint)
- **Preferred “stance cards”**: each preferred extension with a short textual preview of its members.
- **Why‑not (target)**:
  - **Grounded roadblocks**: attackers not counter‑attacked by the grounded set.
  - Across **preferred**: **persistent** attackers (in all stances) and **soft** attackers (in some stances).
- *(Optional)* **LLM narrative**: 4–6 sentences summarizing core, stances, and blockers.
- In **repair** mode, a single integrated doc with **BEFORE → NEW CLAIMS → Verification → AFTER**.

### What the JSON includes

- `input`: your IDs, `id_to_atom` mapping, and edge provenance from extraction.
- `af`: APX atoms and `attacks` (APX names); if `--names ids` or `both`, also `(id,id)` edges.
- `semantics`: the requested semantics family, using APX names or IDs (per `--names`).
- `insights`: target, grounded core, defense depth, grounded roadblocks, preferred persistent/soft attackers.
- `query` (if used): `YES/NO` for credulous/skeptical acceptance.
- In **repair** mode: **plan** (blockers, groups, new_claims) and **verification** (after‑coverage, credulous flag).

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
- CLI is available too: `python af_clingo.py graph.apx --sem preferred`.

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

## 6) Repair mode in detail (preferred‑credulous, add‑nodes‑only)

**Goal.** Make a target argument **credulously accepted** under **preferred semantics** by **adding new nodes only** (no edits to existing edges). The planner identifies the target’s **direct attackers** (blockers), groups them, and adds **defender** claims that **attack those blockers**. Verification is run on the original + new nodes with **explicit edges** only.

**Why it works.** If the new defenders attack **all** direct attackers of the target, the set `{target} ∪ {defenders}` is admissible and can be extended to a preferred extension that **includes** the target—hence credulous acceptance.

### What the tool adds

New claim blocks (R‑nodes), for example:
```
ID: R1
ATTACKS: A2, A3
These claims share a contested assumption and ignore limiting conditions; taken together, they overstate their conclusion in this context.
```
- One or more `R*` nodes per plan (`--k` limits how many).  
- `ATTACKS:` lines are **explicit** so verification is deterministic.  
- Defender text can be LLM‑generated (`--llm-generate`) or from a **deterministic template**.

### Planning knobs

- **Coverage vs. minimality**
  - `--k 1 --fanout 0` → a **single** defender attacks **all** blockers (minimal nodes).
  - `--fanout 1` → **one defender per blocker** (clearer provenance).
- **Already credulous?**
  - Default: **skip** (no changes).
  - `--force` to proceed anyway (e.g., to **increase coverage**).
  - `--min-coverage X` for stricter goals (e.g., `1.0` = **skeptical under preferred**).

### Outputs & verification

- **Integrated report** (Markdown): BEFORE → NEW CLAIMS → Verification → AFTER.  
- **Verification** recomputes semantics on the combined file using **`--relation explicit`**, ensuring **only** the declared `ATTACKS:` edges exist for the new nodes (no hidden incoming attacks).  
- **Coverage metric**: shows **k/n ≈ frac** for how many preferred stances contain the target **before and after**.

---

## 7) Debugging tips & gotchas

- **No edges appear?** Ensure **blank lines** between blocks. `ATTACKS:` must have entries **on the same line**.
- **Heuristics not firing?** In `--relation auto`, heuristics are used **only if no explicit edges** exist anywhere.
- **LLM returns nothing?** Lower `--llm-threshold` (e.g., `0.3`) and verify env vars. Prefer `--llm-mode augment`.
- **Stable is empty?** That’s normal on some AFs (odd cycles). Check **preferred** or **semi‑stable**.
- **Query name mismatch?** APX atoms are sanitized (lowercase). `argsem.py` maps IDs↔atoms; pass either (`A2` or `a2`).

---

## 8) Reproducible examples

### 8.1 Dual‑preferred stance (no repair)

Create `as_arguments_dual_preferred_explicit.txt` (already in repo):
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
python argsem.py as_arguments_dual_preferred_explicit.txt \
  --relation explicit --target A1 --md-out report.md
python argsem.py as_arguments_dual_preferred_explicit.txt \
  --relation explicit --sem all --json-out result.json
```
You should see **two preferred stances** in both Markdown and JSON, plus a small grounded core.

### 8.2 Non‑trivial repair (A1 not credulous before)

Create `as_arguments_nontrivial_explicit.txt` (already in repo):
```
ID: A1
We should adopt a 3-day in-office policy to boost collaboration and team cohesion.

ID: A2
ATTACKS: A1
Mandatory office days harm inclusion for caregivers and colleagues with long commutes.

ID: A3
ATTACKS: A1
Remote work often increases productivity for focused tasks and reduces burnout.

ID: A4
Providing travel stipends and flexible hours can mitigate some commute burdens, but not for everyone.
```

Run repair:
```bash
python argsem.py as_arguments_nontrivial_explicit.txt \
  --relation explicit \
  --repair --target A1 --k 1 \
  --md-out repair_report.md --json-out repair_plan.json
```

Expected: **Before** credulous = NO (blockers `{A2, A3}`); **After** credulous = YES, coverage improves to `1/1`.

---

## 9) Programmatic pipelines (if you don’t want Markdown)

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
  # Build AF
  blocks = nl2apx.parse_blocks("your.txt")
  ids, id2text, idx_edges, meta = nl2apx.build_edges(blocks, relation_mode="auto")
  atoms = nl2apx.make_unique([nl2apx.sanitize_atom(i) for i in ids])
  id2atom = {ids[i]: atoms[i] for i in range(len(ids))}
  attacks = {(atoms[i], atoms[j]) for (i,j) in idx_edges}

  # Solve
  G  = af_clingo.grounded(atoms, attacks)
  PR = af_clingo.preferred(atoms, attacks)
  ```

---

## 10) Roadmap / ideas

- Carry **LLM confidence** per edge into reports (`[llm 0.72]`).
- Add **CF2 semantics** (SCC‑recursive) for odd cycles.
- `--self-test` target that runs a bundled example and emits `report.md`, `graph.apx`.
- Minimal **Argdown** subset parser → APX for fully deterministic authoring.
- **Semantic clustering** of blockers in repair mode (topic‑coherent multi‑target defenders).

---

## 11) One‑liners you’ll reuse

```bash
# LLM extraction → readable report
python argsem.py your.txt --use-llm --target A1 --md-out report.md

# Deterministic explicit edges
python argsem.py your.txt --relation explicit --target A1 --md

# Programmatic: semantics + insights to JSON
python argsem.py your.txt --use-llm --sem all --json > result.json

# Pure solving on APX (no extraction)
python af_clingo.py graph.apx --sem all --json > sem.json

# Integrated repair (minimal, one defender covers all blockers)
python argsem.py your.txt --relation explicit --repair --target A1 --k 1 --md-out repair_report.md
```
