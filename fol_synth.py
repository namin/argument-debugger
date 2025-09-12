# -*- coding: utf-8 -*-
"""
fol_synth.py — NL → FOL synthesizer for common strict patterns.

Recognizes:
  (A) Syllogism:
      "All/Every A are B.  X is A.  Therefore X is B."
      → ∀x A(x) → B(x);  A(X);  ⊢ B(X)
  (B) Modus Ponens:
      "If P then Q.  P.  Therefore Q."
      → (p => q), p ⊢ q

On success, sets:
  - inf.rule = "strict"
  - inf.type = "deductive"
  - inf.scheme = "ModusPonens" | "Syllogism"
  - inf.fol = { premises: [...], conclusion: "..." }

This complements (or replaces) fol_from_nl.seed_fol_for_strict, which only operates
when rule=='strict' already. Use this with --synth-fol or --e2e so certification has FOL.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple
from arg_ir import ArgumentIR, FOLPayload

_univ = re.compile(r'^(all|every|any|each)\s+([A-Za-z][A-Za-z0-9 _-]+?)\s+are\s+([A-Za-z][A-Za-z0-9 _-]+)\.?$', re.IGNORECASE)
_is   = re.compile(r'^([A-Z][A-Za-z0-9 _-]+)\s+is\s+(an?\s+)?([A-Za-z][A-Za-z0-9 _-]+)\.?$', re.IGNORECASE)
_imp  = re.compile(r'^(if|when)\s+(.+?)\s+(then|,)\s+(.+?)\.?$', re.IGNORECASE)
_conc = re.compile(r'^(therefore|so|hence|thus|consequently|as a result)[,:]?\s+', re.IGNORECASE)

def _strip_conc(s: str) -> str:
    return _conc.sub('', s).strip()

def _pred(s: str) -> str:
    t = re.sub(r'[^a-z0-9_]+', '_', s.strip().lower())
    t = re.sub(r'_+', '_', t).strip('_')
    if not t: t = 'p'
    if t[0].isdigit(): t = 'p_' + t
    return t

def _const(s: str) -> str:
    t = re.sub(r'[^a-z0-9_]+', '_', s.strip().lower())
    t = re.sub(r'_+', '_', t).strip('_')
    if not t: t = 'a'
    if t[0].isdigit(): t = 'a_' + t
    return t

def _try_syllogism(prem_texts, conc_text) -> Optional[FOLPayload]:
    A=B=c=None
    for t in prem_texts:
        m = _univ.match(t.strip())
        if m:
            A, B = m.group(2), m.group(3)
            break
    if not (A and B): return None
    for t in prem_texts:
        m = _is.match(t.strip())
        if m:
            c = m.group(1); A2 = m.group(3)
            if _pred(A2) == _pred(A):
                m3 = _is.match(_strip_conc(conc_text))
                if m3 and _pred(m3.group(1)) == _pred(c) and _pred(m3.group(3)) == _pred(B):
                    A1, B1, c1 = _pred(A), _pred(B), _const(c)
                    return FOLPayload(premises=[f"forall x. {A1}(x) -> {B1}(x)", f"{A1}({c1})"],
                                      conclusion=f"{B1}({c1})", symbols={})
    return None

def _try_mp(prem_texts, conc_text) -> Optional[FOLPayload]:
    P=Q=None
    for t in prem_texts:
        m = _imp.match(t.strip())
        if m:
            P, Q = m.group(2).strip(), m.group(4).strip()
            break
    if not (P and Q): return None
    # require premise P and conclusion Q
    has_P = any(_pred(_strip_conc(t)) == _pred(P) for t in prem_texts)
    if not has_P: return None
    if _pred(_strip_conc(conc_text)) != _pred(Q): return None
    p, q = _pred(P), _pred(Q)
    return FOLPayload(premises=[f"{p} => {q}", p], conclusion=q, symbols={})

def synth_fol(ir: ArgumentIR) -> ArgumentIR:
    by_id = {p.id: p.text for p in ir.propositions}
    for inf in ir.inferences:
        # collect premise/conc texts
        prem = [by_id.get(pid, "") for pid in inf.from_ids]
        conc = by_id.get(inf.to, "")
        # already have FOL?
        if inf.fol and getattr(inf.fol, "conclusion", None):
            # ensure rule is strict
            inf.rule = "strict"
            inf.type = "deductive"
            continue
        # try strict patterns
        fol = _try_syllogism(prem, conc) or _try_mp(prem, conc)
        if fol:
            inf.fol = fol
            inf.rule = "strict"
            inf.type = "deductive"
            if _try_mp(prem, conc):
                inf.scheme = "ModusPonens"
            else:
                inf.scheme = "Syllogism"
    return ir
