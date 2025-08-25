# TUTORIAL_AS.md — End‑to‑End Argumentation Semantics Toolkit

This document explains the small toolkit we’ve assembled around **Dung-style argumentation semantics**,
covering **extraction from natural language**, **semantics solving** (via clingo), and **human‑readable reports**.

It describes what each script does, how they fit together, and how to run them with both **deterministic** inputs
(explicit edges) and **LLM‑inferred** edges.

> TL;DR:
> - **`nl2apx.py`** → turns text blocks into an **AF** + **APX** (with explicit/heuristic/LLM edges).
> - **`af_clingo.py`** → computes **grounded / preferred / stable / complete / stage / semi‑stable** via **clingo**.
> - **`as_pretty.py`** → end‑to‑end **Markdown** report that ties semantics back to **original text**, with provenance tags and optional LLM summary.
> - **`as_end2end.py`** (optional) → end‑to‑end **JSON**‑first pipeline (good for CI and programmatic integrations).
> - **`apxsolve.py`** (optional) → no‑dependency reference solver for small AFs (handy when clingo isn’t available).

---

## 0) Repository layout

Python deps:
- `clingo` (Python package) for `af_clingo.py` and `as_end2end.py` / `as_pretty.py` solving.
- (Optional) `google-genai` (`google.genai`) if you want **LLM edge inference** or **LLM summaries**.

LLM env:
- Set **either** `GEMINI_API_KEY`, **or** `GOOGLE_CLOUD_PROJECT` (+ `GOOGLE_CLOUD_LOCATION`, default `us-central1`).

---

## 1) Input format (text blocks)

Each **argument** is one **block**, separated by a **blank line**. You can optionally provide directives per block:

- `ID: A1` — explicit identifier (otherwise auto‑labels `A1, A2, ...`)
- `ATTACKS: A2, A3` — explicit *attacks* from this block to others (by **ID**)
- `ATTACKS: #2 #3` — same, but using **1‑based indices**

**Example (explicit edges):**
```
ID: A1
We should adopt a 3-day in-office policy to boost collaboration and team cohesion.

ID: A2
ATTACKS: A1
Fully remote work reduces commute time and often increases productivity for focused tasks.
```

**Example (no directives → heuristics/LLM will infer edges):**
```
We should adopt a 3-day in-office policy to boost collaboration and team cohesion.

Fully remote work reduces commute time and often increases productivity for focused tasks.
```

> **Note:** Always keep a blank line between arguments. The parser relies on this to detect blocks.

---

## 2) Natural language → APX (`nl2apx.py`)

**Purpose:** Build a Dung abstract argumentation framework (AF) from text blocks and emit **APX**:
```
arg(a1).
arg(a2).
att(a2,a1).
```

**Key options:**
- `--relation {auto,explicit,none}`
  - `explicit`: trust only `ATTACKS:` lines
  - `auto` (default): use `ATTACKS:` if present, else **heuristics**
  - `none`: disable heuristics but still honor `ATTACKS:` lines
- Heuristics knobs (used when `auto` and no `ATTACKS:` are present):
  - `--jaccard 0.45`, `--min-overlap 3`, and a simple **negation** check
- LLM inference:
  - `--use-llm` (requires env above)
  - `--llm-threshold 0.55` (drop low‑confidence edges)
  - `--llm-mode {augment,override}` (union with explicit/heuristics or replace them)
- `--provenance` adds comments with edge sources.

**Examples:**
```bash
# Deterministic: explicit attacks only
python nl2apx.py arguments.txt --relation explicit --out graph.apx

# Heuristics or LLM (union with explicit by default)
python nl2apx.py arguments.txt --use-llm --llm-threshold 0.6 --out graph.apx --provenance
```

**Provenance comments** show where edges came from:
```
% explicit_edges: [(1,0), (5,0)]
% heuristic_edges: []
% llm_edges: [(2,0), (3,1)]
% final_edges: [(1,0), (2,0), (3,1), (5,0)]
```

---

## 3) Semantics via clingo (`af_clingo.py`)

**Purpose:** Compute standard Dung semantics (no external scripts), using embedded clingo encodings.

**Run directly on an APX file:**
```bash
python af_clingo.py graph.apx                 # all semantics (human-readable)
python af_clingo.py graph.apx --sem preferred # preferred only
python af_clingo.py graph.apx --json          # JSON output
python af_clingo.py graph.apx --dot af.dot    # Graphviz export
```

**Programmatic use:**
```python
from af_clingo import read_apx, grounded, preferred, stable

atoms, atts = read_apx("graph.apx")
G  = grounded(atoms, atts)
PR = preferred(atoms, atts)
ST = stable(atoms, atts)
```

**Semantics included:** grounded, complete, preferred, stable, stage, semi‑stable.  
Preferred is computed by enumerating **admissible** sets via clingo and filtering ⊆‑maximal sets in Python (robust for small/medium AFs).

---

## 4) Pretty, human‑oriented report (`as_pretty.py`)

**Purpose:** One‑shot, **Markdown** report that attaches results to the **original text**.

