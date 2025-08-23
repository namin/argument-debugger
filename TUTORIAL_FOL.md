
# TUTORIAL — Detecting Logical Arguments & Fallacies with FOL (+ Lean Verification)

**Modules covered:** `logical_form.py`, `logical_form_core.py`, `lean_bridge.py`  
**What you’ll learn:** how natural language becomes First-Order Logic (FOL), how ASP flags valid/fallacious patterns, and where Lean certifies steps with tiny proof artifacts.

---

## 0) What you’ll build & run

You’ll run a pipeline that:
1) **Extracts** a FOL-style structure from text (via LLM) into Python dataclasses.
2) **Analyzes** it with **ASP (Clingo)** to detect valid inferences and fallacies.
3) **Optionally verifies** selected steps with Lean by emitting micro-proofs (and saving `.lean` files you can replay).

```
Natural language
   │
   ▼
LLM → LogicalArgument(dataclasses)
   │
   ├─ ASP (Clingo): valid/fallacious patterns
   │
   └─ Lean micro‑verification: “Verified ✅” + proof artifact
```

---

## 1) Prerequisites

- Python 3.10+
- **Clingo** installed (`clingo --version` should work)
- **Lean** installed and on your PATH (for verification; optional to run ASP only)
- LLM provider configured (the repo uses Gemini; set `GEMINI_API_KEY`, etc.)

> If Lean is not installed, the pipeline still runs; you just won’t get “Verified ✅” proof artifacts.

---

## 2) Quickstart (use the provided examples)

Run the Nth example from `examples_logical_form.txt` and show Lean output:

```bash
python logical_form.py --example 1 --lean
```

Typical output (abridged):

```
✅ VALID INFERENCES:
  - Valid universal instantiation: s1 → s3

Lean micro‑verification:
  UI ['s1', 's2'] → s3: Verified ✅
    artifact: /tmp/argdb_lean_ui_.../ui_s3.lean
```

**Interpretation**
- ASP recognized a **valid** pattern (universal instantiation / UI).
- Lean produced a small `.lean` file that **proves** this step (you can open and run it yourself).

> Use `--debug` to print the generated ASP program and model facts.

---

## 3) How the argument becomes FOL (dataclasses)

`logical_form.py` parses LLM output into typed structures:

```python
@dataclass
class FOLAtom:
    predicate: str           # e.g., "bird", "flies", "rains"
    terms: List[str]         # [] for propositional; ["x"] for unary

@dataclass
class FOLFormula:
    type: Literal["atom","not","and","or","implies","iff","forall","exists"]
    atom: Optional[FOLAtom] = None
    left: Optional['FOLFormula'] = None
    right: Optional['FOLFormula'] = None
    variable: Optional[str] = None
    body: Optional['FOLFormula'] = None

@dataclass
class LogicalStatement:
    id: str
    formula: FOLFormula

@dataclass
class LogicalInference:
    from_ids: List[str]      # which statements support this inference
    to_id: str               # the conclusion statement id
    pattern: str             # e.g., "modus_ponens", "universal_instantiation"

@dataclass
class LogicalArgument:
    statements: List[LogicalStatement]
    inferences: List[LogicalInference]
    goal_id: Optional[str] = None
```

**Example mapping**

> “All birds can fly. Penguins are birds. Therefore, penguins can fly.”

- `s1`: `∀x (bird(x) → can_fly(x))`  
- `s2`: `bird(penguins)`  
- `s3`: `can_fly(penguins)`  
- inference: `['s1','s2'] → s3` with pattern `universal_instantiation`

The analyzer converts those to **ASP facts** (plus structural links) for pattern detection.

---

## 4) What ASP checks (detection layer)

ASP (in `build_asp_program`) shows only specific predicates to keep output readable.

**Valid**
- **Modus Ponens**: `P→Q, P ⊢ Q` → `valid_modus_ponens/3`
- **Modus Tollens**: `P→Q, ¬Q ⊢ ¬P` → `valid_modus_tollens/3`
- **Universal Instantiation (UI)**: `∀x(P→Q), P(c) ⊢ Q(c)` → `valid_universal_instantiation/2`
- **Universal syllogism / chain**: `∀x(A→B), ∀x(B→C) ⊢ ∀x(A→C)` → `valid_syllogism/3`
  - Accepts labels `syllogism` or `hypothetical_syllogism`.

