# ---------- Generic TSTP refutation explainer (resolution-oriented) ----------
import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

@dataclass
class Lit:
    neg: bool
    pred: str
    args: List[str]  # strings: variables 'X1' or constants 'penguin' etc.

    def pretty(self) -> str:
        a = "" if len(self.args) == 0 else "(" + ",".join(self.args) + ")"
        return ("~" if self.neg else "") + f"{self.pred}{a}"

def _is_var(tok: str) -> bool:
    # TPTP CNF uses uppercase vars like X1, X2; constants & functors lowercase
    return bool(re.fullmatch(r"X\d+", tok))

def _parse_lit(text: str) -> Optional[Lit]:
    s = text.strip()
    neg = s.startswith("~")
    if neg: s = s[1:].strip()
    # 0-arity atom like "rain"  OR predicate(args)
    m0 = re.fullmatch(r"([a-z]\w*)", s)
    if m0:
        return Lit(neg, m0.group(1), [])
    m = re.fullmatch(r"([a-z]\w*)\(([^()]*)\)", s)
    if not m:
        return None
    pred = m.group(1)
    args = [t.strip() for t in m.group(2).split(",")] if m.group(2).strip() else []
    return Lit(neg, pred, args)

def _parse_clause_body(body: str) -> List[Lit]:
    return [l for l in (_parse_lit(part) for part in body.split("|")) if l is not None]

@dataclass
class Clause:
    cid: str
    role: str
    lits: List[Lit]
    parents: List[str]  # parent clause IDs (flat list)

_CNF_RE = re.compile(r"^cnf\(([^,]+),\s*([^,]+),\s*\((.*?)\)\s*,(.*?)\)\.", re.M | re.S)

def _extract_parents(inf_blob: str) -> List[str]:
    # Grab tokens like c_0_6, c_12_3 etc. from nested inference(...) blobs
    return re.findall(r"\b[a-z]\w*_\d+\b", inf_blob)

def parse_cnf_proof(proof_tstp: str) -> Dict[str, Clause]:
    clauses: Dict[str, Clause] = {}
    for m in _CNF_RE.finditer(proof_tstp):
        cid, role, body, inf = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
        lits = [] if body.strip() == "$false" else _parse_clause_body(body)
        parents = _extract_parents(inf)
        clauses[cid] = Clause(cid, role, lits, parents)
    return clauses

def _unify_terms(a: str, b: str, subst: Dict[str, str]) -> Optional[Dict[str, str]]:
    # very small occurs-check-free unifier over variables vs constants
    if a == b: return subst
    if _is_var(a):
        va = subst.get(a)
        if va is None:
            subst[a] = b
            return subst
        else:
            return subst if va == b else None
    if _is_var(b):
        return _unify_terms(b, a, subst)
    # constants/functors differ → fail (we don't handle nested functors here)
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
    def sub(t: str) -> str: return s.get(t, t)
    return Lit(l.neg, l.pred, [sub(t) for t in l.args])

def _apply_subst_to_clause(lits: List[Lit], s: Dict[str, str]) -> List[Lit]:
    return [_apply_subst_to_lit(l, s) for l in lits]

def reconstruct_refutation_steps(clauses: Dict[str, Clause]) -> Optional[List[str]]:
    # find the empty clause
    empty = next((c for c in clauses.values() if len(c.lits) == 0), None)
    if empty is None:
        return None  # no refutation
    steps: List[str] = []

    # BFS/stack back from empty to inputs; we’ll make a simple linearization:
    stack = [empty]
    seen = set()
    tmp_ids: List[str] = []

    while stack:
        c = stack.pop()
        if c.cid in seen: continue
        seen.add(c.cid)
        tmp_ids.append(c.cid)
        for pid in c.parents:
            if pid in clauses:
                stack.append(clauses[pid])

    # Now go forward: try to show actual resolution pivots whenever we can
    # Collect only CNF lines involved
    core_ids = [cid for cid in tmp_ids if cid in clauses]
    core = [clauses[cid] for cid in core_ids if cid in clauses]

    # Helper to pretty-print a clause
    def show_clause(cl: Clause) -> str:
        if len(cl.lits) == 0:
            return "($false)"
        return " | ".join(l.pretty() for l in cl.lits)

    # Build a map for quick parent lookup
    cmap = {c.cid: c for c in clauses.values()}

    # We attempt to detect pairs (A,B)->R by scanning parents of each derived clause along the path.
    for c in core:
        if len(c.lits) == 0:
            # Last step: explain using its immediate parents (2+)
            parents = [cmap[p] for p in c.parents if p in cmap]
            # Try to find a final pair that resolves to empty
            if len(parents) >= 2:
                A, B = parents[0], parents[1]
                pivot = None
                mgu: Optional[Dict[str, str]] = None
                for la in A.lits:
                    for lb in B.lits:
                        s = _unify_lits(la, lb)
                        if s:
                            pivot = (la, lb); mgu = s; break
                    if pivot: break
                if pivot:
                    la, lb = pivot
                    # After eliminating pivot, check if the other parent can finish it
                    steps.append(f"[{A.cid}] {show_clause(A)}")
                    steps.append(f"[{B.cid}] {show_clause(B)}")
                    theta = "{" + ", ".join(f"{k}→{v}" for k,v in mgu.items()) + "}" if mgu else "{}"
                    steps.append(f"── resolve on {la.pred} with θ={theta} → [r] " +
                                 " | ".join(_apply_subst_to_clause(
                                     [x for x in A.lits if x is not la] +
                                     [x for x in B.lits if x is not lb], mgu or {}
                                 )[0:1] or ["(unit)"]))
                # add any additional parents
                for P in parents[2:]:
                    steps.append(f"[{P.cid}] {show_clause(P)}")
                steps.append("── resolve/simplify → ⊥")
            continue

        # For non-empty derived clauses, print a generic derivation header
        if c.parents:
            parents = [cmap[p] for p in c.parents if p in cmap]
            if parents:
                for p in parents:
                    steps.append(f"[{p.cid}] {show_clause(p)}")
                steps.append(f"── derive [{c.cid}] {show_clause(c)}")

    # Deduplicate consecutive duplicates
    cleaned: List[str] = []
    for ln in steps:
        if not cleaned or cleaned[-1] != ln:
            cleaned.append(ln)

    return cleaned or None

def render_generic_digest(proof_tstp: Optional[str], szs_status: str) -> str:
    if not proof_tstp:
        return ""
    clauses = parse_cnf_proof(proof_tstp)
    steps = reconstruct_refutation_steps(clauses)
    if steps:
        return "Generic proof steps:\n" + "\n".join("  " + s for s in steps)
    # If we reach here, we didn't find a refutation path (e.g., CounterSatisfiable)
    if szs_status == "CounterSatisfiable":
        # Show a minimal, model-style explanation using units
        units = [c for c in clauses.values() if len(c.lits) == 1]
        unit_str = ", ".join(l.pretty() for c in units for l in c.lits) or "(no units)"
        return ("No refutation (CounterSatisfiable). The clauses can be satisfied together with the negated goal.\n"
                f"  Unit clauses present: {unit_str}\n"
                "  (Nothing forces a contradiction; the goal is not entailed.)")
    return "Proof present, but could not reconstruct a simple step view."
