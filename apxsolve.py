#!/usr/bin/env python3
"""
apxsolve.py — Minimal APX solver + insights (no external solvers)

Reads a Dung AF in APX format (arg/att facts) and computes:
  - grounded, complete, preferred, stable, stage, semi-stable
Also provides:
  - credulous/skeptical query
  - simple insights (grounded roadblocks, defense depth, persistent/soft attackers across preferred)
  - DOT export

This is an educational/portable solver: it enumerates subsets for some tasks,
so it's suited for small-to-medium AFs (≈ ≤ 16–18 arguments).

Usage:
  python apxsolve.py graph.apx
  python apxsolve.py graph.apx --sem preferred
  python apxsolve.py graph.apx --sem all --json
  python apxsolve.py graph.apx --query a2 --mode credulous --sem preferred
  python apxsolve.py graph.apx --insights --target a1 --sem all
  python apxsolve.py graph.apx --dot af.dot
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
from typing import Dict, List, Set, Tuple, Iterable, FrozenSet, Optional

# ---------------------------
# APX parsing
# ---------------------------

APX_ARG_RE = re.compile(r"\barg\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\.", re.I)
APX_ATT_RE = re.compile(r"\batt\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\.", re.I)
APX_COMMENT_RE = re.compile(r"%.*?$", re.M)

def read_apx(path: str) -> Tuple[List[str], Set[Tuple[str,str]]]:
    text = open(path, "r", encoding="utf-8").read()
    # Strip '%' comments to avoid false matches
    text_nc = re.sub(APX_COMMENT_RE, "", text)
    args = APX_ARG_RE.findall(text_nc)
    atts = set(APX_ATT_RE.findall(text_nc))
    # De-duplicate args and ensure any atom in att(...) is also in args
    atoms = list(dict.fromkeys(args))  # preserve order
    aset = set(atoms)
    for (u, v) in atts:
        if u not in aset:
            atoms.append(u); aset.add(u)
        if v not in aset:
            atoms.append(v); aset.add(v)
    return atoms, atts

# ---------------------------
# AF core
# ---------------------------

class AF:
    def __init__(self, atoms: List[str], attacks: Set[Tuple[str,str]]):
        self.arguments: List[str] = list(atoms)
        self.attacks: Set[Tuple[str,str]] = set(attacks)
        self._attackers: Dict[str, Set[str]] = {a: set() for a in self.arguments}
        self._attackees: Dict[str, Set[str]] = {a: set() for a in self.arguments}
        for (u, v) in self.attacks:
            if v in self._attackers: self._attackers[v].add(u)
            if u in self._attackees: self._attackees[u].add(v)

    def attackers(self, a: str) -> Set[str]:
        return self._attackers.get(a, set())

    def attackees(self, a: str) -> Set[str]:
        return self._attackees.get(a, set())

    def F(self, S: Set[str]) -> Set[str]:
        defended = set()
        for a in self.arguments:
            ok = True
            for b in self.attackers(a):
                if not any((c, b) in self.attacks for c in S):
                    ok = False; break
            if ok:
                defended.add(a)
        return defended

    def conflict_free(self, S: Iterable[str]) -> bool:
        Sset = set(S)
        for x in Sset:
            for y in Sset:
                if (x, y) in self.attacks:
                    return False
        return True

    def defends(self, S: Set[str], a: str) -> bool:
        for b in self.attackers(a):
            if not any((c, b) in self.attacks for c in S):
                return False
        return True

    def admissible(self, S: Iterable[str]) -> bool:
        Sset = set(S)
        if not self.conflict_free(Sset):
            return False
        for a in Sset:
            if not self.defends(Sset, a):
                return False
        return True

    def range_size(self, S: Iterable[str]) -> int:
        Sset = set(S)
        out = set()
        for s in Sset:
            out.update(self.attackees(s))
        return len(Sset | out)

    # Enumerations
    def _all_subsets(self) -> Iterable[FrozenSet[str]]:
        A = self.arguments
        n = len(A)
        for r in range(n + 1):
            for comb in itertools.combinations(A, r):
                yield frozenset(comb)

    def all_conflict_free(self) -> List[FrozenSet[str]]:
        return [S for S in self._all_subsets() if self.conflict_free(S)]

    def all_admissible(self) -> List[FrozenSet[str]]:
        return [S for S in self._all_subsets() if self.admissible(S)]

    def complete_extensions(self) -> List[FrozenSet[str]]:
        res = []
        for S in self._all_subsets():
            if self.admissible(S) and self.F(set(S)) == set(S):
                res.append(S)
        return res

    def grounded_extension(self) -> FrozenSet[str]:
        S = set()
        while True:
            T = self.F(S)
            if T == S: break
            S = T
        return frozenset(S)

    def preferred_extensions(self) -> List[FrozenSet[str]]:
        adm = self.all_admissible()
        res = []
        for S in adm:
            if not any(S < T for T in adm):
                res.append(S)
        return res

    def stable_extensions(self) -> List[FrozenSet[str]]:
        res = []
        Aset = set(self.arguments)
        for S in self.all_conflict_free():
            outside = Aset - set(S)
            ok = True
            for x in outside:
                if not any((s, x) in self.attacks for s in S):
                    ok = False; break
            if ok:
                res.append(S)
        return res

    def stage_extensions(self) -> List[FrozenSet[str]]:
        cf = self.all_conflict_free()
        if not cf: return []
        best = max(self.range_size(S) for S in cf) if cf else -1
        return [S for S in cf if self.range_size(S) == best]

    def semi_stable_extensions(self) -> List[FrozenSet[str]]:
        comp = self.complete_extensions()
        if not comp: return []
        best = max(self.range_size(S) for S in comp) if comp else -1
        return [S for S in comp if self.range_size(S) == best]

# ---------------------------
# Insights
# ---------------------------

def defense_depth(af: AF) -> Dict[str, Optional[int]]:
    """
    Depth[a] = minimum i >= 0 such that a ∈ F^{i+1}(∅), counting from 1 for the first wave.
    Returns None for arguments never entering grounded.
    """
    A = set(af.arguments)
    S = set()
    depth = {a: None for a in A}
    i = 0
    while True:
        T = af.F(S)
        if T == S:
            break
        wave = T - S
        i += 1
        for a in wave:
            if depth[a] is None:
                depth[a] = i
        S = T
    return depth

def grounded_roadblocks(af: AF, target: str) -> List[str]:
    G = set(af.grounded_extension())
    if target in G: return []
    # attackers of target that G does not counter-attack
    rb = []
    for b in af.attackers(target):
        if not any((c, b) in af.attacks for c in G):
            rb.append(b)
    return sorted(rb)

def preferred_persistent_soft_attackers(af: AF, target: str) -> Tuple[Set[str], Set[str]]:
    prefs = af.preferred_extensions()
    if not prefs:
        return set(), set()
    inter = set(af.arguments)
    union = set()
    for S in prefs:
        inter &= set(S)
        union |= set(S)
    att_set = set(af.attackers(target))
    persistent = inter & att_set     # attackers IN every preferred
    soft = (union - inter) & att_set # attackers IN some but not all preferred
    return persistent, soft

# ---------------------------
# Utilities
# ---------------------------

def credulous(fams: List[FrozenSet[str]], a: str) -> bool:
    return any(a in S for S in fams)

def skeptical(fams: List[FrozenSet[str]], a: str) -> bool:
    if not fams: return False
    return all(a in S for S in fams)

def format_setset(sets: List[FrozenSet[str]]) -> str:
    if not sets: return "[]"
    return "[" + ", ".join("{" + ", ".join(sorted(S)) + "}" for S in sets) + "]"

def export_dot(af: AF, path: str):
    lines = ["digraph AF {"]
    for a in af.arguments:
        lines.append(f'  "{a}" [shape=ellipse,label="{a}"];')
    for (u,v) in sorted(af.attacks):
        lines.append(f'  "{u}" -> "{v}";')
    lines.append("}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ---------------------------
# CLI
# ---------------------------

def main():
    p = argparse.ArgumentParser(description="APX solver + insights (grounded/preferred/stable/complete/stage/semi-stable).")
    p.add_argument("path", help="APX file path")
    p.add_argument("--sem", default="all", choices=["grounded","preferred","stable","complete","stage","semi-stable","semistable","all"])
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--query", type=str, default=None, help="Atom to test (e.g., a1)")
    p.add_argument("--mode", type=str, default=None, choices=["credulous","skeptical"], help="Query mode")
    p.add_argument("--insights", action="store_true", help="Print insight panel")
    p.add_argument("--target", type=str, default=None, help="Target atom for insights (defaults to goal or first arg)")
    p.add_argument("--dot", type=str, default=None, help="Export DOT graph")
    args = p.parse_args()

    atoms, atts = read_apx(args.path)
    af = AF(atoms, atts)

    if args.dot:
        export_dot(af, args.dot)

    # Compute semantics
    def compute_all():
        return {
            "grounded": af.grounded_extension(),
            "preferred": af.preferred_extensions(),
            "stable": af.stable_extensions(),
            "complete": af.complete_extensions(),
            "stage": af.stage_extensions(),
            "semi-stable": af.semi_stable_extensions(),
        }

    if args.sem == "all":
        res = compute_all()
    elif args.sem == "grounded":
        res = af.grounded_extension()
    elif args.sem == "preferred":
        res = af.preferred_extensions()
    elif args.sem == "stable":
        res = af.stable_extensions()
    elif args.sem == "complete":
        res = af.complete_extensions()
    elif args.sem == "stage":
        res = af.stage_extensions()
    else:  # semi-stable
        res = af.semi_stable_extensions()

    # Query
    query_ans = None
    if args.query and args.mode:
        if args.sem == "grounded":
            fam = [res] if isinstance(res, frozenset) else [af.grounded_extension()]
        elif args.sem == "all":
            fam = compute_all()["preferred"]
        else:
            fam = res if isinstance(res, list) else [res]
        query_ans = credulous(fam, args.query) if args.mode == "credulous" else skeptical(fam, args.query)

    # Insights
    insight_obj = None
    if args.insights:
        tgt = args.target or (atoms[0] if atoms else None)
        depth = defense_depth(af)
        G = af.grounded_extension()
        pref = af.preferred_extensions()
        stbl = af.stable_extensions()
        persistent, soft = (set(), set())
        if tgt:
            persistent, soft = preferred_persistent_soft_attackers(af, tgt)
        insight_obj = {
            "target": tgt,
            "grounded": sorted(list(G)),
            "preferred_count": len(pref),
            "stable_count": len(stbl),
            "depth": {a: depth[a] for a in atoms},
            "roadblocks_grounded": (grounded_roadblocks(af, tgt) if tgt else []),
            "preferred_persistent_attackers_of_target": sorted(list(persistent)),
            "preferred_soft_attackers_of_target": sorted(list(soft)),
        }

    # Output
    if args.json:
        out = {
            "arguments": atoms,
            "attacks": sorted(list(atts)),
            "semantics": None,
        }
        if args.sem == "all":
            out["semantics"] = {
                "grounded": sorted(list(res["grounded"])),
                "preferred": [sorted(list(S)) for S in res["preferred"]],
                "stable": [sorted(list(S)) for S in res["stable"]],
                "complete": [sorted(list(S)) for S in res["complete"]],
                "stage": [sorted(list(S)) for S in res["stage"]],
                "semi-stable": [sorted(list(S)) for S in res["semi-stable"]],
            }
        else:
            if isinstance(res, frozenset):
                out["semantics"] = sorted(list(res))
            elif isinstance(res, list):
                out["semantics"] = [sorted(list(S)) for S in res]
            else:
                out["semantics"] = res
        if query_ans is not None:
            out["query"] = {"arg": args.query, "mode": args.mode, "answer": bool(query_ans)}
        if insight_obj is not None:
            out["insights"] = insight_obj
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # Human-readable
    print("=== APX Solver ===")
    print("Arguments:", ", ".join(atoms) if atoms else "(none)")
    print("Attacks:")
    if not atts:
        print("  (none)")
    else:
        for (u,v) in sorted(atts):
            print(f"  {u} -> {v}")

    def show_sets(name: str, sets):
        if isinstance(sets, frozenset):
            print(f"{name}: " + "{" + ", ".join(sorted(list(sets))) + "}")
        else:
            print(f"{name}: " + format_setset(sets))

    if args.sem == "all":
        print("\n=== Semantics ===")
        show_sets("Grounded", res["grounded"])
        show_sets("Preferred", res["preferred"])
        show_sets("Stable", res["stable"])
        show_sets("Complete", res["complete"])
        show_sets("Stage", res["stage"])
        show_sets("Semi-stable", res["semi-stable"])
    else:
        print(f"\n=== {args.sem.upper()} ===")
        show_sets(args.sem.capitalize(), res)

    if args.query and args.mode:
        print(f"\nQuery: {args.mode.capitalize()} acceptance of {args.query}: {'YES' if query_ans else 'NO'}")

    if insight_obj is not None:
        print("\n=== Insights ===")
        print(f"Target: {insight_obj['target']}")
        print(f"Grounded core: {{{', '.join(insight_obj['grounded'])}}}")
        print(f"Preferred count: {insight_obj['preferred_count']}  |  Stable count: {insight_obj['stable_count']}")
        print("Defense depth:")
        for a in atoms:
            print(f"  {a}: {insight_obj['depth'][a]}")
        if insight_obj['target']:
            print(f"Grounded roadblocks for {insight_obj['target']}: {{{', '.join(insight_obj['roadblocks_grounded'])}}}")
            print(f"Preferred persistent attackers of {insight_obj['target']}: {{{', '.join(insight_obj['preferred_persistent_attackers_of_target'])}}}")
            print(f"Preferred soft attackers of {insight_obj['target']}: {{{', '.join(insight_obj['preferred_soft_attackers_of_target'])}}}")

if __name__ == "__main__":
    main()
