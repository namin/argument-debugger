# ---------- Generic TSTP refutation explainer (resolution-oriented) ----------
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

@dataclass
class Lit:
    neg: bool
    pred: str
    args: List[str]  # variables 'X1'.. or constants 'penguin', etc.

    def pretty(self) -> str:
        a = "" if not self.args else "(" + ",".join(self.args) + ")"
        return ("~" if self.neg else "") + f"{self.pred}{a}"

def _is_var(tok: str) -> bool:
    # TPTP CNF variables are typically uppercase like X1, X2
    return bool(re.fullmatch(r"X\d+", tok))

def _parse_lit(text: str) -> Optional[Lit]:
    s = text.strip()
    neg = s.startswith("~")
    if neg:
        s = s[1:].strip()
    # Nullary atom like "rain"
    m0 = re.fullmatch(r"([a-z]\w*)", s)
    if m0:
        return Lit(neg, m0.group(1), [])
    # Predicate with args: p(args)
    m = re.fullmatch(r"([a-z]\w*)\(([^()]*)\)", s)
    if not m:
        return None
    pred = m.group(1)
    args = [t.strip() for t in m.group(2).split(",")] if m.group(2).strip() else []
    return Lit(neg, pred, args)

def _parse_clause_body(body: str) -> List[Lit]:
    parts = [p.strip() for p in body.split("|")]
    lits: List[Lit] = []
    for p in parts:
        lit = _parse_lit(p)
        if lit is not None:
            lits.append(lit)
    return lits

@dataclass
class Clause:
    cid: str
    role: str      # e.g., plain / negated_conjecture / axiom
    lits: List[Lit]
    parents: List[str]  # parent IDs

# cnf(c_0_7, plain, (p(X)|~q(X)), inference(...,[c_0_1,c_0_2])).
_CNF_RE = re.compile(r"^cnf\(([^,]+),\s*([^,]+),\s*\((.*?)\)\s*,(.*?)\)\.", re.M | re.S)

def _extract_parents(inf_blob: str) -> List[str]:
    # Find 'c_...' ids in nested inference(...) blobs
    return re.findall(r"\b[a-z]\w*_\d+\b", inf_blob)

def parse_cnf_proof(proof_tstp: str) -> Dict[str, Clause]:
    clauses: Dict[str, Clause] = {}
    for m in _CNF_RE.finditer(proof_tstp):
        cid, role, body, inf = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
        lits = [] if body.strip() == "$false" else _parse_clause_body(body)
        parents = _extract_parents(inf)
        clauses[cid] = Clause(cid=cid, role=role, lits=lits, parents=parents)
    return clauses

# ------------------------------- Unification ---------------------------------

def _unify_terms(a: str, b: str, subst: Dict[str, str]) -> Optional[Dict[str, str]]:
    if a == b:
        return subst
    if _is_var(a):
        va = subst.get(a)
        if va is None:
            subst[a] = b
            return subst
        return subst if va == b else None
    if _is_var(b):
        return _unify_terms(b, a, subst)
    # (No function symbols support here; extend if you need nested terms.)
    return None

def _unify_lits(p: Lit, q: Lit) -> Optional[Dict[str, str]]:
    if p.pred != q.pred or p.neg == q.neg or len(p.args) != len(q.args):
        return None
    subst: Dict[str, str] = {}
    for ta, tb in zip(p.args, q.args):
        subst = _unify_terms(ta, tb, subst)
        if subst is None:
            return None
    return subst

def _apply_subst_to_lit(l: Lit, s: Dict[str, str]) -> Lit:
    sub = lambda t: s.get(t, t)
    return Lit(l.neg, l.pred, [sub(t) for t in l.args])

def _apply_subst_to_lits(lits: List[Lit], s: Dict[str, str]) -> List[Lit]:
    return [_apply_subst_to_lit(l, s) for l in lits]

# -------------------------- Refutation reconstruction ------------------------

