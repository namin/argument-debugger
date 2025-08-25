#!/usr/bin/env python3
"""
as_end2end.py — End-to-end pipeline

Natural language blocks (with optional ID:/ATTACKS:)  →  APX  →  clingo semantics.

Depends on:
  - nl2apx.py     (for extraction & APX emission)
  - af_clingo.py  (for semantics via clingo)

Usage examples:
  python as_end2end.py arguments.txt --use-llm --sem all
  python as_end2end.py examples_dual_preferred.txt --relation explicit --sem preferred
  python as_end2end.py arguments.txt --use-llm --apx-out graph.apx --dot af.dot --json
  python as_end2end.py arguments.txt --use-llm --sem all --insights --target A1 --names both
"""
from __future__ import annotations

import argparse
import json
from typing import Dict, List, Set, Tuple, FrozenSet, Optional

import nl2apx
import af_clingo

# ---------- Helpers for mapping & insights ----------

def build_apx_in_memory(
    blocks_path: str,
    relation: str = "auto",
    jaccard: float = 0.45,
    min_overlap: int = 3,
    use_llm: bool = False,
    llm_threshold: float = 0.55,
    llm_mode: str = "augment",
) -> Tuple[List[str], Dict[str,str], List[str], Dict[str,str], Set[Tuple[str,str]], Dict]:
    """
    Returns (ids, id_to_text, apx_atoms, id2atom, attacks_apx, meta)
    - ids: original IDs (A1, A2, ...)
    - id_to_text: block text per original ID
    - apx_atoms: sanitized atom names used in APX
    - id2atom: mapping original ID -> sanitized atom
    - attacks_apx: set of (atom, atom) attacks
    - meta: provenance from nl2apx (explicit/heuristic/llm/final edges as index pairs)
    """
    blocks = nl2apx.parse_blocks(blocks_path)
    ids, id_to_text, idx_edges, meta = None, None, None, None  # for clarity

    ids, id_to_text, idx_edges, meta = nl2apx.build_edges(
        blocks,
        relation_mode=relation,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )

    # Build sanitized APX atoms deterministically (same as nl2apx.emit_apx)
    apx_atoms = nl2apx.make_unique([nl2apx.sanitize_atom(i) for i in ids])
    id2atom = {ids[i]: apx_atoms[i] for i in range(len(ids))}
    atom2id = {v: k for k, v in id2atom.items()}

    # Convert index-based edges -> atom-based attacks
    attacks_apx: Set[Tuple[str,str]] = set((apx_atoms[i], apx_atoms[j]) for (i, j) in idx_edges)

    return ids, id_to_text, apx_atoms, id2atom, attacks_apx, meta

def emit_apx_file(apx_path: str, ids: List[str], id_to_text: Dict[str,str], attacks_idx: Set[Tuple[int,int]]):
    """Write APX file using nl2apx.emit_apx (for reproducibility & external tools)."""
    apx_text = nl2apx.emit_apx(ids, id_to_text, attacks_idx, provenance=None)
    with open(apx_path, "w", encoding="utf-8") as f:
        f.write(apx_text)

def _F(atoms: List[str], attacks: Set[Tuple[str,str]], S: Set[str]) -> Set[str]:
    """Characteristic function F(S) over APX atoms (for insights)."""
    attackers: Dict[str, Set[str]] = {a: set() for a in atoms}
    for (u,v) in attacks:
        if v in attackers:
            attackers[v].add(u)
    defended = set()
    for a in atoms:
        ok = True
        for b in attackers[a]:
            if not any((c, b) in attacks for c in S):
                ok = False; break
        if ok:
            defended.add(a)
    return defended

def defense_depth(atoms: List[str], attacks: Set[Tuple[str,str]]) -> Dict[str, Optional[int]]:
    depth = {a: None for a in atoms}
    S = set()
    i = 0
    while True:
        T = _F(atoms, attacks, S)
        if T == S: break
        wave = T - S
        i += 1
        for a in wave:
            if depth[a] is None:
                depth[a] = i
        S = T
    return depth

