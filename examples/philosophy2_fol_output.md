# Logical Form Analysis
Loaded 4 arguments from examples/philosophy2.txt

# EXAMPLE 1
No belief is rationally justified.
But if that's true, then the belief 'no belief is rationally justified' is itself not justified.
So if skepticism is true, we shouldn't believe skepticism.
Therefore, skepticism defeats itself.

Extracting logical form...

Logical Structure:
  s1: SkepticismTruth()
  s2: (SkepticismTruth() → ¬SkepticismBeliefIsJustified())
  s_implicit1: (¬SkepticismBeliefIsJustified() → ¬ShouldBelieveSkepticism())
  s3: (SkepticismTruth() → ¬ShouldBelieveSkepticism())
  s_implicit2: ((SkepticismTruth() → ¬ShouldBelieveSkepticism()) → SkepticismDefeatsItself())
  s4: SkepticismDefeatsItself()

Inferences:
  ['s2', 's_implicit1'] → s3 (hypothetical_syllogism)
  ['s3', 's_implicit2'] → s4 (modus_ponens)

Analyzing with ASP...

✅ VALID INFERENCES:
  - Valid modus ponens: [s3, s_implicit2] → s4
  - Valid modus ponens: [s_implicit2, s3] → s4

Verifying with E (global entailment)…
  SZS status: Theorem
  Used premises: ['s2', 's_implicit1', 's_implicit2']
  --- TSTP proof ---
fof(s_implicit2, axiom, ((skepticismTruth=>~(shouldBelieveSkepticism))=>skepticismDefeatsItself)).
fof(conj, conjecture, skepticismDefeatsItself).
fof(s2, axiom, (skepticismTruth=>~(skepticismBeliefIsJustified))).
fof(s_implicit1, axiom, (~(skepticismBeliefIsJustified)=>~(shouldBelieveSkepticism))).
fof(c_0_4, plain, ((skepticismTruth=>~shouldBelieveSkepticism)=>skepticismDefeatsItself), inference(fof_simplification,[],[s_implicit2])).
fof(c_0_5, negated_conjecture, ~skepticismDefeatsItself, inference(fof_simplification,[],[inference(assume_negation,[],[conj])])).
fof(c_0_6, plain, (skepticismTruth=>~skepticismBeliefIsJustified), inference(fof_simplification,[],[s2])).
fof(c_0_7, plain, ((skepticismTruth|skepticismDefeatsItself)&(shouldBelieveSkepticism|skepticismDefeatsItself)), inference(distribute,[],[inference(fof_nnf,[],[c_0_4])])).
fof(c_0_8, negated_conjecture, ~skepticismDefeatsItself, inference(fof_nnf,[],[c_0_5])).
fof(c_0_9, plain, (~skepticismBeliefIsJustified=>~shouldBelieveSkepticism), inference(fof_simplification,[],[s_implicit1])).
fof(c_0_10, plain, (~skepticismTruth|~skepticismBeliefIsJustified), inference(fof_nnf,[],[inference(fof_nnf,[],[c_0_6])])).
cnf(c_0_11, plain, (skepticismTruth|skepticismDefeatsItself), inference(split_conjunct,[],[c_0_7])).
cnf(c_0_12, negated_conjecture, (~skepticismDefeatsItself), inference(split_conjunct,[],[c_0_8])).
fof(c_0_13, plain, (skepticismBeliefIsJustified|~shouldBelieveSkepticism), inference(fof_nnf,[],[inference(fof_nnf,[],[c_0_9])])).
cnf(c_0_14, plain, (shouldBelieveSkepticism|skepticismDefeatsItself), inference(split_conjunct,[],[c_0_7])).
cnf(c_0_15, plain, (~skepticismTruth|~skepticismBeliefIsJustified), inference(split_conjunct,[],[c_0_10])).
cnf(c_0_16, plain, (skepticismTruth), inference(sr,[],[c_0_11, c_0_12])).
cnf(c_0_17, plain, (skepticismBeliefIsJustified|~shouldBelieveSkepticism), inference(split_conjunct,[],[c_0_13])).
cnf(c_0_18, plain, (shouldBelieveSkepticism), inference(sr,[],[c_0_14, c_0_12])).
cnf(c_0_19, plain, (~skepticismBeliefIsJustified), inference(cn,[],[inference(rw,[],[c_0_15, c_0_16])])).
cnf(c_0_20, plain, ($false), inference(sr,[],[inference(cn,[],[inference(rw,[],[c_0_17, c_0_18])]), c_0_19]), ['proof']).

  --- Generic digest ---
