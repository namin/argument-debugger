#!/usr/bin/env python3
"""
baf_integrated.py — End-to-end pipeline on a Bipolar Argumentation Framework (BAF)

Goal
----
Unify:
  - Cross-argument ATTACKS from `nl2apx.py` (explicit/heuristic/LLM)
  - Per-argument STRUCTURE from `ad.py` (claims + inferences → SUPPORT)

…into a single BAF. Then (optionally) collapse to a Dung AF using the standard
supported/secondary attack rules and compute Dung-style semantics with `af_clingo.py`.

You can run `ad.py` on ALL blocks, on a SELECTED subset (IDs), or skip it.

Inputs
------
- arguments.txt  (blocks separated by blank lines; optional ATTACKS: lines)

Outputs
-------
- Markdown report (optional)
- JSON with BAF + Semantics (optional)
- APX (collapsed AF) (optional)
- DOT (BAF visualization) (optional)

Requirements
------------
- baf.py             (provided in this repo)
- ad_adapter.py      (provided)  -- requires ad.py & Google GenAI config to function
- nl2apx_adapter.py  (provided)  -- requires nl2apx.py
- af_clingo.py       (your solver)
- nl2apx.py          (your extractor)

Usage examples
--------------
# Run with structure for ALL blocks, collapse and compute all semantics:
python baf_integrated.py arguments.txt --ad all --sem all --md-out report.md --json-out result.json

# Only use cross-argument attacks (no per-argument structure):
python baf_integrated.py arguments.txt --ad none --md --json

# Run structure only for A2 and A3; include supported/secondary attacks during collapse:
python baf_integrated.py arguments.txt --ad ids A2 A3 --collapse supported,secondary --md

# With LLM edges from nl2apx:
python baf_integrated.py arguments.txt --use-llm --llm-mode augment --sem preferred --md
"""
from __future__ import annotations

import json
import sys
import argparse
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set, Optional, Iterable

# Local modules
try:
    import baf as BAFM
    from baf import BAF
except Exception as e:
    print("ERROR: This script requires baf.py in the same directory.", file=sys.stderr)
    raise

try:
    import nl2apx_adapter as NA
    import nl2apx as NL
except Exception as e:
    print("ERROR: This script requires nl2apx_adapter.py and nl2apx.py.", file=sys.stderr)
    raise

# ad is optional if --ad none
_HAVE_AD = False
try:
    import ad_adapter as ADA
    import ad as AD
    _HAVE_AD = True
except Exception:
    _HAVE_AD = False

# clingo-based solver
try:
    import af_clingo
except Exception as e:
    print("ERROR: This script requires af_clingo.py.", file=sys.stderr)
    raise


# ----------------------- small utils -----------------------

def _defense_depth(atoms: List[str], attacks: Set[Tuple[str,str]]):
    """Grounded iteration depth for each atom (for reporting)."""
    atk = {a:set() for a in atoms}
    for (u,v) in attacks:
        atk[v].add(u)

    def F(S: Set[str]) -> Set[str]:
        out = set()
        for a in atoms:
            ok = True
            for b in atk[a]:
                if not any((c,b) in attacks for c in S):
                    ok = False; break
            if ok:
                out.add(a)
        return out

    depth = {a: None for a in atoms}
    S = set(); i = 0
    while True:
        T = F(S)
        if T == S: break
        i += 1
        wave = T - S
        for a in wave:
            if depth[a] is None:
                depth[a] = i
        S = T
    return depth


def _stance_cards(prefs: List[Set[str]], atom2id: Dict[str,str], ids_filter: Optional[Set[str]] = None, limit: int = 4):
    cards = []
    for i, S in enumerate(prefs[:limit], 1):
        members = sorted(atom2id[a] for a in S if (ids_filter is None or atom2id[a] in ids_filter))
        cards.append({"name": f"S{i}", "members": members})
    return cards


