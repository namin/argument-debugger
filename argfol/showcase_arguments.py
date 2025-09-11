#!/usr/bin/env python3
"""Showcase 3: Verifying Natural Language Arguments

argfol can verify if arguments are logically valid - 
does the conclusion necessarily follow from the premises?
"""

from argfol.fol_ast import Var, Const, Pred, Forall, Exists, Implies, And, Or, Not, AtomF
from argfol.tptp import to_tptp_problem
from argfol.eprover import prove_with_e

print("=" * 60)
print("SHOWCASE 3: VERIFYING ARGUMENT VALIDITY")
print("=" * 60)

# Argument 1: Valid syllogism
print("\n1. Classic Syllogism (VALID):")
print("   Premise 1: All philosophers are thinkers")
print("   Premise 2: All thinkers are curious")  
print("   Premise 3: Socrates is a philosopher")
print("   Conclusion: Socrates is curious")

X = Var('X')
philosopher = lambda x: Pred('philosopher', [x])
thinker = lambda x: Pred('thinker', [x])
curious = lambda x: Pred('curious', [x])
socrates = Const('socrates')

axioms = {
    'all_phil_think': Forall([X], Implies(AtomF(philosopher(X)), AtomF(thinker(X)))),
    'all_think_curious': Forall([X], Implies(AtomF(thinker(X)), AtomF(curious(X)))),
    'socrates_phil': AtomF(philosopher(socrates)),
}

conjecture = AtomF(curious(socrates))
tptp = to_tptp_problem(axioms, conjecture)
res = prove_with_e(tptp, cpu_limit=2)

print(f"   Result: {res.status}")
if res.status == "Theorem":
    print("   ✓ VALID: The conclusion follows from the premises")
    print(f"   Used premises: {res.used_axioms}")
else:
    print("   ✗ INVALID: The conclusion doesn't follow")

# Argument 2: Invalid argument (affirming the consequent)
print("\n2. Affirming the Consequent (INVALID):")
print("   Premise 1: If it rains, the ground is wet")
print("   Premise 2: The ground is wet")
print("   Conclusion: It rained")

rains = Pred('rains', [])
ground_wet = Pred('ground_wet', [])

axioms = {
    'rain_implies_wet': Implies(AtomF(rains), AtomF(ground_wet)),
    'ground_is_wet': AtomF(ground_wet),
}

conjecture = AtomF(rains)
tptp = to_tptp_problem(axioms, conjecture)
res = prove_with_e(tptp, cpu_limit=2)

print(f"   Result: {res.status}")
if res.status == "Theorem":
    print("   ✓ VALID: The conclusion follows from the premises")
else:
    print("   ✗ INVALID: The conclusion doesn't necessarily follow")
    print("   (The ground could be wet for other reasons)")

# Argument 3: Complex valid argument
print("\n3. Complex Argument with Disjunction (VALID):")
print("   Premise 1: Every student is either studying or working")
print("   Premise 2: No one who is working is studying")
print("   Premise 3: Alice is a student")
print("   Premise 4: Alice is not working")
print("   Conclusion: Alice is studying")

student = lambda x: Pred('student', [x])
studying = lambda x: Pred('studying', [x])
working = lambda x: Pred('working', [x])
alice = Const('alice')

axioms = {
    'student_study_or_work': Forall([X], 
        Implies(AtomF(student(X)), Or(AtomF(studying(X)), AtomF(working(X))))
    ),
    'work_not_study': Forall([X],
        Implies(AtomF(working(X)), Not(AtomF(studying(X))))
    ),
    'alice_student': AtomF(student(alice)),
    'alice_not_working': Not(AtomF(working(alice))),
}

conjecture = AtomF(studying(alice))
tptp = to_tptp_problem(axioms, conjecture)
res = prove_with_e(tptp, cpu_limit=2)

print(f"   Result: {res.status}")
if res.status == "Theorem":
    print("   ✓ VALID: The conclusion follows necessarily")
    print(f"   Used premises: {res.used_axioms}")

# Argument 4: Checking for hidden assumptions
print("\n4. Argument with Hidden Assumption (INVALID without it):")
print("   Premise 1: All birds can fly")
print("   Premise 2: Penguins are birds")
print("   Conclusion: Penguins can fly")
print("   (Testing both with and without the hidden assumption)")

bird = lambda x: Pred('bird', [x])
can_fly = lambda x: Pred('can_fly', [x])
penguin = lambda x: Pred('penguin', [x])

# First, try without the connecting assumption
axioms_incomplete = {
    'birds_fly': Forall([X], Implies(AtomF(bird(X)), AtomF(can_fly(X)))),
    'penguins_are_birds': AtomF(bird(Const('some_penguin'))),
}

conjecture = Forall([X], Implies(AtomF(penguin(X)), AtomF(can_fly(X))))
tptp = to_tptp_problem(axioms_incomplete, conjecture)
res1 = prove_with_e(tptp, cpu_limit=2)

# Now add the hidden assumption
axioms_complete = {
    'birds_fly': Forall([X], Implies(AtomF(bird(X)), AtomF(can_fly(X)))),
    'penguins_are_birds': Forall([X], Implies(AtomF(penguin(X)), AtomF(bird(X)))),
}

tptp = to_tptp_problem(axioms_complete, conjecture)
res2 = prove_with_e(tptp, cpu_limit=2)

print(f"   Without connecting premise: {res1.status}")
print(f"   With 'all penguins are birds': {res2.status}")
if res2.status == "Theorem" and res1.status != "Theorem":
    print("   ✓ Hidden assumption identified: Need 'All penguins are birds'")

print("\n" + "=" * 60)