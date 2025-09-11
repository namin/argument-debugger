#!/usr/bin/env python3
"""Showcase 1: Mathematical Theorem Proving

argfol can prove mathematical properties and theorems.
"""

from argfol.fol_ast import Var, Const, Pred, Forall, Exists, Implies, And, Or, Not, AtomF, Iff
from argfol.tptp import to_tptp_problem
from argfol.eprover import prove_with_e

print("=" * 60)
print("SHOWCASE 1: MATHEMATICAL PROPERTIES")
print("=" * 60)

# Example 1: Prove that equality is transitive
print("\n1. Proving transitivity of equality:")
print("   If a=b and b=c, then a=c")

X = Var('X')
Y = Var('Y')
Z = Var('Z')

equals = lambda x, y: Pred('equals', [x, y])

axioms = {
    # Equality is reflexive
    'reflexive': Forall([X], AtomF(equals(X, X))),
    
    # Equality is symmetric
    'symmetric': Forall([X, Y], 
        Implies(AtomF(equals(X, Y)), AtomF(equals(Y, X)))
    ),
    
    # Equality is transitive (we'll prove this follows from substitution)
    'substitution': Forall([X, Y], 
        Implies(
            AtomF(equals(X, Y)),
            Forall([Z], Implies(
                AtomF(equals(X, Z)),
                AtomF(equals(Y, Z))
            ))
        )
    ),
    
    # Given facts
    'a_equals_b': AtomF(equals(Const('a'), Const('b'))),
    'b_equals_c': AtomF(equals(Const('b'), Const('c'))),
}

# Prove: a = c
conjecture = AtomF(equals(Const('a'), Const('c')))

tptp = to_tptp_problem(axioms, conjecture, problem_name='transitivity')
res = prove_with_e(tptp, cpu_limit=2)

print(f"   Result: {res.status}")
if res.status == "Theorem":
    print(f"   ✓ Proven! Used axioms: {res.used_axioms}")

# Example 2: Prove properties about even/odd numbers
print("\n2. Proving properties of even and odd numbers:")
print("   The sum of two even numbers is even")

even = lambda x: Pred('even', [x])
odd = lambda x: Pred('odd', [x])
sum_of = lambda x, y, z: Pred('sum', [x, y, z])  # sum(x,y,z) means x+y=z

axioms = {
    # Definition: a number is even iff it equals 2k for some k
    'even_def': Forall([X], 
        Iff(
            AtomF(even(X)),
            Exists([Y], AtomF(Pred('double', [Y, X])))  # double(y,x) means x=2y
        )
    ),
    
    # If x=2a and y=2b, then x+y=2(a+b)
    'sum_of_doubles': Forall([X, Y, Z],
        Implies(
            And(
                Exists([Var('A')], AtomF(Pred('double', [Var('A'), X]))),
                Exists([Var('B')], AtomF(Pred('double', [Var('B'), Y])))
            ),
            Exists([Var('C')], And(
                AtomF(sum_of(X, Y, Z)),
                AtomF(Pred('double', [Var('C'), Z]))
            ))
        )
    ),
}

# Prove: If x is even and y is even, then x+y is even
conjecture = Forall([X, Y, Z],
    Implies(
        And(
            And(AtomF(even(X)), AtomF(even(Y))),
            AtomF(sum_of(X, Y, Z))
        ),
        AtomF(even(Z))
    )
)

tptp = to_tptp_problem(axioms, conjecture, problem_name='even_sum')
res = prove_with_e(tptp, cpu_limit=2)

print(f"   Result: {res.status}")
if res.status == "Theorem":
    print(f"   ✓ Proven! Mathematical property verified")

# Example 3: Prove a property about ordering
print("\n3. Proving ordering properties:")
print("   If x<y and y<z, then x<z (transitivity)")

less_than = lambda x, y: Pred('lt', [x, y])

axioms = {
    # Less than is transitive
    'transitive': Forall([X, Y, Z],
        Implies(
            And(AtomF(less_than(X, Y)), AtomF(less_than(Y, Z))),
            AtomF(less_than(X, Z))
        )
    ),
    
    # Less than is irreflexive
    'irreflexive': Forall([X], Not(AtomF(less_than(X, X)))),
    
    # Given: 1 < 2 and 2 < 3
    'one_lt_two': AtomF(less_than(Const('n1'), Const('n2'))),
    'two_lt_three': AtomF(less_than(Const('n2'), Const('n3'))),
}

# Prove: 1 < 3
conjecture = AtomF(less_than(Const('n1'), Const('n3')))

tptp = to_tptp_problem(axioms, conjecture, problem_name='ordering')
res = prove_with_e(tptp, cpu_limit=2)

print(f"   Result: {res.status}")
if res.status == "Theorem":
    print(f"   ✓ Proven! Transitivity confirmed")

print("\n" + "=" * 60)