def grounded_roadblocks(atoms: List[str], attacks: Set[Tuple[str,str]], target: str) -> List[str]:
    G = set(af_clingo.grounded(atoms, attacks))
    if target in G:
        return []
    # attackers of target that G does not counter-attack
    atk_map: Dict[str, Set[str]] = {a: set() for a in atoms}
    for (u,v) in attacks:
        if v in atk_map:
            atk_map[v].add(u)
    rbs = []
    for b in atk_map.get(target, set()):
        if not any((c,b) in attacks for c in G):
            rbs.append(b)
    return sorted(rbs)

def preferred_persistent_soft(atoms: List[str], attacks: Set[Tuple[str,str]], target: str):
    prefs = af_clingo.preferred(atoms, attacks)
    if not prefs:
        return [], []
    inter = set(atoms)
    union = set()
    for S in prefs:
        inter &= set(S)
        union |= set(S)
    atk_map: Dict[str, Set[str]] = {a: set() for a in atoms}
    for (u,v) in attacks:
        if v in atk_map:
            atk_map[v].add(u)
    att = atk_map.get(target, set())
    pers = sorted(list(inter & att))
    soft = sorted(list((union - inter) & att))
    return pers, soft

def translate_set(S: FrozenSet[str], atom2id: Dict[str,str]) -> List[str]:
    return sorted([atom2id.get(a, a) for a in S])

