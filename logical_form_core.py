from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Set

@dataclass(frozen=True)
class LFCore:
    atoms: List[str]                     # statement ids
    implications: List[Tuple[str, str]]  # ("sA","sB") means sA ⇒ sB (explicit statements only)
    facts: List[str]                     # premise-like ids
    goals: List[str]                     # goal ids

def _key(formula: Any) -> str:
    try:
        return formula.to_string()
    except Exception:
        return repr(formula)

def lf_to_core(argument: Any) -> LFCore:
    id_to_formula: Dict[str, Any] = {str(s.id): s.formula for s in argument.statements}
    key_to_ids: Dict[str, List[str]] = {}
    for sid, f in id_to_formula.items():
        key_to_ids.setdefault(_key(f), []).append(sid)

    atoms: List[str] = list(id_to_formula.keys())

    # Explicit top-level (A → B) statements only
    edges: List[Tuple[str, str]] = []
    for sid, f in id_to_formula.items():
        if getattr(f, "type", None) == "implies" and f.left and f.right:
            lk = _key(f.left); rk = _key(f.right)
            l_ids = key_to_ids.get(lk) or []
            r_ids = key_to_ids.get(rk) or []
            if l_ids and r_ids:
                edges.append((l_ids[0], r_ids[0]))
    edges = list(dict.fromkeys(edges))

    # Facts: classic heuristic—anything never concluded
    conclusions = {str(inf.to_id) for inf in getattr(argument, "inferences", []) or []}
    facts = [sid for sid in atoms if sid not in conclusions]

    # Goals: prefer explicit goal, else sink
    if getattr(argument, "goal_id", None):
        goals = [str(argument.goal_id)]
    else:
        outs = {a for (a, _) in edges}; ins = {b for (_, b) in edges}
        sinks = sorted(ins - outs)
        goals = [sinks[0]] if sinks else []

    return LFCore(atoms=atoms, implications=edges, facts=facts, goals=goals)