**Fallacies**
- **Affirming the consequent**: `P→Q, Q ⊢ P` → `fallacy_affirming_consequent/3`
- **Denying the antecedent**: `P→Q, ¬P ⊢ ¬Q` → `fallacy_denying_antecedent/3`
- **Hasty generalization**: `P(c) ⊢ ∀x P(x)` → `fallacy_hasty_generalization/2`

> The rules rely on structure: e.g., `quantifier(_, S, "forall", ...)` to detect ∀-statements, `binary(_, S, "implies", ...)` for →, and `negation(_, S, ...)` for ¬.

<details>
<summary><strong>Copy‑paste: updated ASP pattern rules</strong></summary>

```prolog
% Helper: inference cites two premises (order-insensitive)
inference_from_both(To, S1, S2) :-
    inference_from(To, S1),
    inference_from(To, S2),
    S1 != S2.

% Valid
valid_modus_ponens(Simp, Sprem, Sgoal) :-
    binary(_, Simp, "implies", _, _),
    statement(Sprem),
    statement(Sgoal),
    inference_from_both(Sgoal, Simp, Sprem),
    inference_pattern(Sgoal, "modus_ponens").

valid_modus_tollens(Simp, SnegQ, SnegP) :-
    binary(_, Simp, "implies", _, _),
    negation(_, SnegQ, _),
    negation(_, SnegP, _),
    inference_from_both(SnegP, Simp, SnegQ),
    inference_pattern(SnegP, "modus_tollens").

valid_universal_instantiation(Sforall, Sgoal) :-
    quantifier(_, Sforall, "forall", _, _),
    statement(Sgoal),
    inference_from_both(Sgoal, Sforall, Sinst),
    statement(Sinst),
    inference_pattern(Sgoal, "universal_instantiation").

valid_syllogism(S1, S2, S3) :-
    quantifier(_, S1, "forall", _, _),
    quantifier(_, S2, "forall", _, _),
    quantifier(_, S3, "forall", _, _),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "syllogism").

valid_syllogism(S1, S2, S3) :-
    quantifier(_, S1, "forall", _, _),
    quantifier(_, S2, "forall", _, _),
    quantifier(_, S3, "forall", _, _),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "hypothetical_syllogism").

valid_existential_generalization(Sinst, Sexists) :-
    fol_atom(_, Sinst, _),
    quantifier(_, Sexists, "exists", _, _),
    inference_from(Sexists, Sinst),
    inference_pattern(Sexists, "existential_generalization").

% Fallacies
fallacy_affirming_consequent(Simp, Sq, Sp) :-
    binary(_, Simp, "implies", _, _),
    statement(Sq),
    statement(Sp),
    inference_from_both(Sp, Simp, Sq),
    inference_pattern(Sp, "affirming_consequent").

fallacy_denying_antecedent(Simp, SnegP, SnegQ) :-
    binary(_, Simp, "implies", _, _),
    negation(_, SnegP, _),
    negation(_, SnegQ, _),
    inference_from_both(SnegQ, Simp, SnegP),
    inference_pattern(SnegQ, "denying_antecedent").

fallacy_hasty_generalization(Sinst, Sforall) :-
    fol_atom(_, Sinst, _),
    has_const(_, _, _),
    quantifier(_, Sforall, "forall", _, _),
    inference_from(Sforall, Sinst),
    inference_pattern(Sforall, "hasty_generalization").

#show valid_modus_ponens/3.
#show valid_modus_tollens/3.
#show valid_universal_instantiation/2.
#show valid_syllogism/3.
#show valid_existential_generalization/2.
#show fallacy_affirming_consequent/3.
#show fallacy_denying_antecedent/3.
#show fallacy_hasty_generalization/2.
```
</details>

---

## 5) Where Lean comes in (verification layer)

Lean **certifies** select steps by producing a tiny program that type‑checks to a proof.

