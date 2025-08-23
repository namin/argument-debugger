# Logical Form Analysis
Loaded 5 arguments from examples_logical_form.txt

# EXAMPLE 1
All birds can fly.
Penguins are birds.
Therefore, penguins can fly.

Extracting logical form...

Logical Structure:
  s1: ∀x((bird(x) → can_fly(x)))
  s2: bird(penguins)
  s3: can_fly(penguins)

Inferences:
  ['s1', 's2'] → s3 (universal_instantiation)

Analyzing with ASP...

✅ VALID INFERENCES:
  - Valid universal instantiation: s1 → s3

Verifying with Lean...

Lean micro‑verification:
  UI ['s1', 's2'] → s3: Verified ✅
    artifact: /var/folders/70/m4vcj5vd76bbzsyc_kr0mqr80000gp/T/argdb_lean_ui_99qjx5pj/ui_s3.lean

# EXAMPLE 2
If it rains, the ground gets wet.
The ground is wet.
Therefore, it rained.

Extracting logical form...

Logical Structure:
  s1: (rains() → wet())
  s2: wet()
  s3: rains()

Inferences:
  ['s1', 's2'] → s3 (affirming_consequent)

Analyzing with ASP...

❌ LOGICAL ISSUES FOUND:
  - Fallacy - Affirming the consequent: [s1, s2] → s3
  - Invalid inference pattern 'affirming_consequent' for statement s3

Verifying with Lean...

Lean micro‑verification:
  chain goal=s3: Not verified ❌
    note: No implication chain from facts to goal

# EXAMPLE 3
If you study hard, you will pass.
You didn't pass.
Therefore, you didn't study hard.

Extracting logical form...

Logical Structure:
  s1: (study_hard() → pass())
  s2: ¬pass()
  s3: ¬study_hard()

Inferences:
  ['s1', 's2'] → s3 (modus_tollens)

Analyzing with ASP...

✅ VALID INFERENCES:
  - Valid modus tollens: [s1, s2] → s3

Verifying with Lean...

Lean micro‑verification:
  MT ['s1', 's2'] → s3: Verified ✅
    artifact: /var/folders/70/m4vcj5vd76bbzsyc_kr0mqr80000gp/T/argdb_lean_mt_2cx0o096/mt_s3.lean
  (nothing to verify for this example)

# EXAMPLE 4
Some students are athletes.
John is a student.
Therefore, John is an athlete.

Extracting logical form...

Logical Structure:
  s1: ∃x((student(x) ∧ athlete(x)))
  s2: student(john)
  s3: athlete(john)

Inferences:

Analyzing with ASP...

⚠️ No formal logical patterns detected

Verifying with Lean...

Lean micro‑verification:
  (nothing to verify for this example)

# EXAMPLE 5
All mammals are animals.
All dogs are mammals.
Therefore, all dogs are animals.

Extracting logical form...

Logical Structure:
  s1: ∀x((mammal(x) → animal(x)))
  s2: ∀x((dog(x) → mammal(x)))
  s3: ∀x((dog(x) → animal(x)))

Inferences:
  ['s1', 's2'] → s3 (hypothetical_syllogism)

Analyzing with ASP...

⚠️ No formal logical patterns detected

Verifying with Lean...

Lean micro‑verification:
  ∀-chain ['s1', 's2'] → s3: Not verified ❌
    note: predicate mismatch in ∀-chain
  (nothing to verify for this example)
