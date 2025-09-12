# ARGIR DESIGN

**Single‑Parse Argument Strengthener — End‑to‑End Design**

> *Goal:* one semantic parse of a natural‑language (NL) argument into a shared intermediate representation (**ARG‑IR**) that supports both **within‑link** strengthening (warrants, strict proof certificates) and **across‑graph** reasoning (attacks/defenses under argumentation semantics). The system can optionally **certify strict steps** (E prover / Lean later), **compile to an abstract argumentation framework (AF)**, and compute plans to **minimally strengthen** the target claim.

---

## 0) TL;DR / How to run

```bash
# optional: keep the TPTP problems E sees
export CERT_OUTDIR=out/certs

# Single file (end-to-end)
python -B strengthener_cli.py --file arguments_nl/01_syllogism_socrates.txt --e2e --synth-fol

# Whole folder (end-to-end) + dump parsed IRs
python -B strengthener_cli.py --dir arguments_nl --e2e --synth-fol --dump-ir out/
```

**Strict patterns** (Syllogism, Chained Syllogism, Modus Ponens) are recognized, **certified with E**, CQ obligations are **waived**, and targets are **Accepted** with **Cost: 0**.
**Defeasible patterns** (expert opinion, causal, analogical, statistical, value) remain defeasible: the planner answers critical questions (CQs) and counters attacks (typical **Cost: 2**).

---

## 1) System overview

```
 NL text(s)
    │
    ▼
 (optional LLM)             Deterministic               External solvers
 ┌────────────────┐   ┌────────────────────┐   ┌──────────────────────────┐
 │ nl_to_argir.py │ → │  fol_synth.py      │ → │ certify_strict.py        │
 │ (parse to       │   │  (strict FOL from │   │ (E prover now; Lean later)│
 │  ARG‑IR)        │   │   NL patterns)    │   └──────────────┬───────────┘
 └────────┬────────┘   └──────────┬────────┘                  │ marks
          │                       │                           │ inf.certified=True
          ▼                       ▼                           │
      ARG‑IR (one parse) ─────────────────────────────────────┘
          │
          ▼
  compile_to_af.py → AF (Dung) with default doubts + CQ obligations
          │
          ├── af_semantics.py → grounded extension / status(Accepted/Not)
          │
          ├── enforcement_optimal.py (clingo)  ←┐
          │        OR enforcement_greedy.py     ├─ propose minimal edit plan
          ▼                                      │  (answer CQs, counter attackers)
    pedagogy.py → explain acceptance delta      ←┘
```

**One parse** (ARG‑IR) powers both sides:

* **Within a link**: unmet CQs / deductive checks become obligation undercutters; strict steps can carry **FOL** and be **certified**.
* **Across the graph**: AF edges capture **attacks/defenses**; we reason with **grounded extension**.

---

## 2) ARG‑IR: the shared intermediate representation

A simplified sketch of the schema (JSON):

```json
{
  "propositions": [
    { "id": "p1", "text": "All humans are mortal." },
    { "id": "p2", "text": "Socrates is human." },
    { "id": "p3", "text": "Therefore, Socrates is mortal." }
  ],
  "inferences": [
    {
      "id": "i1",
      "from_ids": ["p1", "p2"],
      "to": "p3",
      "rule": "defeasible | strict",
      "type": "deductive | inductive | causal | practical | ...",
      "scheme": "Syllogism | ModusPonens | ... (optional)",
      "fol": {
        "premises": ["forall x. human(x) -> mortal(x)", "human(socrates)"],
        "conclusion": "mortal(socrates)",
        "symbols": {}
      },
      "meta": { "certified": false }
    }
  ],
  "targets": ["p3"]
}
```

**Key choices**

* **Single representation** is rich enough for both **within‑link** (CQs, strict FOL) and **across‑graph** (attacks) analysis.
* **FOL payload** is optional and only for **strict steps** we can certify.
* **Targets** list the conclusions we aim to make **Accepted** under grounded semantics.

---

## 3) End‑to‑end pipeline (with who does what)

