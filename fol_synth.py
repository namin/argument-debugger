# fol_synth.py
# -*- coding: utf-8 -*-
"""
Robust NL → FOL synthesizer for common strict patterns.

Recognizes (most specific first):
  (A) Chained syllogism:   All Y are Z.  All X are Y.  c is X.     ⇒  Z(c)
  (B) Syllogism:           All X are Y.  c is X.                   ⇒  Y(c)
  (C) Modus Ponens:        If P then Q.  P.                        ⇒  Q
  (D) Modus Tollens:       If P then Q.  not Q.                    ⇒  not P
  (E) Only-if (props):     Only if P is Q.  Q.                     ⇒  P

Key fix:
  - Normalizes plural/singular variants (e.g., "humans" ↔ "human")
    so universal + instance match reliably.

On success, sets for the matched inference:
  - inf.rule   = "strict"
  - inf.type   = "deductive"
  - inf.scheme = "Syllogism" | "ChainedSyllogism" | "ModusPonens" | "ModusTollens" | "OnlyIf"
  - inf.fol    = FOLPayload(premises=[...], conclusion="...")
"""

from __future__ import annotations
import re
from typing import Optional, List, Tuple, Dict
from arg_ir import ArgumentIR, FOLPayload, Proposition

# ---------------- Normalization helpers ----------------

def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip())

def _lem_word(w: str) -> str:
    w = w.lower()
    # quick-and-dirty singularization
    if len(w) <= 3: 
        return w
    if w.endswith("ies"):   # policies -> policy
        return w[:-3] + "y"
    if w.endswith(("ses","xes","zes","ches","shes")):  # classes -> class; boxes -> box
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss"):       # humans -> human; cats -> cat
        return w[:-1]
    return w

def _lemma_phrase(s: str) -> str:
    # keep alphanum tokens; singularize each; join with '_'
    toks = re.findall(r"[A-Za-z0-9]+", s)
    toks = [_lem_word(t) for t in toks]
    return "_".join(toks) or "p"

def _sym(s: str) -> str:
    # symbol for predicates (concepts/conditions)
    return _lemma_phrase(s)

def _const(s: str) -> str:
    # constant symbol for individuals
    return _lemma_phrase(s)

# strip discourse markers on conclusions
_CONC = re.compile(r'^(therefore|so|hence|thus|consequently|as a result)[,:]?\s+', re.IGNORECASE)
def _strip_conc(s: str) -> str:
    return _CONC.sub('', s).strip()

# ---------------- Patterns ----------------

_UNIV = re.compile(
    r'^(all|every|any|each)\s+(.+?)\s+(are|are\s+all|are\s+always|are\s+typically|are\s+generally|are\s+usually|are)\s+(.+?)\.?$',
    re.IGNORECASE
)
_IS   = re.compile(r'^([A-Z][A-Za-z0-9 _-]+)\s+is\s+(an?\s+)?(.+?)\.?$', re.IGNORECASE)
_IMP  = re.compile(r'^(if|when)\s+(.+?)\s+(then|,)\s+(.+?)\.?$', re.IGNORECASE)
_NEG_SENT = re.compile(r'^(not\s+|no\s+)(.+)$', re.IGNORECASE)
_ONLY_IF  = re.compile(r'^\s*only if\s+(.+?)\s+(is|are)\s+(.+?)\.?$', re.IGNORECASE)

# ------------- Local builders (use inf.from_ids) -------------

def _try_syllogism_local(prem_texts: List[str], conc_text: str) -> Optional[FOLPayload]:
    A=B=c=None
    for t in prem_texts:
        m = _UNIV.match(_norm(t))
        if m:
            A, B = m.group(2), m.group(4)
            break
    if not (A and B): 
        return None
    for t in prem_texts:
        m = _IS.match(_norm(t))
        if m:
            c = m.group(1); A2 = m.group(3)
            if _sym(A2) == _sym(A):
                m3 = _IS.match(_norm(_strip_conc(conc_text)))
                if m3 and _sym(m3.group(1)) == _sym(c) and _sym(m3.group(3)) == _sym(B):
                    A1, B1, c1 = _sym(A), _sym(B), _const(c)
                    return FOLPayload(
                        premises=[f"forall x. {A1}(x) -> {B1}(x)", f"{A1}({c1})"],
                        conclusion=f"{B1}({c1})", symbols={}
                    )
    return None