Generic proof steps:
  [c_0_17] skepticismBeliefIsJustified | ~shouldBelieveSkepticism (from inference, split_conjunct)
  [c_0_18] shouldBelieveSkepticism (from inference, sr)
  [c_0_19] ~skepticismBeliefIsJustified (from inference, cn, inference, rw)
  ── resolve/simplify → ⊥

Verifying each inference step with E…
  ['s2', 's_implicit1'] ⊢ s3 [hypothetical_syllogism]: Theorem
  ['s3', 's_implicit2'] ⊢ s4 [modus_ponens]: Theorem

Verifying with Lean...

Lean micro‑verification:
  chain goal=s4: Not verified ❌
    note: No implication chain from facts to goal
  ∀-chain ['s2', 's_implicit1'] → s3: Not verified ❌
    note: could not line up ∀-chain components

# EXAMPLE 2
Someone with $1 million is rich.
If someone with $X is rich, then someone with $X - 1 is also rich.
(After all, one dollar can't make the difference between rich and not-rich!)
Therefore, someone with $999,999 is rich.
By repeated application: someone with $1 is rich.
But that's absurd - so our concept of 'rich' is incoherent.

Extracting logical form...

Logical Structure:
  s1: Rich(Million)
  s2: ∀x(∀y(((Rich(x) ∧ IsOneLess(y,x)) → Rich(y))))
  s_fact_999999: IsOneLess(NineNineNineNineNineNine,Million)
  s3: Rich(NineNineNineNineNineNine)
  s4: Rich(One)

Inferences:
  ['s1', 's2', 's_fact_999999'] → s3 (universal_instantiation)
  ['s1', 's2'] → s4 (universal_instantiation)

Analyzing with ASP...

✅ VALID INFERENCES:
  - Valid universal instantiation: [s2, s1] → s3
  - Valid universal instantiation: [s2, s1] → s4

Verifying with E (global entailment)…
  SZS status: CounterSatisfiable
  Used premises: ['s1', 's2', 's_fact_999999']
  --- TSTP proof ---
fof(conj, conjecture, rich(one)).
fof(s2, axiom, ![X1, X2]:(((rich(X1)&isOneLess(X2,X1))=>rich(X2)))).
fof(s_fact_999999, axiom, isOneLess(nineNineNineNineNineNine,million)).
fof(s1, axiom, rich(million)).
fof(c_0_4, negated_conjecture, ~rich(one), inference(fof_simplification,[],[inference(assume_negation,[],[conj])])).
fof(c_0_5, plain, ![X3, X4]:((~rich(X3)|~isOneLess(X4,X3)|rich(X4))), inference(fof_nnf,[],[inference(variable_rename,[],[inference(fof_nnf,[],[s2])])])).
fof(c_0_6, negated_conjecture, ~rich(one), inference(fof_nnf,[],[c_0_4])).
cnf(c_0_7, plain, (rich(X2)|~rich(X1)|~isOneLess(X2,X1)), inference(split_conjunct,[],[c_0_5]), ['final']).
cnf(c_0_8, plain, (isOneLess(nineNineNineNineNineNine,million)), inference(split_conjunct,[],[s_fact_999999]), ['final']).
cnf(c_0_9, plain, (rich(million)), inference(split_conjunct,[],[s1]), ['final']).
cnf(c_0_10, negated_conjecture, (~rich(one)), inference(split_conjunct,[],[c_0_6]), ['final']).
cnf(c_0_11, plain, (rich(nineNineNineNineNineNine)), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_7, c_0_8]), c_0_9])]), ['final']).

  --- Generic digest ---
No refutation (CounterSatisfiable). The axioms are consistent with the negated goal.
  Unit clauses: isOneLess(nineNineNineNineNineNine,million), rich(million), ~rich(one), rich(nineNineNineNineNineNine)
  (Nothing forces a contradiction; the goal is not entailed.)

Verifying each inference step with E…
  ['s1', 's2', 's_fact_999999'] ⊢ s3 [universal_instantiation]: Theorem
  ['s1', 's2'] ⊢ s4 [universal_instantiation]: CounterSatisfiable

Verifying with Lean...

Lean micro‑verification:
  UI ['s1', 's2', 's_fact_999999'] → s3: Not verified ❌
    note: ∀ body is not an implication
  UI ['s1', 's2'] → s4: Not verified ❌
    note: ∀ body is not an implication

