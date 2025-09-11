
"""argfol: Minimal NL→FOL→TPTP→E-prover plumbing

- Build formulas with a tiny FOL AST (see fol_ast.py).
- Render to TPTP FOF (see tptp.py).
- Call E prover (see eprover.py).

This package doesn't include an NL parser. The expectation is that an LLM or a human
produces the FOL AST terms from text, then E-prover is used to check entailment.
"""
from .fol_ast import *
from .tptp import to_tptp_problem
from .eprover import prove_with_e, EProverResult
