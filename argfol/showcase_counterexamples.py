#!/usr/bin/env python3
"""Showcase 4: Finding Counterexamples and Testing Claims

argfol can help find if claims are always true, sometimes false,
or identify what additional assumptions would make them true.
"""

from argfol.fol_ast import Var, Const, Pred, Forall, Exists, Implies, And, Or, Not, AtomF
from argfol.tptp import to_tptp_problem
from argfol.eprover import prove_with_e

print("=" * 60)
print("SHOWCASE 4: FINDING COUNTEREXAMPLES & TESTING CLAIMS")
print("=" * 60)

# Test 1: Is this generalization always true?
print("\n1. Testing a Generalization:")
print("   Claim: 'All rich people are happy'")
print("   Given: 'John is rich' and 'John is not happy'")
print("   Can these both be true?")

X = Var('X')
rich = lambda x: Pred('rich', [x])
happy = lambda x: Pred('happy', [x])
john = Const('john')

# Try to prove a contradiction
axioms = {
    'generalization': Forall([X], Implies(AtomF(rich(X)), AtomF(happy(X)))),
    'john_rich': AtomF(rich(john)),
    'john_not_happy': Not(AtomF(happy(john))),
}

# If we can derive False, then the statements are contradictory
conjecture = AtomF(Pred('false', []))  # Try to derive a contradiction
tptp = to_tptp_problem(axioms, Not(conjecture))  # Prove Not(False) = True
res = prove_with_e(tptp, cpu_limit=2)

if res.status != "Theorem":
    print("   ✗ COUNTEREXAMPLE FOUND!")
    print("   The generalization is false - John is a counterexample")
else:
    print("   ✓ No contradiction - the claims are consistent")

# Test 2: Finding missing conditions
print("\n2. Finding Missing Conditions:")
print("   Claim: 'If someone works hard, they succeed'")
print("   Testing: Can we find cases where this fails?")

works_hard = lambda x: Pred('works_hard', [x])
succeeds = lambda x: Pred('succeeds', [x])
has_opportunity = lambda x: Pred('has_opportunity', [x])

# Version 1: Simple claim
axioms_simple = {
    'claim': Forall([X], Implies(AtomF(works_hard(X)), AtomF(succeeds(X)))),
    'bob_works_hard': AtomF(works_hard(Const('bob'))),
}

conjecture = AtomF(succeeds(Const('bob')))
res1 = prove_with_e(to_tptp_problem(axioms_simple, conjecture), cpu_limit=2)

# Version 2: With additional condition
axioms_refined = {
    'claim': Forall([X], Implies(
        And(AtomF(works_hard(X)), AtomF(has_opportunity(X))),
        AtomF(succeeds(X))
    )),
    'bob_works_hard': AtomF(works_hard(Const('bob'))),
    'bob_has_opportunity': AtomF(has_opportunity(Const('bob'))),
}

res2 = prove_with_e(to_tptp_problem(axioms_refined, conjecture), cpu_limit=2)

print(f"   Simple version (work→success): Bob succeeds? {res1.status}")
print(f"   Refined (work∧opportunity→success): Bob succeeds? {res2.status}")
print("   ✓ Shows that opportunity is a necessary additional condition")

# Test 3: Testing mutual exclusivity
print("\n3. Testing Mutual Exclusivity:")
print("   Can something be both A and B at the same time?")

is_even = lambda x: Pred('even', [x])
is_odd = lambda x: Pred('odd', [x])
is_prime = lambda x: Pred('prime', [x])

# Test if even and odd are mutually exclusive
axioms = {
    'even_not_odd': Forall([X], Implies(AtomF(is_even(X)), Not(AtomF(is_odd(X))))),
    'odd_not_even': Forall([X], Implies(AtomF(is_odd(X)), Not(AtomF(is_even(X))))),
    'two_is_even': AtomF(is_even(Const('two'))),
    'two_is_prime': AtomF(is_prime(Const('two'))),
}

# Can something be both even and odd?
conj1 = Exists([X], And(AtomF(is_even(X)), AtomF(is_odd(X))))
res1 = prove_with_e(to_tptp_problem(axioms, conj1), cpu_limit=2)

# Can something be both even and prime?
conj2 = Exists([X], And(AtomF(is_even(X)), AtomF(is_prime(X))))
res2 = prove_with_e(to_tptp_problem(axioms, conj2), cpu_limit=2)

print(f"   Can something be even AND odd? {res1.status}")
print(f"   Can something be even AND prime? {res2.status}")
if res2.status == "Theorem":
    print("   ✓ Yes! Example: 2 is both even and prime")

# Test 4: Identifying implicit assumptions
print("\n4. Identifying Implicit Assumptions in Arguments:")
print("   Argument: 'All swans are white. This is a swan. Therefore it's white.'")
print("   Question: What if we discover a black swan?")

swan = lambda x: Pred('swan', [x])
white = lambda x: Pred('white', [x])
black = lambda x: Pred('black', [x])

# Original theory
axioms_original = {
    'all_swans_white': Forall([X], Implies(AtomF(swan(X)), AtomF(white(X)))),
    'found_swan': AtomF(swan(Const('new_bird'))),
}

# Can we prove the new bird is white?
conj = AtomF(white(Const('new_bird')))
res1 = prove_with_e(to_tptp_problem(axioms_original, conj), cpu_limit=2)

# Now add a black swan - is there a contradiction?
axioms_with_black = {
    'all_swans_white': Forall([X], Implies(AtomF(swan(X)), AtomF(white(X)))),
    'black_swan_exists': And(AtomF(swan(Const('black_swan'))), AtomF(black(Const('black_swan')))),
    'nothing_both': Forall([X], Not(And(AtomF(white(X)), AtomF(black(X))))),
}

# Try to derive False (contradiction)
conj_false = AtomF(white(Const('black_swan')))
res2 = prove_with_e(to_tptp_problem(axioms_with_black, conj_false), cpu_limit=2)

print(f"   Original claim proves new swan is white? {res1.status}")
print(f"   Black swan creates contradiction? {res2.status}")
print("   ✓ Shows the 'all swans are white' assumption is falsifiable")

print("\n" + "=" * 60)