# EXAMPLE 3
It's possible that a maximally great being exists.
A maximally great being would have necessary existence (exists in all possible worlds).
If it's possible that a necessary being exists, then that being exists in at least one possible world.
But if a necessary being exists in any possible world, it exists in all possible worlds.
Therefore, a maximally great being exists in the actual world.

Extracting logical form...

Logical Structure:
  s1: ∃w((W(w) ∧ ∃x((MG(x) ∧ Exists(x,w)))))
  s2: ∀x((MG(x) → ∀w((W(w) → Exists(x,w)))))
  s3: (∃w_p((W(w_p) ∧ ∃y((∀w_k((W(w_k) → Exists(y,w_k))) ∧ Exists(y,w_p))))) → ∃y((∀w_k((W(w_k) → Exists(y,w_k))) ∧ ∃w_q((W(w_q) ∧ Exists(y,w_q))))))
  s4: ∀y(((∀w_k((W(w_k) → Exists(y,w_k))) ∧ ∃w_r((W(w_r) ∧ Exists(y,w_r)))) → ∀w_s((W(w_s) → Exists(y,w_s)))))
  s5: ∃x((MG(x) ∧ Exists(x,w_actual)))
  s_int1: ∃x((MG(x) ∧ ∀w((W(w) → Exists(x,w)))))

Inferences:
  ['s1', 's2'] → s_int1 (deduction)
  ['s_int1'] → s5 (deduction)

Analyzing with ASP...

⚠️ No formal logical patterns detected

Verifying with E (global entailment)…
  SZS status: CounterSatisfiable
  Used premises: ['s1', 's2', 's3', 's4']
  --- TSTP proof ---