def _try_chained_local(prem_texts: List[str], conc_text: str) -> Optional[FOLPayload]:
    rules: List[Tuple[str,str]] = []
    inst_c = inst_A = None
    for t in prem_texts:
        m = _UNIV.match(_norm(t))
        if m:
            rules.append((_sym(m.group(2)), _sym(m.group(4))))
        else:
            m2 = _IS.match(_norm(t))
            if m2:
                inst_c, inst_A = _const(m2.group(1)), _sym(m2.group(3))
    if len(rules) < 2 or not (inst_c and inst_A): 
        return None
    conc_m = _IS.match(_norm(_strip_conc(conc_text)))
    if not conc_m:
        return None
    conc_c, conc_Z = _const(conc_m.group(1)), _sym(conc_m.group(3))
    if conc_c != inst_c:
        return None
    for (x,y) in rules:
        for (y2,z) in rules:
            if y == y2 and inst_A == x and conc_Z == z:
                return FOLPayload(
                    premises=[f"forall t. {x}(t) -> {y}(t)", f"forall t. {y}(t) -> {z}(t)", f"{x}({inst_c})"],
                    conclusion=f"{z}({inst_c})", symbols={}
                )
    return None

def _try_mp_local(prem_texts: List[str], conc_text: str) -> Optional[FOLPayload]:
    P=Q=None
    for t in prem_texts:
        m = _IMP.match(_norm(t))
        if m:
            P, Q = m.group(2).strip(), m.group(4).strip()
            break
    if not (P and Q): 
        return None
    has_P = any(_sym(_strip_conc(t)) == _sym(P) for t in prem_texts)
    if not has_P or _sym(_strip_conc(conc_text)) != _sym(Q): 
        return None
    p, q = _sym(P), _sym(Q)
    return FOLPayload(premises=[f"{p} => {q}", p], conclusion=q, symbols={})

def _try_mt_local(prem_texts: List[str], conc_text: str) -> Optional[FOLPayload]:
    P=Q=None
    for t in prem_texts:
        m = _IMP.match(_norm(t))
        if m:
            P, Q = m.group(2).strip(), m.group(4).strip()
            break
    if not (P and Q): 
        return None
    has_not_Q = any(
        _sym(_strip_conc(_NEG_SENT.sub(r'\2', _norm(t)))) == _sym(Q)
        and t.lower().startswith(("not ","no ","it is not"))
        for t in prem_texts
    )
    conc_not_P = _sym(_strip_conc(_NEG_SENT.sub(r'\2', _norm(conc_text)))) == _sym(P) \
                 and conc_text.lower().startswith(("not ","no ","it is not"))
    if not (has_not_Q and conc_not_P): 
        return None
    p, q = _sym(P), _sym(Q)
    return FOLPayload(premises=[f"{p} => {q}", f"~{q}"], conclusion=f"~{p}", symbols={})

def _try_only_if_local(prem_texts: List[str], conc_text: str) -> Optional[FOLPayload]:
    for t in prem_texts:
        m = _ONLY_IF.match(_norm(t))
        if m:
            P, Q = _sym(m.group(1)), _sym(m.group(3))
            if any(_sym(_strip_conc(x)) == Q for x in prem_texts) and _sym(_strip_conc(conc_text)) == P:
                return FOLPayload(premises=[f"{Q} => {P}", Q], conclusion=P, symbols={})
    return None

# ------------- Global builders (scan all propositions) -------------

def _texts_by_id(props: List[Proposition]) -> Dict[str,str]:
    return {p.id: p.text for p in props}

def _all_texts(props: List[Proposition]) -> List[str]:
    return [p.text for p in props]

