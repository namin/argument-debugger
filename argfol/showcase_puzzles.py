#!/usr/bin/env python3
"""Showcase 2: Logic Puzzles Solver

argfol can solve classic logic puzzles by finding what must be true.
"""

from argfol.fol_ast import Var, Const, Pred, Forall, Exists, Implies, And, Or, Not, AtomF, Iff
from argfol.tptp import to_tptp_problem
from argfol.eprover import prove_with_e

print("=" * 60)
print("SHOWCASE 2: LOGIC PUZZLES")
print("=" * 60)

# Puzzle 1: Knights and Knaves
print("\n1. Knights and Knaves Puzzle:")
print("   On an island, knights always tell the truth and knaves always lie.")
print("   A says: 'B is a knave'")
print("   B says: 'A and I are of opposite types'")
print("   What are A and B?")

knight = lambda x: Pred('knight', [x])
knave = lambda x: Pred('knave', [x])
says_true = lambda x: Pred('says_true', [x])

a = Const('a')
b = Const('b')

axioms = {
    # Everyone is either a knight or a knave (not both)
    'exclusive': Forall([Var('X')], 
        And(
            Or(AtomF(knight(Var('X'))), AtomF(knave(Var('X')))),
            Not(And(AtomF(knight(Var('X'))), AtomF(knave(Var('X')))))
        )
    ),
    
    # Knights tell the truth
    'knights_truthful': Forall([Var('X')],
        Implies(AtomF(knight(Var('X'))), AtomF(says_true(Var('X'))))
    ),
    
    # Knaves lie
    'knaves_lie': Forall([Var('X')],
        Implies(AtomF(knave(Var('X'))), Not(AtomF(says_true(Var('X')))))
    ),
    
    # A says "B is a knave" - this is true iff B is actually a knave
    'a_statement': Iff(
        AtomF(says_true(a)),
        AtomF(knave(b))
    ),
    
    # B says "A and I are of opposite types" - true iff they differ
    'b_statement': Iff(
        AtomF(says_true(b)),
        Or(
            And(AtomF(knight(a)), AtomF(knave(b))),
            And(AtomF(knave(a)), AtomF(knight(b)))
        )
    ),
}

# Test if A is a knight and B is a knave
conjecture1 = And(AtomF(knight(a)), AtomF(knave(b)))
tptp1 = to_tptp_problem(axioms, conjecture1)
res1 = prove_with_e(tptp1, cpu_limit=2)

# Test if A is a knave and B is a knight  
conjecture2 = And(AtomF(knave(a)), AtomF(knight(b)))
tptp2 = to_tptp_problem(axioms, conjecture2)
res2 = prove_with_e(tptp2, cpu_limit=2)

print(f"\n   Testing: A is knight, B is knave -> {res1.status}")
print(f"   Testing: A is knave, B is knight -> {res2.status}")

if res1.status == "Theorem":
    print("   ✓ Solution: A is a knight, B is a knave")
elif res2.status == "Theorem":
    print("   ✓ Solution: A is a knave, B is a knight")

# Puzzle 2: The Three Boxes
print("\n2. The Three Boxes Puzzle:")
print("   Three boxes: one has gold, one silver, one bronze")
print("   Gold box says: 'Silver is not in the middle'")
print("   Silver box says: 'Gold is not here'")
print("   Bronze box says: 'Gold is in the middle'")
print("   Exactly one box tells the truth. Where is the gold?")

in_box = lambda item, pos: Pred('in_box', [item, pos])
tells_truth = lambda box: Pred('tells_truth', [box])

gold = Const('gold')
silver = Const('silver')
bronze = Const('bronze')
left = Const('left')
middle = Const('middle')
right = Const('right')

axioms = {
    # Each item is in exactly one position
    'gold_unique': Or(
        Or(AtomF(in_box(gold, left)), AtomF(in_box(gold, middle))),
        AtomF(in_box(gold, right))
    ),
    'silver_unique': Or(
        Or(AtomF(in_box(silver, left)), AtomF(in_box(silver, middle))),
        AtomF(in_box(silver, right))
    ),
    'bronze_unique': Or(
        Or(AtomF(in_box(bronze, left)), AtomF(in_box(bronze, middle))),
        AtomF(in_box(bronze, right))
    ),
    
    # Each position has exactly one item
    'no_overlap': And(
        Implies(AtomF(in_box(gold, left)), 
                And(Not(AtomF(in_box(silver, left))), Not(AtomF(in_box(bronze, left))))),
        Implies(AtomF(in_box(gold, middle)),
                And(Not(AtomF(in_box(silver, middle))), Not(AtomF(in_box(bronze, middle)))))
    ),
    
    # Gold box statement: "Silver is not in the middle"
    'gold_says': Iff(
        AtomF(tells_truth(gold)),
        Not(AtomF(in_box(silver, middle)))
    ),
    
    # Silver box statement: "Gold is not here" (wherever silver is)
    'silver_says': Iff(
        AtomF(tells_truth(silver)),
        Forall([Var('P')], Implies(
            AtomF(in_box(silver, Var('P'))),
            Not(AtomF(in_box(gold, Var('P'))))
        ))
    ),
    
    # Bronze box statement: "Gold is in the middle"
    'bronze_says': Iff(
        AtomF(tells_truth(bronze)),
        AtomF(in_box(gold, middle))
    ),
    
    # Exactly one tells the truth
    'one_truth': And(
        Or(Or(AtomF(tells_truth(gold)), AtomF(tells_truth(silver))), 
           AtomF(tells_truth(bronze))),
        And(
            Implies(AtomF(tells_truth(gold)), 
                    And(Not(AtomF(tells_truth(silver))), Not(AtomF(tells_truth(bronze))))),
            Implies(AtomF(tells_truth(silver)),
                    And(Not(AtomF(tells_truth(gold))), Not(AtomF(tells_truth(bronze)))))
        )
    ),
}

# Test different positions for gold
for position in [left, middle, right]:
    conjecture = AtomF(in_box(gold, position))
    tptp = to_tptp_problem(axioms, conjecture, problem_name=f'gold_in_{position.name}')
    res = prove_with_e(tptp, cpu_limit=2)
    print(f"   Testing gold in {position.name}: {res.status}")
    if res.status == "Theorem":
        print(f"   ✓ Solution found: Gold is in the {position.name} box!")

print("\n" + "=" * 60)