fof(s2, axiom, ![X2]:((mG(X2)=>![X1]:((w(X1)=>exists(X2,X1)))))).
fof(s1, axiom, ?[X1]:((w(X1)&?[X2]:((mG(X2)&exists(X2,X1)))))).
fof(s3, axiom, (?[X3]:((w(X3)&?[X4]:((![X5]:((w(X5)=>exists(X4,X5)))&exists(X4,X3)))))=>?[X4]:((![X5]:((w(X5)=>exists(X4,X5)))&?[X6]:((w(X6)&exists(X4,X6))))))).
fof(conj, conjecture, ?[X2]:((mG(X2)&exists(X2,w_actual)))).
fof(s4, axiom, ![X4]:(((![X5]:((w(X5)=>exists(X4,X5)))&?[X7]:((w(X7)&exists(X4,X7))))=>![X8]:((w(X8)=>exists(X4,X8)))))).
fof(c_0_5, plain, ![X11, X12]:((~mG(X11)|(~w(X12)|exists(X11,X12)))), inference(fof_nnf,[],[inference(shift_quantors,[],[inference(variable_rename,[],[inference(fof_nnf,[],[s2])])])])).
fof(c_0_6, plain, (w(esk1_0)&(mG(esk2_0)&exists(esk2_0,esk1_0))), inference(skolemize,[],[inference(variable_rename,[],[s1])])).
fof(c_0_7, plain, ![X13, X14, X17]:((((~w(X17)|exists(esk4_0,X17)|(w(esk3_2(X13,X14))|~exists(X14,X13)|~w(X13)))&((w(esk5_0)|(w(esk3_2(X13,X14))|~exists(X14,X13)|~w(X13)))&(exists(esk4_0,esk5_0)|(w(esk3_2(X13,X14))|~exists(X14,X13)|~w(X13)))))&((~w(X17)|exists(esk4_0,X17)|(~exists(X14,esk3_2(X13,X14))|~exists(X14,X13)|~w(X13)))&((w(esk5_0)|(~exists(X14,esk3_2(X13,X14))|~exists(X14,X13)|~w(X13)))&(exists(esk4_0,esk5_0)|(~exists(X14,esk3_2(X13,X14))|~exists(X14,X13)|~w(X13))))))), inference(distribute,[],[inference(fof_nnf,[],[inference(shift_quantors,[],[inference(skolemize,[],[inference(variable_rename,[],[inference(fof_nnf,[],[s3])])])])])])).
cnf(c_0_8, plain, (exists(X1,X2)|~mG(X1)|~w(X2)), inference(split_conjunct,[],[c_0_5]), ['final']).
cnf(c_0_9, plain, (mG(esk2_0)), inference(split_conjunct,[],[c_0_6]), ['final']).
cnf(c_0_10, plain, (w(esk5_0)|w(esk3_2(X1,X2))|~exists(X2,X1)|~w(X1)), inference(split_conjunct,[],[c_0_7])).
cnf(c_0_11, plain, (exists(esk2_0,esk1_0)), inference(split_conjunct,[],[c_0_6]), ['final']).
cnf(c_0_12, plain, (w(esk1_0)), inference(split_conjunct,[],[c_0_6]), ['final']).
cnf(c_0_13, plain, (exists(esk2_0,X1)|~w(X1)), inference(spm,[],[c_0_8, c_0_9]), ['final']).
cnf(c_0_14, plain, (w(esk3_2(esk1_0,esk2_0))|w(esk5_0)), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_10, c_0_11]), c_0_12])])).
cnf(c_0_15, plain, (w(esk5_0)|~exists(X1,esk3_2(X2,X1))|~exists(X1,X2)|~w(X2)), inference(split_conjunct,[],[c_0_7])).
cnf(c_0_16, plain, (exists(esk2_0,esk3_2(esk1_0,esk2_0))|w(esk5_0)), inference(spm,[],[c_0_13, c_0_14])).
cnf(c_0_17, plain, (w(esk5_0)), inference(cn,[],[inference(rw,[],[inference(rw,[],[inference(spm,[],[c_0_15, c_0_16]), c_0_11]), c_0_12])]), ['final']).
cnf(c_0_18, plain, (exists(esk4_0,X1)|w(esk3_2(X2,X3))|~w(X1)|~exists(X3,X2)|~w(X2)), inference(split_conjunct,[],[c_0_7]), ['final']).
cnf(c_0_19, plain, (exists(esk2_0,esk5_0)), inference(spm,[],[c_0_13, c_0_17]), ['final']).
cnf(c_0_20, plain, (exists(esk4_0,X1)|w(esk3_2(esk5_0,esk2_0))|~w(X1)), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_18, c_0_19]), c_0_17])]), ['final']).
cnf(c_0_21, plain, (exists(esk4_0,esk1_0)|w(esk3_2(esk5_0,esk2_0))), inference(spm,[],[c_0_20, c_0_12])).
cnf(c_0_22, plain, (exists(esk4_0,esk5_0)|w(esk3_2(X1,X2))|~exists(X2,X1)|~w(X1)), inference(split_conjunct,[],[c_0_7])).
cnf(c_0_23, plain, (exists(esk4_0,X1)|~w(X1)|~exists(X2,esk3_2(X3,X2))|~exists(X2,X3)|~w(X3)), inference(split_conjunct,[],[c_0_7]), ['final']).
cnf(c_0_24, plain, (exists(esk2_0,esk3_2(esk5_0,esk2_0))|exists(esk4_0,esk1_0)), inference(spm,[],[c_0_13, c_0_21])).
cnf(c_0_25, plain, (exists(esk4_0,esk5_0)|w(esk3_2(esk5_0,esk2_0))), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_22, c_0_19]), c_0_17])])).
fof(c_0_26, negated_conjecture, ~(?[X2]:((mG(X2)&exists(X2,w_actual)))), inference(assume_negation,[],[conj])).
cnf(c_0_27, plain, (exists(esk4_0,esk1_0)|exists(esk4_0,X1)|~w(X1)), inference(cn,[],[inference(rw,[],[inference(rw,[],[inference(spm,[],[c_0_23, c_0_24]), c_0_19]), c_0_17])])).
cnf(c_0_28, plain, (exists(esk4_0,esk5_0)|~exists(X1,esk3_2(X2,X1))|~exists(X1,X2)|~w(X2)), inference(split_conjunct,[],[c_0_7])).
cnf(c_0_29, plain, (exists(esk2_0,esk3_2(esk5_0,esk2_0))|exists(esk4_0,esk5_0)), inference(spm,[],[c_0_13, c_0_25])).
fof(c_0_30, plain, ![X19, X21, X22]:(((w(esk6_1(X19))|(~w(X21)|~exists(X19,X21))|(~w(X22)|exists(X19,X22)))&(~exists(X19,esk6_1(X19))|(~w(X21)|~exists(X19,X21))|(~w(X22)|exists(X19,X22))))), inference(distribute,[],[inference(fof_nnf,[],[inference(shift_quantors,[],[inference(skolemize,[],[inference(variable_rename,[],[inference(fof_nnf,[],[s4])])])])])])).
fof(c_0_31, negated_conjecture, ![X23]:((~mG(X23)|~exists(X23,w_actual))), inference(fof_nnf,[],[inference(variable_rename,[],[inference(fof_nnf,[],[c_0_26])])])).
cnf(c_0_32, plain, (exists(esk4_0,esk1_0)), inference(spm,[],[c_0_27, c_0_12]), ['final']).
cnf(c_0_33, plain, (exists(esk4_0,esk5_0)), inference(cn,[],[inference(rw,[],[inference(rw,[],[inference(spm,[],[c_0_28, c_0_29]), c_0_19]), c_0_17])]), ['final']).
cnf(c_0_34, plain, (w(esk6_1(X1))|exists(X1,X3)|~w(X2)|~exists(X1,X2)|~w(X3)), inference(split_conjunct,[],[c_0_30]), ['final']).
cnf(c_0_35, negated_conjecture, (~mG(X1)|~exists(X1,w_actual)), inference(split_conjunct,[],[c_0_31]), ['final']).
cnf(c_0_36, plain, (exists(esk4_0,X1)|w(esk3_2(esk1_0,esk4_0))|~w(X1)), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_18, c_0_32]), c_0_12])]), ['final']).
cnf(c_0_37, plain, (exists(esk4_0,X1)|w(esk3_2(esk5_0,esk4_0))|~w(X1)), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_18, c_0_33]), c_0_17])]), ['final']).
cnf(c_0_38, plain, (exists(esk4_0,X1)|w(esk6_1(esk4_0))|~w(X1)), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_34, c_0_33]), c_0_17])]), ['final']).
cnf(c_0_39, plain, (exists(esk4_0,X1)|w(esk3_2(esk1_0,esk2_0))|~w(X1)), inference(cn,[],[inference(rw,[],[inference(spm,[],[c_0_18, c_0_11]), c_0_12])]), ['final']).
cnf(c_0_40, plain, (exists(X1,X3)|~exists(X1,esk6_1(X1))|~w(X2)|~exists(X1,X2)|~w(X3)), inference(split_conjunct,[],[c_0_30]), ['final']).
cnf(c_0_41, negated_conjecture, (~exists(esk2_0,w_actual)), inference(spm,[],[c_0_35, c_0_9]), ['final']).

  --- Generic digest ---
