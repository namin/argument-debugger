
# -*- coding: utf-8 -*-
"""
Minimal TPTP helpers for E prover integration.
This is a *very* small translator for a friendly subset of FOL. It also accepts
TPTP directly; if the string looks like TPTP (starts with "fof(" or "tff("), we pass through.

Supported sugar in fol strings (best-effort):
- "forall x. ..."  → "! [X] : (...)"
- "exists x. ..."  → "? [X] : (...)"
- "->" or "→" "⇒"  → "=>"
- "<->"            → "<=>"
- "and" "∧"        → "&"
- "or"  "∨"        → "|"
- "not" "¬"        → "~"
- variables are assumed to be lower-case words bound by quantifiers; they will be upper-cased in TPTP.
- predicates/functions/constants left as-is (user should keep them lower-case for TPTP).

If translation fails, we return the original string and let E try (user may already supply TPTP).
"""
from __future__ import annotations
import re
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class FOLPayload:
    premises: List[str]
    conclusion: str

def _looks_tptp(s: str) -> bool:
    t = s.strip()
    return t.startswith("fof(") or t.startswith("tff(")

_qforall = re.compile(r'\bforall\s+([a-zA-Z0-9_,\s]+)\s*\.\s*', re.IGNORECASE)
_qexists = re.compile(r'\bexists\s+([a-zA-Z0-9_,\s]+)\s*\.\s*', re.IGNORECASE)

def _replace_quantifiers(s: str) -> str:
    # forall x,y. φ  → ! [X,Y] : φ
    def repl_forall(m):
        vars_ = [v.strip() for v in m.group(1).split(',') if v.strip()]
        vars_ = [v[0].upper() + v[1:] for v in vars_]
        return f"! [{', '.join(vars_)}] : "
    def repl_exists(m):
        vars_ = [v.strip() for v in m.group(1).split(',') if v.strip()]
        vars_ = [v[0].upper() + v[1:] for v in vars_]
        return f"? [{', '.join(vars_)}] : "
    s = _qforall.sub(repl_forall, s)
    s = _qexists.sub(repl_exists, s)
    return s

def _sugar(s: str) -> str:
    repl = {
        '→': '=>', '⇒': '=>', '->': '=>',
        '<->': '<=>',
        '∧': '&', ' and ': ' & ',
        '∨': '|', ' or ': ' | ',
        '¬': '~', ' not ': ' ~ ',
        'TRUE': '$true', 'True': '$true', 'FALSE': '$false', 'False': '$false'
    }
    out = s
    for a, b in repl.items():
        out = out.replace(a, b)
    return out

def to_tptp_formulas(s: str) -> str:
    try:
        if _looks_tptp(s):
            return s
        s = _replace_quantifiers(s)
        s = _sugar(s)
        # Upper-case standalone single-letter variables x,y,z → X,Y,Z
        s = re.sub(r'\b([a-z])\b', lambda m: m.group(1).upper(), s)
        return s
    except Exception:
        return s

def make_tptp_problem(fol: FOLPayload, name_prefix: str = "prob") -> str:
    lines = []
    # premises as axioms
    for k, pr in enumerate(fol.premises, start=1):
        body = to_tptp_formulas(pr)
        lines.append(f"fof({name_prefix}_ax{k}, axiom, ({body})).")
    # conjecture
    conc = to_tptp_formulas(fol.conclusion)
    lines.append(f"fof({name_prefix}_conj, conjecture, ({conc})).")
    return "\n".join(lines) + "\n"