| Step                 | File(s)                                            | What it does                                                         |    Uses LLM? |    Deterministic logic? |       External tool? |
| -------------------- | -------------------------------------------------- | -------------------------------------------------------------------- | -----------: | ----------------------: | -------------------: |
| NL → ARG‑IR          | `nl_to_argir.py` (calls `llm.py` if configured)    | Segment NL, identify premises/inferences/targets                     | **Optional** | ✅ (fallback heuristics) |                    — |
| Strict FOL synth     | `fol_synth.py`                                     | Recognize strict patterns and attach `fol` + `rule="strict"`         |           No |                       ✅ |                    — |
| TPTP emission        | `tptp_emit.py`                                     | Convert mini‑FOL to TPTP/FOF                                         |           No |                       ✅ |                    — |
| Strict certification | `certify_strict.py`                                | Run **E prover** (or Lean later); set `inf.certified=True`           |           No |                       ✅ |                **E** |
| Compile AF           | `compile_to_af.py`                                 | Build Dung AF with **default doubt** and **obligation undercutters** |           No |                       ✅ |                    — |
| Waive obligations    | (helper inside `strengthener_cli.py`)              | If `inf.certified`, remove CQ/obligation nodes for that step         |           No |                       ✅ |                    — |
| Semantics            | `af_semantics.py`                                  | Compute **grounded extension**, `status()`                           |           No |                       ✅ |                    — |
| Planning             | `enforcement_optimal.py` / `enforcement_greedy.py` | Find minimal edit plan (add “answer:” or “counter:” nodes/edges)     |           No |                       ✅ | **clingo** (optimal) |
| Pedagogy             | `pedagogy.py`                                      | Explain why acceptance changed                                       |           No |                       ✅ |                    — |
| CLI                  | `strengthener_cli.py`                              | Glue, flags (`--e2e`, `--synth-fol`, `--certify`, `--optimal`, etc.) |           No |                       ✅ |                    — |

**Notes**

* If you disable the LLM, `nl_to_argir.py` uses conservative heuristics; you can later re‑enable LLM parsing and repairing (via your existing `llm.py` integration).
* **Within‑link** strengthening uses **CQs** as obligations; the planner can add “answer:” nodes that **attack those obligation nodes**.
* **Across‑graph** strengthening adds “counter:” nodes that **attack attackers** (e.g., `neg:p3`, explicit opposing claims).

---

## 4) Abstract Framework (AF) and obligations

### AF nodes and special conventions

* **Claims**: `pX` (from ARG‑IR `propositions`)
* **Inferences**: `iX` (edges in IR become support/defense; exact encoding is done in `compile_to_af.py`)
* **Default doubt**: `neg:pX` — a standing attacker of each target claim
* **Obligation undercutters** (CQs/deductive checks):

  * `cq:iX:premises_present`
  * `cq:iX:rule_applicable`
  * `cq:iX:term_consistency`
  * (legacy) `ob:iX:*`
* **Answers** (proposed repairs): `answer: …` nodes that **attack** the relevant `cq:iX:*`
* **Counters**: `counter: …` nodes that **attack** `neg:pX` or an explicit attacker claim `pY`

### Semantics

* We use **Dung (1995)** **grounded extension** via `af_semantics.py`.
* The CLI reports **Status: Accepted / Not accepted** for the target node and prints the grounded extension size.

### Certification waiver (strict steps)

* After `E` certifies an inference (sets `inf.certified=True`), the CLI helper **removes** all `cq:iX:*` / `ob:iX:*` nodes and incident edges targeting `iX`. This models: *“a strict proof needs no warrant.”*
* Result: strict, certified arguments are **Accepted** without edits (**Cost: 0**).

---

## 5) Planning: optimal vs greedy

* **Optimal**: `enforcement_optimal.py` uses **clingo** to select the **minimum‑cost** edit set (add minimal answers/counters) so that the **target becomes Accepted** under grounded semantics.

  * CLI flag: `--optimal` or automatically under `--e2e`
  * If clingo is not available, the CLI **falls back** to greedy.

* **Greedy**: `enforcement_greedy.py` supports:

  * **Within‑first** (`--within-first`): answer obligations first, then across‑graph counters
  * **Across‑first**: counter attackers first, then answer remaining obligations
  * **Budget** (`--budget N`): cap the number of edit steps