No refutation (CounterSatisfiable). The axioms are consistent with the negated goal.
  Unit clauses: mG(esk2_0), exists(esk2_0,esk1_0), w(esk1_0), w(esk5_0), w(esk5_0), w(esk5_0), exists(esk2_0,esk5_0), exists(esk4_0,esk1_0), exists(esk4_0,esk1_0), exists(esk4_0,esk5_0), exists(esk4_0,esk5_0), exists(esk4_0,esk1_0), exists(esk4_0,esk5_0), ~exists(esk2_0,w_actual)
  (Nothing forces a contradiction; the goal is not entailed.)

Verifying each inference step with E…
  ['s1', 's2'] ⊢ s_int1 [deduction]: Theorem
  ['s_int1'] ⊢ s5 [deduction]: CounterSatisfiable

Verifying with Lean...

Lean micro‑verification:
  (nothing to verify for this example)

# EXAMPLE 4
Some people claim 'there is no objective truth.'
But this claim itself purports to be objectively true.
For any meaningful debate to occur, participants must assume that some statements are objectively true or false.
Even to argue against objective truth requires assuming objective standards of logic and evidence.
Therefore, the very possibility of rational discourse presupposes objective truth.

Extracting logical form...

Logical Structure:
  s1: ∃x((Person(x) ∧ Claims(x,S_no_obj_truth)))
  s2: PurportsToBeObjectivelyTrue(S_no_obj_truth)
  s3: (MeaningfulDebatePossible() → AssumeObjectiveTruthOrFalsity())
  s4: (ArguesAgainstObjectiveTruth() → AssumesObjectiveStandards())
  s5: (RationalDiscoursePossible() → MeaningfulDebatePossible())
  s6: (RationalDiscoursePossible() → ArguesAgainstObjectiveTruth())
  s7: (AssumeObjectiveTruthOrFalsity() → PresupposesObjectiveTruth())
  s8: (AssumesObjectiveStandards() → PresupposesObjectiveTruth())
  s9: (RationalDiscoursePossible() → PresupposesObjectiveTruth())
  s10: (RationalDiscoursePossible() → AssumeObjectiveTruthOrFalsity())
  s11: (RationalDiscoursePossible() → AssumesObjectiveStandards())