def translate_sets(sets: List[FrozenSet[str]], atom2id: Dict[str,str]) -> List[List[str]]:
    return [translate_set(S, atom2id) for S in sets]

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="End-to-end: NL blocks -> APX -> clingo semantics + insights.")
    ap.add_argument("path", help="Path to text file (blocks separated by blank lines).")
    # Extraction
    ap.add_argument("--relation", default="auto", choices=["auto","explicit","none"],
                    help="ATTACKS handling: 'auto' uses ATTACKS if present else heuristics; 'explicit' only ATTACKS; 'none' disables heuristics (ATTACKS still honored).")
    ap.add_argument("--jaccard", type=float, default=0.45, help="Heuristic Jaccard threshold (auto mode).")
    ap.add_argument("--min-overlap", type=int, default=3, help="Minimum shared content tokens (auto mode).")
    ap.add_argument("--use-llm", action="store_true", help="Use LLM to infer attacks.")
    ap.add_argument("--llm-threshold", type=float, default=0.55, help="Confidence cutoff for LLM edges.")
    ap.add_argument("--llm-mode", default="augment", choices=["augment","override"],
                    help="Combine LLM edges with others (augment) or use only LLM edges (override).")
    ap.add_argument("--apx-out", type=str, default=None, help="Write the APX to this path (optional).")
    # Semantics
    ap.add_argument("--sem", default="all",
                    choices=["grounded","preferred","stable","complete","stage","semi-stable","semistable","all"],
                    help="Which semantics to compute.")
    ap.add_argument("--query", type=str, default=None, help="Acceptance query for an argument ID or APX atom.")
    ap.add_argument("--mode", type=str, default=None, choices=["credulous","skeptical"], help="Query mode.")
    ap.add_argument("--dot", type=str, default=None, help="Export DOT graph (APX atoms).")
    # Output
    ap.add_argument("--json", action="store_true", help="JSON output.")
    ap.add_argument("--names", default="apx", choices=["apx","ids","both"],
                    help="How to display argument names in output (APX atoms, original IDs, or both).")
    # Insights
    ap.add_argument("--insights", action="store_true", help="Show insights (grounded roadblocks, depth, persistent/soft attackers).")
    ap.add_argument("--target", type=str, default=None, help="Target argument (ID or APX atom) for insights.")
    args = ap.parse_args()

    # Build AF in memory
    ids, id2text, atoms, id2atom, attacks, meta = build_apx_in_memory(
        args.path, relation=args.relation, jaccard=args.jaccard, min_overlap=args.min_overlap,
        use_llm=args.use_llm, llm_threshold=args.llm_threshold, llm_mode=args.llm_mode
    )
    atom2id = {v:k for (k,v) in id2atom.items()}

    # Optionally write APX
    if args.apx_out:
        # Need index-based edges for emit; reconstruct from atom-based attacks
        idx_map = {ids[i]: i for i in range(len(ids))}
        idx_edges = set()
        for (u,v) in attacks:
            # find indices by matching atoms -> ids -> indices
            uid = atom2id.get(u); vid = atom2id.get(v)
            if uid in idx_map and vid in idx_map:
                idx_edges.add((idx_map[uid], idx_map[vid]))
        emit_apx_file(args.apx_out, ids, id2text, idx_edges)

    # Export DOT
    if args.dot:
        af_clingo.export_dot(atoms, attacks, args.dot)

    # Compute semantics with clingo
    if args.sem == "all":
        Sem = {
            "grounded": af_clingo.grounded(atoms, attacks),
            "preferred": af_clingo.preferred(atoms, attacks),
            "stable":    af_clingo.stable(atoms, attacks),
            "complete":  af_clingo.complete(atoms, attacks),
            "stage":     af_clingo.stage(atoms, attacks),
            "semi-stable": af_clingo.semi_stable(atoms, attacks),
        }
    elif args.sem == "grounded":
        Sem = af_clingo.grounded(atoms, attacks)
    elif args.sem == "preferred":
        Sem = af_clingo.preferred(atoms, attacks)
    elif args.sem == "stable":
        Sem = af_clingo.stable(atoms, attacks)
    elif args.sem == "complete":
        Sem = af_clingo.complete(atoms, attacks)
    elif args.sem == "stage":
        Sem = af_clingo.stage(atoms, attacks)
    else:
        Sem = af_clingo.semi_stable(atoms, attacks)

    # Query
    query_ans = None
    if args.query and args.mode:
        q = args.query
        # Normalize query to APX atom
        if q in id2atom: q_atom = id2atom[q]
        elif q in atoms: q_atom = q
        else: q_atom = q  # try as-is
        if args.sem == "grounded":
            fam = [Sem] if isinstance(Sem, frozenset) else [af_clingo.grounded(atoms, attacks)]
        elif args.sem == "all":
            fam = Sem["preferred"]
        else:
            fam = Sem if isinstance(Sem, list) else [Sem]
        query_ans = af_clingo.credulous(fam, q_atom) if args.mode == "credulous" else af_clingo.skeptical(fam, q_atom)

    # Insights
    insights = None
    if args.insights:
        tgt = args.target
        if tgt is None and ids:
            tgt = ids[0]  # default to first ID
        # normalize to APX atom
        tgt_atom = id2atom.get(tgt, tgt)
        depth = defense_depth(atoms, attacks)
        G = af_clingo.grounded(atoms, attacks)
        persistent, soft = preferred_persistent_soft(atoms, attacks, tgt_atom) if tgt_atom else ([], [])
        insights = {
            "target": {"id": (tgt if tgt in ids else None), "atom": tgt_atom},
            "grounded_core": sorted(list(G)),
            "defense_depth": depth,
            "grounded_roadblocks": grounded_roadblocks(atoms, attacks, tgt_atom) if tgt_atom else [],
            "preferred_counts": {"preferred": len(af_clingo.preferred(atoms, attacks)),
                                 "stable": len(af_clingo.stable(atoms, attacks))},
            "preferred_attackers_of_target": {"persistent": persistent, "soft": soft},
        }

    # Prepare output
    def translate(obj):
        """Translate semantics to original IDs if requested."""
        if isinstance(obj, frozenset):
            return translate_set(obj, atom2id)
        elif isinstance(obj, list):
            return [translate_set(S, atom2id) for S in obj]
        elif isinstance(obj, dict):  # sem=all
            out = {}
            for k,v in obj.items():
                if isinstance(v, (list, set)):
                    out[k] = [translate_set(S, atom2id) for S in v]
                else:
                    out[k] = translate_set(v, atom2id)
            return out
        return obj

    if args.json:
        out = {
            "input": {"path": args.path, "ids": ids, "id_to_atom": id2atom, "meta": meta},
            "af": {"atoms": atoms, "attacks": sorted(list(attacks))},
            "semantics": None
        }
        if args.names == "apx":
            out["semantics"] = (Sem if args.sem != "all" else
                                {"grounded": sorted(list(Sem["grounded"])),
                                 "preferred": [sorted(list(S)) for S in Sem["preferred"]],
                                 "stable": [sorted(list(S)) for S in Sem["stable"]],
                                 "complete": [sorted(list(S)) for S in Sem["complete"]],
                                 "stage": [sorted(list(S)) for S in Sem["stage"]],
                                 "semi-stable": [sorted(list(S)) for S in Sem["semi-stable"]]})
        elif args.names == "ids":
            out["semantics"] = translate(Sem)
        else:  # both
            out["semantics"] = {
                "apx": (Sem if args.sem != "all" else
                        {"grounded": sorted(list(Sem["grounded"])),
                         "preferred": [sorted(list(S)) for S in Sem["preferred"]],
                         "stable": [sorted(list(S)) for S in Sem["stable"]],
                         "complete": [sorted(list(S)) for S in Sem["complete"]],
                         "stage": [sorted(list(S)) for S in Sem["stage"]],
                         "semi-stable": [sorted(list(S)) for S in Sem["semi-stable"]]}),
                "ids": translate(Sem)
            }
        if query_ans is not None:
            out["query"] = {"arg": args.query, "mode": args.mode, "answer": bool(query_ans)}
        if insights is not None:
            out["insights"] = insights
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # Human-readable
    print("=== NL → APX → clingo (end-to-end) ===")
    print(f"Blocks: {len(ids)} | Edges: {len(attacks)}")
    print("[edge provenance]")
    print(" explicit:", meta.get("explicit_edges") or "(none)")
    print(" heuristic:", meta.get("heuristic_edges") or "(none)")
    print(" llm     :", meta.get("llm_edges") or "(none)")

    def show_sets(label: str, sets):
        if isinstance(sets, frozenset):
            s = ", ".join(sorted(list(sets)))
            print(f"{label}: "+"{"+s+"}")
        else:
            inner = ", ".join("{" + ", ".join(sorted(S)) + "}" for S in sets)
            print(f"{label}: [{inner}]")

    if args.sem == "all":
        print("\n=== Semantics (APX atoms) ===")
        show_sets("Grounded", Sem["grounded"])
        show_sets("Preferred", Sem["preferred"])
        show_sets("Stable", Sem["stable"])
        show_sets("Complete", Sem["complete"])
        show_sets("Stage", Sem["stage"])
        show_sets("Semi-stable", Sem["semi-stable"])
        if args.names in ("ids","both"):
            print("\n--- Same semantics in original IDs ---")
            Sem_ids = translate(Sem)
            for k,v in Sem_ids.items():
                print(k.capitalize()+":", v)
    else:
        label = args.sem.capitalize()
        print(f"\n=== {label} (APX atoms) ===")
        show_sets(label, Sem if isinstance(Sem, list) else [Sem])
        if args.names in ("ids","both"):
            print(f"--- {label} in original IDs ---")
            Sem_ids = translate(Sem)
            print(Sem_ids)

    if args.query and args.mode:
        print(f"\nQuery: {args.mode.capitalize()} acceptance of {args.query}: {'YES' if query_ans else 'NO'}")

    if args.insights:
        print("\n=== Insights ===")
        print(f"Target: {insights['target']}")
        print(f"Grounded core (APX): {{{', '.join(insights['grounded_core'])}}}")
        print("Defense depth:")
        for a in atoms:
            print(f"  {a}: {insights['defense_depth'][a]}")
        print(f"Grounded roadblocks for target: {{{', '.join(insights['grounded_roadblocks'])}}}")
        pa = insights['preferred_attackers_of_target']
        print(f"Preferred attackers of target — persistent: {{{', '.join(pa['persistent'])}}}, soft: {{{', '.join(pa['soft'])}}}")
        cnt = insights['preferred_counts']
        print(f"Preferred count: {cnt['preferred']}  |  Stable count: {cnt['stable']}")

if __name__ == "__main__":
    main()
