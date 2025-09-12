
# -*- coding: utf-8 -*-
"""
Heuristic FOL generator for common strict patterns.

Targets:
- Syllogism: "All/Every A are/is B.", "X is A.", "Therefore/So X is B."
- Modus Ponens: "If P then Q.", "P.", "Therefore Q."

This is intentionally small; if LLM provides FOL, we keep it. Otherwise we try.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple, List, Dict
from arg_ir import ArgumentIR, Inference, FOLPayload

# --- helpers -------------------------------------------------------------------
def _predize(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9_]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    if not s:
        s = 'p'
    if s[0].isdigit():
        s = 'p_' + s
    return s

def _constize(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9_]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    if not s:
        s = 'a'
    if s[0].isdigit():
        s = 'a_' + s
    return s

# --- pattern extractors --------------------------------------------------------

_univ_pat = re.compile(r'^(all|every|any|each)\s+([A-Za-z][A-Za-z0-9 _-]+?)\s+(are|are\s+all|are\s+always|are\s+usually|are\s+typically|are\s+generally|are\s+often|are\s+)\s+([A-Za-z][A-Za-z0-9 _-]+)\.?$', re.IGNORECASE)

_is_pat = re.compile(r'^([A-Z][A-Za-z0-9 _-]+)\s+is\s+(an?\s+)?([A-Za-z][A-Za-z0-9 _-]+)\.?$', re.IGNORECASE)

_imp_pat = re.compile(r'^(if|when)\s+(.+?)\s+(then|,)\s+(.+?)\.?$', re.IGNORECASE)

_concl_lead = re.compile(r'^(therefore|so|hence|thus|consequently|as a result)[,:]?\s+', re.IGNORECASE)

def _strip_concl_lead(s: str) -> str:
    return _concl_lead.sub('', s).strip()

# --- builders ------------------------------------------------------------------

def _build_syllogism_fol(A: str, B: str, c: str) -> FOLPayload:
    # forall x. A(x) -> B(x); A(c); |- B(c)
    A1, B1, c1 = _predize(A), _predize(B), _constize(c)
    premises = [f"forall x. {A1}(x) -> {B1}(x)", f"{A1}({c1})"]
    concl = f"{B1}({c1})"
    return FOLPayload(premises=premises, conclusion=concl, symbols={})

def _build_modus_ponens_fol(P: str, Q: str) -> FOLPayload:
    # propositional-level (0-ary predicates): p, p => q |- q
    p, q = _predize(P), _predize(Q)
    premises = [f"{p} => {q}", p]
    concl = q
    return FOLPayload(premises=premises, conclusion=concl, symbols={})

# --- main entry ----------------------------------------------------------------

def seed_fol_for_strict(ir: ArgumentIR) -> None:
    """
    For each inference i with rule='strict' and missing/empty fol, try to construct one.
    We look at the *texts* of premises and conclusion in the IR.
    """
    by_id = {p.id: p.text for p in ir.propositions}
    for i in ir.inferences:
        if i.rule != "strict":
            continue
        if i.fol and i.fol.conclusion:
            continue  # LLM already provided
        # collect premise/conc texts
        premise_texts = [by_id.get(pid, "") for pid in i.from_ids]
        conc_text = by_id.get(i.to, "")
        conc_text_nl = _strip_concl_lead(conc_text)

        # try syllogism: need a universal rule + an instance + instance conclusion
        A = B = c = None
        # find universal rule among premises
        for t in premise_texts:
            m = _univ_pat.match(t.strip())
            if m:
                A = m.group(2)
                B = m.group(4)
                break
        # find instance premise: "X is A"
        if A:
            for t in premise_texts:
                m2 = _is_pat.match(t.strip())
                if m2:
                    c = m2.group(1)
                    A2 = m2.group(3)
                    # allow "a/an A"
                    if _predize(A2) == _predize(A):
                        # check conclusion "Therefore, X is B"
                        m3 = _is_pat.match(conc_text_nl)
                        if m3 and _predize(m3.group(1)) == _predize(c) and _predize(m3.group(3)) == _predize(B):
                            i.fol = _build_syllogism_fol(A, B, c)
                            break
        if i.fol and i.fol.conclusion:
            continue

        # try modus ponens: "If P then Q", "P", "Therefore Q"
        P = Q = None
        for t in premise_texts:
            m = _imp_pat.match(t.strip())
            if m:
                P = m.group(2).strip()
                Q = m.group(4).strip()
                break
        if P and Q:
            # premises include P?
            has_P = any(_predize(_strip_concl_lead(t)) == _predize(P) for t in premise_texts)
            # conclusion equals Q?
            if _predize(_strip_concl_lead(conc_text)) == _predize(Q) and has_P:
                i.fol = _build_modus_ponens_fol(P, Q)
                continue
    # done