Inferences:
  ['s5', 's3'] → s10 (hypothetical_syllogism)
  ['s6', 's4'] → s11 (hypothetical_syllogism)
  ['s10', 's7'] → s9 (hypothetical_syllogism)
  ['s11', 's8'] → s9 (hypothetical_syllogism)

Analyzing with ASP...

⚠️ No formal logical patterns detected

Verifying with E (global entailment)…
  SZS status: Theorem
  Used premises: ['s3', 's5', 's7']
  --- TSTP proof ---
fof(conj, conjecture, (rationalDiscoursePossible=>presupposesObjectiveTruth)).
fof(s5, axiom, (rationalDiscoursePossible=>meaningfulDebatePossible)).
fof(s7, axiom, (assumeObjectiveTruthOrFalsity=>presupposesObjectiveTruth)).
fof(s3, axiom, (meaningfulDebatePossible=>assumeObjectiveTruthOrFalsity)).
fof(c_0_4, negated_conjecture, ~((rationalDiscoursePossible=>presupposesObjectiveTruth)), inference(assume_negation,[],[conj])).
fof(c_0_5, plain, (~rationalDiscoursePossible|meaningfulDebatePossible), inference(fof_nnf,[],[inference(fof_nnf,[],[s5])])).
fof(c_0_6, negated_conjecture, (rationalDiscoursePossible&~presupposesObjectiveTruth), inference(fof_nnf,[],[inference(fof_nnf,[],[c_0_4])])).
fof(c_0_7, plain, (~assumeObjectiveTruthOrFalsity|presupposesObjectiveTruth), inference(fof_nnf,[],[inference(fof_nnf,[],[s7])])).
fof(c_0_8, plain, (~meaningfulDebatePossible|assumeObjectiveTruthOrFalsity), inference(fof_nnf,[],[inference(fof_nnf,[],[s3])])).
cnf(c_0_9, plain, (meaningfulDebatePossible|~rationalDiscoursePossible), inference(split_conjunct,[],[c_0_5])).
cnf(c_0_10, negated_conjecture, (rationalDiscoursePossible), inference(split_conjunct,[],[c_0_6])).
cnf(c_0_11, plain, (presupposesObjectiveTruth|~assumeObjectiveTruthOrFalsity), inference(split_conjunct,[],[c_0_7])).
cnf(c_0_12, negated_conjecture, (~presupposesObjectiveTruth), inference(split_conjunct,[],[c_0_6])).
cnf(c_0_13, plain, (assumeObjectiveTruthOrFalsity|~meaningfulDebatePossible), inference(split_conjunct,[],[c_0_8])).
cnf(c_0_14, plain, (meaningfulDebatePossible), inference(cn,[],[inference(rw,[],[c_0_9, c_0_10])])).
cnf(c_0_15, plain, (~assumeObjectiveTruthOrFalsity), inference(sr,[],[c_0_11, c_0_12])).
cnf(c_0_16, plain, ($false), inference(sr,[],[inference(cn,[],[inference(rw,[],[c_0_13, c_0_14])]), c_0_15]), ['proof']).

  --- Generic digest ---
Generic proof steps:
  [c_0_13] assumeObjectiveTruthOrFalsity | ~meaningfulDebatePossible (from inference, split_conjunct)
  [c_0_14] meaningfulDebatePossible (from inference, cn, inference, rw)
  [c_0_15] ~assumeObjectiveTruthOrFalsity (from inference, sr)
  ── resolve/simplify → ⊥

Verifying each inference step with E…
  ['s5', 's3'] ⊢ s10 [hypothetical_syllogism]: Theorem
  ['s6', 's4'] ⊢ s11 [hypothetical_syllogism]: Theorem
  ['s10', 's7'] ⊢ s9 [hypothetical_syllogism]: Theorem
  ['s11', 's8'] ⊢ s9 [hypothetical_syllogism]: Theorem

Verifying with Lean...

Lean micro‑verification:
  ∀-chain ['s5', 's3'] → s10: Not verified ❌
    note: could not line up ∀-chain components
  ∀-chain ['s6', 's4'] → s11: Not verified ❌
    note: could not line up ∀-chain components
  ∀-chain ['s10', 's7'] → s9: Not verified ❌
    note: could not line up ∀-chain components
  ∀-chain ['s11', 's8'] → s9: Not verified ❌
    note: could not line up ∀-chain components
  (nothing to verify for this example)
