#!/usr/bin/env python3
# ad_on_winners.py — standalone CLI to analyze AF winners with ad.py
from __future__ import annotations
import argparse, json, sys
from typing import Dict, List, Set, Tuple

import nl2apx as NL
import af_clingo
try:
    import ad as AD
    HAVE_AD = True
except Exception:
    HAVE_AD = False

def sanitize_atom(s: str) -> str:
    import re
    s0 = s.strip().lower()
    s1 = re.sub(r"[^a-z0-9_]+", "_", s0)
    if not re.match(r"^[a-z]", s1):
        s1 = "n_" + s1
    s1 = re.sub(r"__+", "_", s1).strip("_")
    return s1 or "n"

def build_af(path: str, relation="auto", jaccard=0.45, min_overlap=3, use_llm=False, llm_threshold=0.55, llm_mode="augment"):
    blocks = NL.parse_blocks(path)
    ids, id2text, idx_edges, meta = NL.build_edges(
        blocks,
        relation_mode=relation,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    id2atom = {}; used=set()
    for _id in ids:
        a = sanitize_atom(_id); k=a; j=1
        while k in used: j+=1; k=f"{a}_{j}"
        id2atom[_id]=k; used.add(k)
    atom2id = {v:k for k,v in id2atom.items()}
    attacks=set()
    L=list(ids)
    for (i,j) in idx_edges:
        attacks.add((id2atom[L[i]], id2atom[L[j]]))
    atoms=[id2atom[_id] for _id in ids]
    return ids, id2text, atoms, attacks, id2atom, atom2id, meta

def winners(atoms, attacks, mode):
    mode=(mode or "preferred").lower()
    if mode=="grounded": return [set(af_clingo.grounded(atoms, attacks))]
    if mode=="preferred": return [set(S) for S in af_clingo.preferred(atoms, attacks)]
    if mode=="stable": return [set(S) for S in af_clingo.stable(atoms, attacks)]
    if mode=="complete": return [set(S) for S in af_clingo.complete(atoms, attacks)]
    if mode=="stage": return [set(S) for S in af_clingo.stage(atoms, attacks)]
    if mode in ("semi-stable","semistable","semi_stable"): return [set(S) for S in af_clingo.semi_stable(atoms, attacks)]
    raise ValueError(mode)

def stance_text(members_ids: List[str], id2text: Dict[str,str]) -> str:
    return "\n\n".join([(id2text.get(mid) or "").strip() for mid in members_ids if (id2text.get(mid) or "").strip()]).strip()

def analyze_stance(text: str, want_repair: bool=False):
    if not HAVE_AD: return {"error":"ad.py not available"}
    parser = AD.ArgumentParser()
    argument = parser.parse_argument(text)
    issues = AD.ASPDebugger(debug=False).analyze(argument)
    out={
        "claims":[{"id":c.id,"type":c.type,"content":c.content} for c in argument.claims],
        "inferences":[{"from":i.from_claims,"to":i.to_claim,"rule_type":i.rule_type} for i in argument.inferences],
        "goal_claim": argument.goal_claim,
        "issues":[{"type":it.type,"desc":it.description,"claims":it.involved_claims} for it in issues],
        "issue_counts": {it.type:0 for it in issues}
    }
    for it in issues: out["issue_counts"][it.type]=out["issue_counts"].get(it.type,0)+1
    if want_repair and issues:
        rep = AD.RepairGenerator(debug=False)
        comm, clean = rep.generate_repair(text, argument, issues)
        out["repair"]={"commentary":comm,"clean_argument":clean}
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--relation", choices=["auto","explicit","none"], default="auto")
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--llm-mode", choices=["augment","override"], default="augment")
    ap.add_argument("--llm-threshold", type=float, default=0.55)
    ap.add_argument("--jaccard", type=float, default=0.45)
    ap.add_argument("--min-overlap", type=int, default=3)
    ap.add_argument("--winners", choices=["preferred","stable","grounded","complete","stage","semi-stable"], default="preferred")
    ap.add_argument("--limit-stances", type=int, default=5)
    ap.add_argument("--repair-stance", action="store_true")
    ap.add_argument("--json", action="store_true")
    args=ap.parse_args()

    ids, id2text, atoms, attacks, id2atom, atom2id, meta = build_af(args.file, args.relation, args.jaccard, args.min_overlap, args.use_llm, args.llm_threshold, args.llm_mode)
    ext = winners(atoms, attacks, args.winners)
    if args.limit_stances and len(ext) > args.limit_stances:
        ext = ext[:args.limit_stances]
    stances=[]
    for i,S in enumerate(ext,1):
        mids = sorted([atom2id[a] for a in S])
        text = stance_text(mids, id2text)
        ad_res = analyze_stance(text, want_repair=args.repair_stance) if text else {"error":"empty stance text"}
        stances.append({"name":f"S{i}", "members_ids":mids, "ad":ad_res})

    if args.json:
        print(json.dumps({"stances": stances}, indent=2, ensure_ascii=False))
    else:
        print(f"# Winning sets analyzed by ad.py\n\n- semantics: {args.winners}\n")
        for S in stances:
            mids = S["members_ids"]
            print(f"## {S['name']} — {{ " + ", ".join(mids) + " }}\n")
            ad=S["ad"]
            if ad.get("error"):
                print(f"_ad.py analysis skipped: {ad['error']}_\n")
                continue
            print(f"claims: {len(ad.get('claims',[]))}, inferences: {len(ad.get('inferences',[]))}, goal: {ad.get('goal_claim') or '—'}\n")
            print("**Issues**", ad.get("issue_counts"))