### 5.1 UI (Universal Instantiation)
- Pattern: `∀x (P x → Q x)` and `P c` ⊢ `Q c`
- The emitted Lean proof (ASCII, works in Lean 4/3):

```lean
/- Auto-generated universal instantiation check -/
axiom T : Type
axiom P : T -> Prop
axiom Q : T -> Prop
axiom c : T

theorem ui_s3 (h : forall x : T, P x -> Q x) (hp : P c) : Q c :=
  h c hp
```

**When you’ll see “Verified ✅”**  
If your FOL conforms: the ∀ body is an implication `P x → Q x`, both `P/Q` unary, and the premise/goal share the same constant.

### 5.2 Modus Tollens
- Pattern: `P→Q` and `¬Q` ⊢ `¬P`
- Emitted proof:

```lean
/- Auto-generated Modus Tollens check -/
axiom P : Prop
axiom Q : Prop

theorem mt_s3 (hPQ : P -> Q) (hnQ : Q -> False) : P -> False :=
  fun hP => hnQ (hPQ hP)
```

### 5.3 Propositional Chains
- Pattern: chain of single‑premise implications from a fact to a goal (e.g., `P→Q, Q→R, P ⊢ R`).
- The generator builds a term proof by composing the functions.

> All Lean artifacts are saved under a temp directory and the path is printed.

---

## 6) Hands‑on: five canonical examples

1) **UI (valid)** — `∀x (bird→can_fly)`, `bird(penguins)` ⇒ `can_fly(penguins)`  
   - ASP: prints `Valid universal instantiation`  
   - Lean: **Verified ✅** (UI)

2) **Affirming the consequent (fallacy)** — `rains→wet`, `wet` ⇒ `rains`  
   - ASP: prints fallacy lines  
   - Lean: no chain proof (as expected)

3) **Modus Tollens (valid)** — `study_hard→pass`, `¬pass` ⇒ `¬study_hard`  
   - ASP: prints `Valid modus tollens`  
   - Lean: **Verified ✅** (MT)

4) **Existential misstep (no pattern)** — `∃x(student∧athlete)`, `student(john)` ⇒ `athlete(john)`  
   - ASP: no pattern fires (needs witness management)

5) **∀‑chain (valid)** — `∀x(mammal→animal)`, `∀x(dog→mammal)` ⇒ `∀x(dog→animal)`  
   - ASP: fires if labeled `syllogism` or `hypothetical_syllogism`  
   - Lean: optional emitter exists; requires matching predicates under ∀

---

## 7) Writing your own examples

Create a small block in your examples file (blank line separated):

```
All cats are mammals.
All mammals are animals.
Therefore, all cats are animals.
```

Then run:

```bash
python logical_form.py --example N --lean
```

or

```bash
python logical_form.py --file cat_file.txt --lean
```

If the LLM output labels the inference appropriately, ASP will print the match; Lean will verify when an emitter exists for that pattern.

> Tip: phrasing matters. Prefer crisp, textbook-like sentences for best FOL extraction.

---

## 8) Extending the system

**Add a detection rule (ASP)**
1. Choose a name like `valid_constructive_dilemma/…` or `fallacy_…`.
2. Write a rule that matches your structure (`binary`, `quantifier`, `negation`, etc.).
3. Add it to the `#show` list so it appears in output.
4. Update the Python post‑processing to format the message.

**Add a verification (Lean)**
1. Implement a minimal ASCII proof function in `lean_bridge.py`.
2. Call it in `logical_form.py` when you see the corresponding `pattern`.
3. Print **Verified/Not verified** and the artifact path.

> Keep proofs small and constructive—prefer **term proofs** over tactic-heavy scripts for compatibility and clarity.

---

## 9) Key design constraints

- **Soundness first:** we don’t conflate multi‑premise steps into single edges for chain proofs.  
- **Explicit quantifiers:** UI and ∀‑chain rely on the quantifier structure being present in the FOL.  
- **Artifacts you can trust:** every **Verified ✅** comes with a `.lean` file you can replay independently.

---

Happy debugging — and if you add a new pattern or micro‑proof emitter, consider contributing it back!