Both planners produce a **plan**: a list of added nodes/attacks and a short rationale, followed by an **explanation of acceptance delta** via `pedagogy.py`.

---

## 6) CLI UX and flags

```
python -B strengthener_cli.py [INPUT] [FLOW] [OPTIONS]

Inputs (pick one):
  --text "A. B. Therefore C."
  --file path/to/argument.txt
  --argir path/to/argument.argir.json
  --dir path/to/dir   # .txt/.md (NL) and/or .json (ARG‑IR)

Flow switches:
  --e2e         # synth-fol (if available) + certify + optimal (fallback to greedy)
  --synth-fol   # try to synthesize FOL for strict patterns from NL
  --certify     # attempt E prover (or future Lean) certificates for strict steps
  --optimal     # use clingo optimal enforcement

Greedy options:
  --within-first
  --budget N

Other:
  --target "p3"  # pick claim id or substring
  --dump-ir out/ # write parsed ARG‑IR (file or dir)
```

**Environment variables**

* `CERT_OUTDIR=out/certs` — if set, `certify_strict.py` will dump the exact TPTP problem each strict step was proved against (handy for debugging).

---

## 7) Files & responsibilities (quick reference)

| File                     | Purpose                                                                                                 | Notes / Dependencies                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `strengthener_cli.py`    | Orchestrates the full pipeline; adds waiver for certified strict steps; provides `--e2e` and batch runs | Calls synth/certify/compile/solve/explain                              |
| `nl_to_argir.py`         | Parse NL into ARG‑IR (propositions, inferences, target)                                                 | May call `llm.py` (optional) or use heuristics                         |
| `llm.py`                 | (Optional) LLM wrapper for parsing/repairs                                                              | Your existing utility                                                  |
| `arg_ir.py`              | Data classes & loader for ARG‑IR JSON                                                                   | Holds `FOLPayload`, `Inference`, `Proposition`, etc.                   |
| `fol_synth.py`           | Deterministic **strict pattern** recognizer; attaches `fol` and marks `rule="strict"`                   | No LLM; handles Syllogism / Chained / MP / MT                          |
| `tptp_emit.py`           | Emits TPTP/FOF from mini‑FOL payloads                                                                   | No LLM; ensures variables, quantifiers, and connectives are E‑friendly |
| `certify_strict.py`      | Runs **E prover**; sets `inf.certified=True` on success                                                 | Requires `eprover` in PATH; uses `CERT_OUTDIR`                         |
| `compile_to_af.py`       | Builds AF (nodes, attacks, labels) from ARG‑IR                                                          | Includes **default doubt** and **obligation undercutters**             |
| `af_semantics.py`        | Grounded extension & node status                                                                        | Dung grounded                                                          |
| `enforcement_optimal.py` | ASP encoding for **optimal enforcement**                                                                | Requires **clingo**                                                    |
| `enforcement_greedy.py`  | Greedy strengthening (within / across)                                                                  | No external deps                                                       |
| `pedagogy.py`            | Natural‑language explanation of acceptance delta                                                        | Uses current/after grounded extensions                                 |
| `examples/`              | Example ARG‑IR JSONs                                                                                    | Demonstrations                                                         |
| `arguments_nl/`          | NL examples used by `--dir` batch runs                                                                  | Demonstrations                                                         |

---

## 8) What uses LLMs vs logic?

* **LLM** (optional):

  * `nl_to_argir.py` can use `llm.py` to parse free‑form text into propositions/inferences/targets.
  * (Future) generating substantive **answer:** evidence or **counter:** content; currently plans insert templated text.
* **Logical / deterministic**:

  * `fol_synth.py` (regex & normalization)
  * `tptp_emit.py` (mini‑FOL → TPTP)
  * `certify_strict.py` (driver; E is the external reasoner)
  * `compile_to_af.py`, `af_semantics.py`
  * `enforcement_optimal.py` (ASP + clingo), `enforcement_greedy.py`
  * `pedagogy.py`

---

## 9) Examples

