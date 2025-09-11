from dataclasses import dataclass
from typing import Dict, List, Optional
import re

# =============================================================================
# Generic TSTP refutation digest (structure‑agnostic)
# =============================================================================

@dataclass
class Lit:
    neg: bool; pred: str; args: List[str]
    def pretty(self) -> str:
        return ("~" if self.neg else "") + (self.pred + ("" if not self.args else f"({','.join(self.args)})"))

def _is_var(tok: str) -> bool: return bool(re.fullmatch(r"X\d+", tok))

def _parse_lit(text: str) -> Optional[Lit]:
    s = text.strip(); neg = s.startswith("~"); s0 = s[1:].strip() if neg else s
    m0 = re.fullmatch(r"([a-z]\w*)", s0)
    if m0: return Lit(neg, m0.group(1), [])
    m = re.fullmatch(r"([a-z]\w*)\(([^()]*)\)", s0)
    if not m: return None
    return Lit(neg, m.group(1), [t.strip() for t in (m.group(2) or "").split(",")] if m.group(2).strip() else [])

def _parse_clause(body: str) -> List[Lit]:
    if body.strip() == "$false": return []
    return [l for l in (_parse_lit(p) for p in body.split("|")) if l]

@dataclass
class Clause:
    cid: str; role: str; lits: List[Lit]; parents: List[str]; sources: List[str]

_CNF_RE = re.compile(r"^cnf\(([^,]+),\s*([^,]+),\s*\((.*?)\)\s*,(.*?)\)\.", re.M|re.S)
def _parents(inf: str) -> List[str]: return re.findall(r"\b[a-z]\w*_\d+\b", inf)
def _sources(inf: str) -> List[str]:
    syms = re.findall(r"\b([A-Za-z]\w+)\b", inf)
    return [s for s in syms if not re.match(r"[a-z]\w*_\d+$", s)]

def _parse_cnf(proof: str) -> Dict[str, Clause]:
    d = {}
    for m in _CNF_RE.finditer(proof):
        cid, role, body, inf = m.groups()
        d[cid] = Clause(cid, role.strip(), _parse_clause(body.strip()), _parents(inf), _sources(inf))
    return d

def _unify(a: str, b: str, s: Dict[str,str]) -> Optional[Dict[str,str]]:
    if a == b: return s
    if _is_var(a):  return (s if a in s and s[a]==b else (s | {a:b}) if a not in s else None)
    if _is_var(b):  return _unify(b, a, s)
    return None

def _unify_lits(p: Lit, q: Lit) -> Optional[Dict[str,str]]:
    if p.pred != q.pred or p.neg == q.neg or len(p.args) != len(q.args): return None
    s: Dict[str,str] = {}
    for ta, tb in zip(p.args, q.args):
        s = _unify(ta, tb, s)
        if s is None: return None
    return s

def _apply(l: Lit, s: Dict[str,str]) -> Lit:
    return Lit(l.neg, l.pred, [s.get(t, t) for t in l.args])

def _show_with_src(c: Clause) -> str:
    body = "($false)" if not c.lits else " | ".join(l.pretty() for l in c.lits)
    if c.role == "negated_conjecture": return f"{body} (from ¬goal)"
    if c.sources:
        named = [s for s in c.sources if re.fullmatch(r"(s\d+|conj)", s)]
        tag = ", ".join(named or c.sources)
        return f"{body} (from {tag})"
    return body

def render_generic_digest(proof_tstp: Optional[str], szs_status: str) -> str:
    if not proof_tstp: return ""
    clauses = _parse_cnf(proof_tstp)
    empty = next((c for c in clauses.values() if len(c.lits)==0), None)
    if empty is None:
        # CounterSatisfiable: give a tiny model snapshot
        units = [c for c in clauses.values() if len(c.lits)==1]
        unit_str = ", ".join(l.pretty() for c in units for l in c.lits) or "(no unit clauses)"
        return ("No refutation (CounterSatisfiable). The axioms are consistent with the negated goal.\n"
                f"  Unit clauses: {unit_str}\n"
                "  (Nothing forces a contradiction; the goal is not entailed.)")

    parents = [clauses[p] for p in empty.parents if p in clauses]
    # Try to reconstruct a 2‑step resolution: (A,B)->R then R with C -> ⊥
    for i in range(len(parents)):
        for j in range(i+1, len(parents)):
            A, B = parents[i], parents[j]
            for la in A.lits:
                for lb in B.lits:
                    mgu = _unify_lits(la, lb)
                    if not mgu: continue
                    rest = [_apply(x, mgu) for x in A.lits]
                    rest = [_apply(x, mgu) for x in ([x for x in A.lits if x is not la] + [x for x in B.lits if x is not lb])]
                    res_str = " | ".join(l.pretty() for l in rest) if rest else "(empty)"
                    for k in range(len(parents)):
                        if k in (i, j): continue
                        C = parents[k]
                        # If resolvent not empty, look for complementary literal in C
                        if not rest:
                            lines = [
                                f"[{A.cid}] {_show_with_src(A)}",
                                f"[{B.cid}] {_show_with_src(B)}",
                                f"── resolve on {la.pred} with θ={{" + ", ".join(f"{u}→{v}" for u,v in mgu.items()) + f"}} → [r] {res_str}",
                                f"[{C.cid}] {_show_with_src(C)}",
                                "── resolve/simplify → ⊥",
                            ]
                            return "Generic proof steps:\n" + "\n".join("  "+x for x in lines)
                        for lr in rest:
                            for lc in C.lits:
                                if _unify_lits(lr, lc):
                                    lines = [
                                        f"[{A.cid}] {_show_with_src(A)}",
                                        f"[{B.cid}] {_show_with_src(B)}",
                                        f"── resolve on {la.pred} with θ={{" + ", ".join(f"{u}→{v}" for u,v in mgu.items()) + f"}} → [r] {res_str}",
                                        f"[{C.cid}] {_show_with_src(C)}",
                                        f"── resolve on {lr.pred} → ⊥",
                                    ]
                                    return "Generic proof steps:\n" + "\n".join("  "+x for x in lines)
    # Fallback: list parents
    if parents:
        lines = [f"[{P.cid}] {_show_with_src(P)}" for P in parents] + ["── resolve/simplify → ⊥"]
        return "Generic proof steps:\n" + "\n".join("  "+x for x in lines)
    return "Proof present, but could not reconstruct a simple step view."