def _attackers_of(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> List[str]:
    return sorted({u for (u,v) in attacks if v == target_atom})


def _preferred_coverage(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str):
    PR = af_clingo.preferred(atoms, attacks)
    n = len(PR); k = sum(1 for S in PR if target_atom in S)
    return k, n, (k/n if n>0 else 0.0)


def _preferred_persistent_soft(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str, atom2id: Dict[str,str]):
    PR = af_clingo.preferred(atoms, attacks)
    if not PR:
        return [], []
    inter = set(atoms)
    union = set()
    for S in PR:
        inter &= set(S)
        union |= set(S)
    atk = {a:set() for a in atoms}
    for (u,v) in attacks:
        atk[v].add(u)
    A = atk.get(target_atom, set())
    persistent = sorted([atom2id[a] for a in (inter & A)])
    soft = sorted([atom2id[a] for a in ((union - inter) & A)])
    return persistent, soft


def _is_block_id(baf: BAF, _id: str) -> bool:
    info = baf.nodes.get(_id)
    return bool(info and info.type == "argument")


def _extraction_summary(baf: BAF) -> Dict[str,int]:
    exp = heu = llm = struct = 0
    for (u,v), tags in baf.prov_attack.items():
        if not tags: continue
        if "exp" in tags: exp += 1
        if "heu" in tags: heu += 1
        if "llm" in tags: llm += 1
    for _ in baf.support:
        struct += 1
    return {"explicit": exp, "heuristic": heu, "llm": llm, "support": struct, "total_attacks": len({(u,v) for (u,v,_) in baf.attack})}


def _summarize_issues(baf: BAF) -> Dict[str, Dict[str,int]]:
    """Aggregate issue tags from claim-level nodes back to their block_id."""
    out: Dict[str, Dict[str,int]] = {}
    for nid, info in baf.nodes.items():
        if info.meta.get("issues"):
            # block_id is prefix before first dot if present
            blk = nid.split(".", 1)[0] if "." in nid else nid
            out.setdefault(blk, {})
            for tag in info.meta["issues"]:
                out[blk][tag] = out[blk].get(tag, 0) + 1
    return out


# ----------------------- report (markdown) -----------------------

def markdown_report(title: str,
                    baf: BAF,
                    atoms: List[str],
                    attacks: Set[Tuple[str,str]],
                    id2atom: Dict[str,str],
                    atom2id: Dict[str,str],
                    target_id: Optional[str] = None,
                    max_cards: int = 4) -> str:
    lines = []
    lines.append(f"# {title}")
    lines.append("")

    # Extraction summary
    ex = _extraction_summary(baf)
    lines.append("## Extraction summary")
    lines.append(f"- attacks ⇒ explicit: **{ex['explicit']}**, heuristic: **{ex['heuristic']}**, llm: **{ex['llm']}**")
    lines.append(f"- support (from structure): **{ex['support']}**")
    lines.append(f"- total base attacks: **{ex['total_attacks']}**")
    lines.append("")

    # Arguments (block-level)
    lines.append("## Arguments (block-level)")
    for _id, info in baf.nodes.items():
        if _is_block_id(baf, _id):
            atom = id2atom.get(_id, "?")
            snippet = (info.text or "").strip().replace("\n", " ")
            if len(snippet) > 90: snippet = snippet[:87] + "…"
            lines.append(f"- **{_id}** (`{atom}`): {snippet}")
    lines.append("")

    # Attacks (block-level only for readability)
    lines.append("## Attacks (block→block)")
    base_att = {(u,v) for (u,v,k) in baf.attack}
    for (u,v) in sorted(base_att):
        if _is_block_id(baf, u) and _is_block_id(baf, v):
            tags = ", ".join(baf.prov_attack.get((u,v), []) or [])
            lines.append(f"- {u} → {v} [{tags or 'base'}]")
    if not base_att:
        lines.append("_(none)_")
    lines.append("")

    # Support edges (claim-level → claim/goal/block), summarized by block
    iss = _summarize_issues(baf)
    lines.append("## Structure highlights (by block)")
    if not iss:
        lines.append("_No claim-level issues recorded (run with --ad)._")
    else:
        for blk, counts in iss.items():
            bag = ", ".join(f"{k}:{v}" for k,v in sorted(counts.items()))
            lines.append(f"- **{blk}** — issues: {bag}")
    lines.append("")

    # Semantics table for block-level nodes
    G  = af_clingo.grounded(atoms, attacks)
    PR = af_clingo.preferred(atoms, attacks)
    ST = af_clingo.stable(atoms, attacks)
    CO = af_clingo.complete(atoms, attacks)
    SG = af_clingo.stage(atoms, attacks)
    SS = af_clingo.semi_stable(atoms, attacks)
    depth = _defense_depth(atoms, attacks)

    def in_many(fams, a): return f"{sum(1 for S in fams if a in S)}/{len(fams) or 0}"

    lines.append("## Semantics (block-level)")
    lines.append("| ID | Atom | Grounded | Pref | Stable | Complete | Stage | SemiSt | Depth |")
    lines.append("|---:|:-----|:--------:|:----:|:------:|:--------:|:-----:|:------:|:-----:|")
    for _id, info in sorted(baf.nodes.items()):
        if not _is_block_id(baf, _id): continue
        a = id2atom.get(_id)
        if not a: continue
        row = [
            _id, f"`{a}`",
            "✓" if a in G else "",
            in_many(PR, a),
            in_many(ST, a),
            in_many(CO, a),
            in_many(SG, a),
            in_many(SS, a),
            str(depth.get(a) or "")
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Preferred “stance cards” (block-level)
    blk_ids = {_id for _id in baf.nodes if _is_block_id(baf, _id)}
    cards = _stance_cards(PR, atom2id, ids_filter=blk_ids, limit=max_cards)
    lines.append("## Preferred “stance cards”")
    if cards:
        for c in cards:
            lines.append(f"**{c['name']}** = " + "{" + ", ".join(c['members']) + "}")
    else:
        lines.append("_(none)_")
    lines.append("")

    # Why-not for target
    if target_id and target_id in baf.nodes:
        tgt_atom = id2atom.get(target_id)
        lines.append(f"## Why {target_id} may be out (grounded)")
        # grounded roadblocks: attackers of target not countered by grounded
        Gs = set(G)
        atk = {a:set() for a in atoms}
        for (u,v) in attacks:
            atk[v].add(u)
        road = sorted([atom2id[b] for b in atk.get(tgt_atom, set()) if not any((c,b) in attacks for c in Gs)])
        lines.append(f"- Grounded roadblocks (undefeated attackers): {', '.join(road) or '(none)'}")
        pers, soft = _preferred_persistent_soft(atoms, attacks, tgt_atom, atom2id)
        lines.append(f"- Across preferred: persistent attackers: {', '.join(pers) or '(none)'}; soft attackers: {', '.join(soft) or '(none)'}")
        lines.append("")
    return "\n".join(lines)


# ----------------------- Core runner -----------------------

def run_pipeline(text_path: str,
                 relation_mode: str = "auto",
                 jaccard: float = 0.45,
                 min_overlap: int = 3,
                 use_llm: bool = False,
                 llm_threshold: float = 0.55,
                 llm_mode: str = "augment",
                 ad_mode: str = "none",          # 'none' | 'all' | 'ids'
                 ad_ids: Optional[List[str]] = None,
                 ad_connect_goal: bool = True,
                 collapse_modes: List[str] = ["supported", "secondary"],
                 target_id: Optional[str] = None,
                 max_pref_cards: int = 4):
    """
    Build a BAF from nl2apx edges + optional ad.py structure, collapse to AF, compute semantics.
    """
    # 1) Parse blocks and build cross-argument attacks via nl2apx
    blocks = NL.parse_blocks(text_path)
    ids, id2text, idx_edges, meta = NL.build_edges(
        blocks,
        relation_mode=relation_mode,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    baf = NA.baf_from_nl2apx_edges(ids, id2text, idx_edges, meta)

    # 2) ad.py structure (per-argument) — optional
    selected_ids: List[str] = []
    if ad_mode == "all":
        selected_ids = list(ids)
    elif ad_mode == "ids":
        selected_ids = [i for i in (ad_ids or []) if i in ids]
    elif ad_mode == "none":
        selected_ids = []
    else:
        raise ValueError(f"Unknown --ad mode: {ad_mode}")

    if selected_ids and not _HAVE_AD:
        print("WARNING: --ad requested but ad.py/ad_adapter.py not available; skipping structure.", file=sys.stderr)
        selected_ids = []

    for sid in selected_ids:
        blk_text = id2text.get(sid, "").strip()
        if not blk_text:
            continue
        try:
            b_struct, _ = ADA.baf_from_ad_block(blk_text, sid, connect_goal_to_block=ad_connect_goal)
            baf.merge(b_struct)
        except Exception as e:
            print(f"WARNING: ad_adapter failed on {sid}: {e}", file=sys.stderr)

    # Optional: compress equivalences
    if getattr(baf, "equiv", None):
        baf.compress_equivalences()

    # 3) Collapse to AF
    include_supported = ("supported" in (collapse_modes or []))
    include_secondary = ("secondary" in (collapse_modes or []))
    atoms, attacks, id2atom, atom2id = baf.collapse_to_af(include_supported=include_supported,
                                                          include_secondary=include_secondary)

    # 4) Semantics
    G  = af_clingo.grounded(atoms, attacks)
    PR = af_clingo.preferred(atoms, attacks)
    ST = af_clingo.stable(atoms, attacks)
    CO = af_clingo.complete(atoms, attacks)
    SG = af_clingo.stage(atoms, attacks)
    SS = af_clingo.semi_stable(atoms, attacks)

    # 5) Preferred stance cards (block-level)
    blk_ids = {_id for _id in baf.nodes if _is_block_id(baf, _id)}
    cards = _stance_cards(PR, atom2id, ids_filter=blk_ids, limit=max_pref_cards)

    # 6) Why-not target
    insights = {}
    if target_id and target_id in baf.nodes:
        tgt_atom = id2atom[target_id]
        k, n, frac = _preferred_coverage(atoms, attacks, tgt_atom)
        pers, soft = _preferred_persistent_soft(atoms, attacks, tgt_atom, atom2id)
        insights["target"] = {
            "id": target_id,
            "preferred_coverage": {"k": k, "n": n, "frac": frac},
            "persistent_attackers": pers,
            "soft_attackers": soft
        }

    return {
        "baf": baf,
        "collapsed": {
            "atoms": atoms,
            "attacks": sorted(list(attacks)),
            "id2atom": id2atom,
            "atom2id": atom2id,
        },
        "semantics": {
            "grounded": sorted([atom2id[a] for a in G]),
            "preferred": [sorted([atom2id[a] for a in S]) for S in PR],
            "stable": [sorted([atom2id[a] for a in S]) for S in ST],
            "complete": [sorted([atom2id[a] for a in S]) for S in CO],
            "stage": [sorted([atom2id[a] for a in S]) for S in SG],
            "semi_stable": [sorted([atom2id[a] for a in S]) for S in SS],
            "preferred_cards": cards,
        },
        "insights": insights,
        "extraction": _extraction_summary(baf),
    }


# ----------------------- CLI -----------------------

def main():
    ap = argparse.ArgumentParser(description="BAF-integrated pipeline: nl2apx (attacks) + ad (support) → collapse → semantics")
    ap.add_argument("file", help="arguments.txt (blocks separated by blank lines)")

    # Extraction controls (nl2apx)
    ap.add_argument("--relation", choices=["auto","explicit","none"], default="auto", help="edge source policy for nl2apx")
    ap.add_argument("--use-llm", action="store_true", help="enable LLM edges in nl2apx")
    ap.add_argument("--llm-mode", choices=["augment","override"], default="augment")
    ap.add_argument("--llm-threshold", type=float, default=0.55)
    ap.add_argument("--jaccard", type=float, default=0.45)
    ap.add_argument("--min-overlap", type=int, default=3)

    # ad.py integration
    ap.add_argument("--ad", choices=["none","all","ids"], default="none", help="run ad.py structure extraction per block")
    ap.add_argument("--ad-ids", nargs="*", default=None, help="IDs to run with --ad ids")
    ap.add_argument("--ad-no-goal-link", action="store_true", help="do NOT connect the goal claim ⇒ block")

    # Collapse behavior
    ap.add_argument("--collapse", default="supported,secondary", help="comma-separated: supported,secondary,none")
    ap.add_argument("--no-collapse", action="store_true", help="alias for --collapse none")

    # Reasoning
    ap.add_argument("--sem", choices=["all","grounded","preferred","stable","complete","stage","semi-stable"], default="all")
    ap.add_argument("--target", default=None, help="focus ID for why-not/coverage")

    # Outputs
    ap.add_argument("--md", action="store_true", help="print Markdown to stdout")
    ap.add_argument("--md-out", default=None, help="write Markdown to file")
    ap.add_argument("--json", action="store_true", help="print JSON to stdout")
    ap.add_argument("--json-out", default=None, help="write JSON to file")
    ap.add_argument("--apx-out", default=None, help="write collapsed AF as APX")
    ap.add_argument("--dot-out", default=None, help="write BAF as DOT (support dashed, attacks solid)")

    args = ap.parse_args()

    collapse_modes = [] if args.no_collapse or args.collapse.strip().lower()=="none" else [s.strip() for s in args.collapse.split(",") if s.strip()]

    res = run_pipeline(
        text_path=args.file,
        relation_mode=args.relation,
        jaccard=args.jaccard,
        min_overlap=args.min_overlap,
        use_llm=args.use_llm,
        llm_threshold=args.llm_threshold,
        llm_mode=args.llm_mode,
        ad_mode=args.ad,
        ad_ids=args.ad_ids,
        ad_connect_goal=(not args.ad_no_goal_link),
        collapse_modes=collapse_modes,
        target_id=args.target,
    )

    baf: BAF = res["baf"]
    atoms = res["collapsed"]["atoms"]
    attacks = set(tuple(x) for x in res["collapsed"]["attacks"])
    id2atom = res["collapsed"]["id2atom"]
    atom2id = res["collapsed"]["atom2id"]

    # Markdown
    if args.md or args.md_out:
        title = "BAF Integrated Report"
        md = markdown_report(title, baf, atoms, attacks, id2atom, atom2id, target_id=args.target, max_cards=4)
        if args.md:
            print(md)
        if args.md_out:
            with open(args.md_out, "w", encoding="utf-8") as f:
                f.write(md)

    # JSON
    if args.json or args.json_out:
        # serialize BAF lightly
        baf_json = {
            "nodes": { nid: {"text": info.text, "type": info.type, "meta": info.meta}
                       for nid, info in baf.nodes.items() },
            "support": sorted(list(baf.support)),
            "attack": sorted(list({(u,v,k) for (u,v,k) in baf.attack})),
            "prov_attack": { f"{u}→{v}": tags for (u,v), tags in baf.prov_attack.items() },
            "extraction": res["extraction"],
        }
        payload = {
            "baf": baf_json,
            "collapsed": res["collapsed"],
            "semantics": res["semantics"],
            "insights": res["insights"],
        }
        out = json.dumps(payload, indent=2, ensure_ascii=False)
        if args.json:
            print(out)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as f:
                f.write(out)

    # APX
    if args.apx_out:
        inc_sup = ("supported" in collapse_modes)
        inc_sec = ("secondary" in collapse_modes)
        apx = baf.to_apx(include_supported=inc_sup, include_secondary=inc_sec)
        with open(args.apx_out, "w", encoding="utf-8") as f:
            f.write(apx)

    # DOT
    if args.dot_out:
        inc_sup = ("supported" in collapse_modes)
        inc_sec = ("secondary" in collapse_modes)
        dot = baf.to_dot(show_implied=True, include_supported=inc_sup, include_secondary=inc_sec)
        with open(args.dot_out, "w", encoding="utf-8") as f:
            f.write(dot)


if __name__ == "__main__":
    main()