### A) Strict syllogism (Socrates)

```
[debug] strict i1 scheme= Syllogism
  premises: ['forall x. human(x) -> mortal(x)', 'human(socrates)']
  conclusion: mortal(socrates)

=== Strict-step Certification (E2E) ===
i1: eprover → OK

=== Initial (Grounded) ===
Status: Accepted

--- Optimal Plan (E2E) ---
Cost: 0
```

### B) Defeasible (expert opinion)

No strict FOL recognized; AF shows unmet CQs. Optimal plan typically:

* add one **answer:** node attacking a CQ (e.g., “premises\_present” or “rule\_applicable”)
* add one **counter:** node attacking `neg:p`

**Cost: 2** → **Accepted**.

---

## 10) Extensibility

### Add a new strict pattern

* Edit `fol_synth.py`. Follow the existing pattern helpers:

  * parse premises/conc text
  * if matched, fill `FOLPayload(premises=[...], conclusion="...")`
  * set `inf.rule="strict"`, `inf.type="deductive"`, `inf.scheme="..."`

*Example skeleton:*

```python
def _try_newpattern_local(prem_texts, conc_text):
    # parse & check; return FOLPayload or None
    return None

# In synth_fol(): insert into the OR-chain before the global fallbacks
fol = (_try_newpattern_local(prem_local, conc_text) or
       ... existing checks ...)
```

### Add/modify CQs (obligations)

* The creation of `cq:iX:*` nodes happens inside `compile_to_af.py` (based on `inf.rule`, `inf.type`, etc.).
* To change which obligations appear for a given scheme, modify the mapping there.
* The waiver logic is **centralized** in the CLI helper; it prunes any `cq:iX:*`/`ob:iX:*` for `inf.certified`.

### Swap/augment solvers

* **E prover** is currently used for first‑order strict steps. You can add a Lean pathway in `certify_strict.py` (parallel runner; mark `tool="lean"` on success).
* **clingo** can be swapped for another ASP/SAT solver by re‑implementing `optimal_enforce`.

---

## 11) Testing & reproducibility

* Clear caches after code edits:

  ```bash
  find . -name "__pycache__" -type d -exec rm -rf {} +
  ```
* Verify E prover:

  ```bash
  eprover --version
  ```
* Verify clingo (if using `--optimal` or `--e2e`):

  ```bash
  clingo --version
  ```
* Sanity: `arguments_nl/01_syllogism_socrates.txt` should produce `E → OK` and **Cost: 0**.
* Batch: `./run_batch.sh` (or the `--dir` command) should accept strict examples at **Cost: 0** and defeasible ones at **Cost: 2**.

---

## 12) Known limitations / future work

* **FOL synth**: handles common strict patterns (unary predicates, simple implications). Not a general semantic parser.
* **Defeasible schemes**: we don’t attempt strict proof. A future step could add structured abductive checks or probabilistic scoring.
* **Lean certificates**: planned; the infrastructure and waiver policy already support multiple tools.
* **Semantics**: grounded only; adding preferred/stable would be straightforward (`af_semantics.py`).
* **Only‑if**: often expresses constraints rather than entailments; we keep it defeasible by default.
* **Existentials** (“some X …”): currently require explicit instances/premises; could add config to assume non‑emptiness for selected classes.

---

## 13) Appendix: design decisions that matter

* **One parse to rule them all**: NL→ARG‑IR is the single source of truth for both within‑link and across‑graph reasoning.
* **Certification waives obligations**: strict, proved steps do not carry CQ debt, reflecting mathematical warrants.
* **Default doubt**: every target faces a “why believe this?” attacker, making defense explicit.
* **Edits are explicit**: answer/counter nodes are first‑class and auditable; they double as pedagogical feedback.

---

**Maintainers’ checklist**

* [ ] `eprover` on PATH (for `--certify` / `--e2e`)
* [ ] `clingo` on PATH (for `--optimal` / `--e2e`, otherwise greedy fallback)
* [ ] (optional) `CERT_OUTDIR` set for TPTP dumps
* [ ] `--dir` batch run completes: strict → Cost 0, defeasible → Cost 2

---