def _try_syllogism_global(props: List[Proposition], conc_text: str) -> Optional[FOLPayload]:
    A=B=c=None
    for t in _all_texts(props):
        m = _UNIV.match(_norm(t))
        if m:
            A, B = m.group(2), m.group(4)
            break
    if not (A and B): 
        return None
    for t in _all_texts(props):
        m2 = _IS.match(_norm(t))
        if m2:
            c = m2.group(1); A2 = m2.group(3)
            if _sym(A2) == _sym(A):
                m3 = _IS.match(_norm(_strip_conc(conc_text)))
                if m3 and _sym(m3.group(1)) == _sym(c) and _sym(m3.group(3)) == _sym(B):
                    A1, B1, c1 = _sym(A), _sym(B), _const(c)
                    return FOLPayload(
                        premises=[f"forall x. {A1}(x) -> {B1}(x)", f"{A1}({c1})"],
                        conclusion=f"{B1}({c1})", symbols={}
                    )
    return None

def _try_mp_global(props: List[Proposition], conc_text: str) -> Optional[FOLPayload]:
    P=Q=None
    for t in _all_texts(props):
        m = _IMP.match(_norm(t))
        if m:
            P, Q = m.group(2).strip(), m.group(4).strip()
            break
    if not (P and Q): 
        return None
    has_P = any(_sym(_strip_conc(t)) == _sym(P) for t in _all_texts(props))
    if not has_P or _sym(_strip_conc(conc_text)) != _sym(Q): 
        return None
    p, q = _sym(P), _sym(Q)
    return FOLPayload(premises=[f"{p} => {q}", p], conclusion=q, symbols={})

def _try_chained_global(props: List[Proposition], conc_text: str) -> Optional[FOLPayload]:
    rules: List[Tuple[str,str]] = []
    inst_c = inst_A = None
    for t in _all_texts(props):
        m = _UNIV.match(_norm(t))
        if m:
            rules.append((_sym(m.group(2)), _sym(m.group(4))))
        else:
            m2 = _IS.match(_norm(t))
            if m2:
                inst_c, inst_A = _const(m2.group(1)), _sym(m2.group(3))
    if len(rules) < 2 or not (inst_c and inst_A): 
        return None
    conc_m = _IS.match(_norm(_strip_conc(conc_text)))
    if not conc_m:
        return None
    conc_c, conc_Z = _const(conc_m.group(1)), _sym(conc_m.group(3))
    if conc_c != inst_c:
        return None
    for (x,y) in rules:
        for (y2,z) in rules:
            if y == y2 and inst_A == x and conc_Z == z:
                return FOLPayload(
                    premises=[f"forall t. {x}(t) -> {y}(t)", f"forall t. {y}(t) -> {z}(t)", f"{x}({inst_c})"],
                    conclusion=f"{z}({inst_c})", symbols={}
                )
    return None

# ---------------- Main API ----------------

def synth_fol(ir: ArgumentIR) -> ArgumentIR:
    """Mutates IR: attach FOL to strict patterns and mark rule='strict'."""
    by_id = _texts_by_id(ir.propositions)

    for inf in ir.inferences:
        # Keep existing strict+FOL if present
        if getattr(inf, "fol", None) and getattr(inf.fol, "conclusion", None):
            inf.rule = "strict"; inf.type = "deductive"
            continue

        prem_local = [by_id.get(pid, "") for pid in getattr(inf, "from_ids", [])]
        conc_text  = by_id.get(inf.to, "")

        # Try local patterns, then global fallback
        fol = (
            _try_chained_local(prem_local, conc_text) or
            _try_syllogism_local(prem_local, conc_text) or
            _try_mp_local(prem_local, conc_text) or
            _try_mt_local(prem_local, conc_text) or
            _try_only_if_local(prem_local, conc_text) or
            _try_chained_global(ir.propositions, conc_text) or
            _try_syllogism_global(ir.propositions, conc_text) or
            _try_mp_global(ir.propositions, conc_text)
        )

        if fol:
            inf.fol = fol
            inf.rule = "strict"
            inf.type = "deductive"
            # scheme label
            if fol.premises and fol.premises[0].startswith("forall"):
                inf.scheme = "ChainedSyllogism" if len(fol.premises) == 3 and "forall t." in fol.premises[1] else "Syllogism"
            elif "~" in fol.conclusion:
                inf.scheme = "ModusTollens"
            elif "=>" in fol.premises[0]:
                inf.scheme = "ModusPonens" if not fol.conclusion.startswith("~") else "ModusTollens"
            else:
                inf.scheme = getattr(inf, "scheme", None) or "Deductive"

    return ir