**What it prints:**
- **Arguments** (`ID → APX atom`) with one‑line text snippets
- **Attacks** with provenance tags: `[exp]`, `[heu]`, `[llm]`
- **Semantics table** (per argument): In Grounded? How many preferred/stable/complete/stage/semi‑stable sets include it? **Defense depth** (#F iterations)
- **Preferred “stance cards”**: each preferred extension + a short preview of its members
- **Why‑not for a target**: grounded **roadblocks** (undefeated attackers) and **persistent/soft** attackers across preferred
- Optional **LLM narrative** (`--llm-summarize`)

**Examples:**
```bash
# Deterministic example (explicit ATTACKS), target = A1
python as_pretty.py arguments.txt --relation explicit --target A1 > report.md

# LLM edge inference + narrative summary
python as_pretty.py examples_llm_messy.txt --use-llm --target A1 --llm-summarize > report.md
```

Open `report.md`—it’s README‑ready.

---

## 5) End‑to‑end runner (`as_end2end.py`) — do we still need it?

**Short answer:** it’s **optional but useful**.

- If you want **human‑friendly output**, use `as_pretty.py`.
- If you want **JSON** for programmatic use/CI (*plus* optional APX/DOT export), `as_end2end.py` is the cleanest wrapper.
- If you’re calling from code, you can also import `nl2apx` + `af_clingo` directly and skip both runners.

**Examples:**
```bash
# LLM extraction → semantics → JSON
python as_end2end.py arguments.txt --use-llm --sem all --json > result.json

# Save APX and DOT in the same shot
python as_end2end.py arguments.txt --use-llm --apx-out graph.apx --dot af.dot
```

So: keep **both** `as_pretty.py` (human) **and** `as_end2end.py` (machine) if you want the best of both worlds.

---

## 6) Optional local solver (`apxsolve.py`)

A tiny, dependency‑free solver (subset enumeration) that computes semantics and prints an **insight panel**—
useful when clingo isn’t available or you want a reference check on small graphs.

```bash
python apxsolve.py graph.apx --sem all
python apxsolve.py graph.apx --insights --target a1 --json
```

---

## 7) Common flows

### A) Deterministic (paper‑friendly)
```
Text (with ATTACKS) → nl2apx --relation explicit → APX
                    → af_clingo → semantics
                    → as_pretty → Markdown report
```

### B) LLM‑assisted (fast prototyping)
```
Text → nl2apx --use-llm (augment/override) → APX (optional)
     → af_clingo → semantics
     → as_pretty --llm-summarize → Markdown report
```

### C) Programmatic (CI & repair loops)
```
Text → as_end2end --json → your debugger/UI
     → show grounded, stances, “why-not”, propose edits, re-run
```

---

## 8) Debugging & gotchas

- **No edges?**  
  Ensure you have **blank lines** between blocks. In explicit mode, `ATTACKS:` must be on the **same line** as its entries (e.g., `ATTACKS: A2, A3`). Multi‑line lists aren’t supported by default.

- **Heuristics not firing?**  
  `--relation auto` uses heuristics **only if no explicit edges** were found anywhere. Use `--relation none` to force heuristics off; or make sure your `ATTACKS:` lines are properly parsed.

- **LLM returned nothing?**  
  Lower `--llm-threshold` (e.g., `0.3`) and check your env vars. Consider `--llm-mode augment` so explicit/heuristics backstop the LLM.

- **Stable is empty?**  
  That’s normal for certain AFs (odd cycles). Check **preferred** or **semi‑stable**.

- **Name confusion in queries:**  
  APX atoms (e.g., `a1`) are sanitized; `as_pretty` and `as_end2end` map atoms back to original `ID`s for display.

---

## 9) Interop: APX/TGF & external reasoners

You can export APX via `nl2apx.py --out` or `as_end2end.py --apx-out` and use any ICCMA‑style solver (CoQuiAAS, μ‑toksia, etc.).  
We keep everything in‑process with clingo for portability, but APX is fully standard if you want to compare engines.

---

## 10) Semantics quick refresher (one paragraph each)

- **Conflict‑free**: no internal attacks.  
- **Admissible**: conflict‑free and defends all its members.  
- **Complete**: admissible, and includes every argument it defends.  
- **Grounded**: the **least** complete extension (skeptical core).  
- **Preferred**: ⊆‑maximal admissible sets (coherent **stances**).  
- **Stable**: conflict‑free and attacks all outside (may not exist).  
- **Stage / Semi‑stable**: choose conflict‑free / complete sets with **maximal range** (good coverage).

---

## 11) Small, reproducible example

`examples_dual_preferred.txt`:
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
python as_pretty.py examples_dual_preferred.txt --relation explicit --target A1 > report.md
python as_end2end.py  examples_dual_preferred.txt --relation explicit --sem all --json > result.json
```

You should see **two preferred stances**, reflecting “ship now” vs “delay,”
and the report will show the small **grounded** core and each stance’s members.

---

## 12) Roadmap ideas

- Record **LLM confidence** per edge in `nl2apx` and carry it into reports (`[llm 0.72]`).  
- Add **CF2 semantics** (SCC‑recursive) for odd cycles.  
- `--self-test` demos and a small **Makefile** for one‑command runs.  
- Optional **Argdown** subset parser (deterministic authoring) → APX.

---

## 13) FAQ

**Do I still need `as_end2end.py` now that I have `as_pretty.py`?**  
Keep both: `as_pretty` is for **humans** (Markdown report), `as_end2end` is for **machines** (JSON + APX/DOT)—and both use the same extraction + clingo backbone.

**Can I skip APX entirely?**  
Yes. You can keep everything in memory: `nl2apx → (ids, attacks)` then directly call `af_clingo` functions.

**How big can I go?**  
`af_clingo` uses clingo under the hood and handles typical small/medium AFs comfortably. For very large AFs, you might want to try specialized ICCMA solvers—but start here; it’s robust and simple.

---

## 14) One‑liners you’ll reuse

```bash
# LLM extraction → pretty report
python as_pretty.py your.txt --use-llm --target A1 > report.md

# Deterministic: explicit edges only
python as_pretty.py your.txt --relation explicit --target A1 > report.md

# Programmatic: everything to JSON
python as_end2end.py your.txt --use-llm --sem all --json > result.json

# Pure solving on an APX
python af_clingo.py graph.apx --sem all --json > sem.json
```

Happy mapping! If you want a `--self-test` or HTML exporter next, say the word and we’ll wire it in.
