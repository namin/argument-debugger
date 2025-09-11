
"""Minimal demo: Socrates syllogism

∀x. human(x) → mortal(x)
human(socrates)
⊢ mortal(socrates)
"""
from argfol.fol_ast import Var, Const, Pred, Forall, Implies, AtomF
from argfol.tptp import to_tptp_problem
from argfol.eprover import prove_with_e

X = Var('X')
human = lambda t: Pred('human', [t])
mortal = lambda t: Pred('mortal', [t])
socrates = Const('socrates')

ax = {
    'humans_are_mortal': Forall([X], Implies(AtomF(human(X)), AtomF(mortal(X)))),
    'socrates_is_human': AtomF(human(socrates)),
}
conj = AtomF(mortal(socrates))

tptp = to_tptp_problem(ax, conj, problem_name='socrates')
print('--- TPTP problem ---')
print(tptp)
print('--- Running E prover ---')
res = prove_with_e(tptp, cpu_limit=5)
print('Status:', res.status)
if res.used_axioms:
    print('Used axioms:', res.used_axioms)
if res.proof_tstp:
    print('--- Proof (TSTP) ---')
    print(res.proof_tstp)
else:
    print('(no proof section found)')