def _resolve_pair(A: Clause, B: Clause) -> Optional[Tuple[Tuple[Lit, Lit, Dict[str,str]], List[Lit]]]:
    """
    Try to resolve A and B once. If a pivot (complementary literals) is found,
    return ((la, lb, mgu), resolvent_lits_after_subst).
    """
    for la in A.lits:
        for lb in B.lits:
            mgu = _unify_lits(la, lb)
            if mgu is None:
                continue
            # Remove pivot literals, then apply mgu
            rest = [x for x in A.lits if x is not la] + [x for x in B.lits if x is not lb]
            resolvent = _apply_subst_to_lits(rest, mgu)
            return ((la, lb, mgu), resolvent)
    return None

def _find_empty_clause(clauses: Dict[str, Clause]) -> Optional[Clause]:
    for c in clauses.values():
        if len(c.lits) == 0:
            return c
    return None

def render_generic_digest(proof_tstp: Optional[str], szs_status: str) -> str:
    if not proof_tstp:
        return ""
    clauses = parse_cnf_proof(proof_tstp)
    empty = _find_empty_clause(clauses)

    # CounterSatisfiable: no empty clause → model-style note
    if empty is None:
        # Show unit clauses that can be simultaneously true with ~goal
        units = [c for c in clauses.values() if len(c.lits) == 1]
        unit_str = ", ".join(l.pretty() for c in units for l in c.lits) or "(no unit clauses)"
        return (
            "No refutation (CounterSatisfiable). The axioms are consistent with the negated goal.\n"
            f"  Unit clauses present: {unit_str}\n"
            "  (Nothing forces a contradiction; the goal is not entailed.)"
        )

    # Attempt a 2-step reconstruction from the empty clause's parents
    parent_ids = [pid for pid in empty.parents if pid in clauses]
    parents = [clauses[pid] for pid in parent_ids]

    # Try all pairs among the parents to find a pivot → resolvent,
    # then see if a remaining parent resolves the resolvent to empty.
    for i in range(len(parents)):
        for j in range(i + 1, len(parents)):
            A, B = parents[i], parents[j]
            ab = _resolve_pair(A, B)
            if ab is None:
                continue
            (la, lb, mgu), resolvent = ab

            # pretty resolvent
            res_str = " | ".join(l.pretty() for l in resolvent) if resolvent else "(empty)"

            # Try to finish with a third parent
            for k in range(len(parents)):
                if k == i or k == j:
                    continue
                C = parents[k]
                done = False
                # If resolvent is empty already, any third parent will do
                if not resolvent:
                    lines = [
                        f"[{A.cid}] " + " | ".join(l.pretty() for l in A.lits),
                        f"[{B.cid}] " + " | ".join(l.pretty() for l in B.lits),
                        f"── resolve on {la.pred} with θ="
                        + "{" + ", ".join(f"{u}→{v}" for u, v in mgu.items()) + "} "
                        + f"→ [r] {res_str}",
                        f"[{C.cid}] " + " | ".join(l.pretty() for l in C.lits),
                        "── resolve/simplify → ⊥",
                    ]
                    return "Generic proof steps:\n" + "\n".join("  " + s for s in lines)

                # Otherwise look for a complementary unit in C
                for lc in C.lits:
                    # Try to resolve each resolvent literal with C's literal
                    for lr in resolvent:
                        m2 = _unify_lits(lr, lc)
                        if m2 is None:
                            continue
                        # Reaching empty if C has only that pivot (common in unit)
                        lines = [
                            f"[{A.cid}] " + " | ".join(l.pretty() for l in A.lits),
                            f"[{B.cid}] " + " | ".join(l.pretty() for l in B.lits),
                            f"── resolve on {la.pred} with θ="
                            + "{" + ", ".join(f"{u}→{v}" for u, v in mgu.items()) + "} "
                            + f"→ [r] {res_str}",
                            f"[{C.cid}] " + " | ".join(l.pretty() for l in C.lits),
                            f"── resolve on {lr.pred} → ⊥",
                        ]
                        return "Generic proof steps:\n" + "\n".join("  " + s for s in lines)

    # Fallback: show parents and a final line
    if parents:
        lines = [f"[{P.cid}] " + " | ".join(l.pretty() for l in P.lits) for P in parents]
        lines.append("── resolve/simplify → ⊥")
        return "Generic proof steps:\n" + "\n".join("  " + s for s in lines)

    return "Proof present, but could not reconstruct a simple step view."
