#!/usr/bin/env python3
"""
argsem.py — Unified end-to-end Argumentation Semantics runner

Combines the roles of:
  - as_pretty.py  (human-friendly Markdown report tied to the original text)
  - as_end2end.py (programmatic JSON + APX/DOT export)

Pipeline:
  Text blocks (with optional ID:/ATTACKS:)  →  AF (via nl2apx)  →  Semantics (via af_clingo)
Outputs:
  - Markdown report (pretty) and/or JSON
  - Optional APX file and DOT graph
  - Queries (credulous/skeptical) and Insights (roadblocks, depth, persistent/soft)

Dependencies:
  - nl2apx.py     (natural language → AF/APX) — must be importable in PYTHONPATH
  - af_clingo.py  (clingo-backed semantics)   — must be importable in PYTHONPATH
  - clingo (Python package)
  - Optional: google.genai (Gemini) for LLM summaries

Usage examples:
  # Human-readable Markdown with explicit edges only
  python argsem.py arguments.txt --relation explicit --target A1 --md-out report.md

  # LLM edge inference + JSON + APX + DOT
  python argsem.py examples_llm_messy.txt --use-llm --sem all --json-out result.json --apx-out graph.apx --dot af.dot

  # Both Markdown + JSON to stdout (no files)
  python argsem.py arguments.txt --use-llm --md --json

  # Query acceptance (preferred by default for --sem all)
  python argsem.py arguments.txt --use-llm --query A2 --mode credulous --json
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Set, Tuple, FrozenSet, Optional

import nl2apx
import af_clingo

# -------- Optional LLM summary support (Gemini), graceful fallback --------
_HAVE_LLM = False
try:
    from google import genai
    from google.genai import types
    _HAVELLMPKG = True
except Exception:
    _HAVELLMPKG = False

def _llm_client_or_none():
    if not _HAVELLMPKG:
        return None
    try:
        api = os.getenv("GEMINI_API_KEY")
        proj = os.getenv("GOOGLE_CLOUD_PROJECT")
        loc  = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if api:
            return genai.Client(api_key=api)
        if proj:
            return genai.Client(vertexai=True, project=proj, location=loc)
    except Exception:
        return None
    return None

def _short(s: str, n: int = 140) -> str:
    s1 = " ".join(str(s).split())
    return s1 if len(s1) <= n else s1[: n-1] + "…"

# -------- Build AF in memory from text (uses nl2apx) --------
def build_af(path: str,
             relation: str = "auto",
             jaccard: float = 0.45,
             min_overlap: int = 3,
             use_llm: bool = False,
             llm_threshold: float = 0.55,
             llm_mode: str = "augment"):
    blocks = nl2apx.parse_blocks(path)
    ids, id_to_text, idx_edges, meta = nl2apx.build_edges(
        blocks,
        relation_mode=relation,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    atoms = nl2apx.make_unique([nl2apx.sanitize_atom(i) for i in ids])
    id2atom = {ids[i]: atoms[i] for i in range(len(ids))}
    atom2id = {v:k for k,v in id2atom.items()}
    attacks = set((atoms[i], atoms[j]) for (i,j) in idx_edges)
    return ids, id_to_text, atoms, id2atom, atom2id, attacks, meta

# -------- Insights helpers (grounded roadblocks, depth, persistent/soft) --------
def _F(atoms: List[str], attacks: Set[Tuple[str,str]], S: Set[str]) -> Set[str]:
    atk = {a:set() for a in atoms}
    for (u,v) in attacks:
        if v in atk: atk[v].add(u)
    defended = set()
    for a in atoms:
        ok = True
        for b in atk[a]:
            if not any((c,b) in attacks for c in S):
                ok = False; break
        if ok:
            defended.add(a)
    return defended

def defense_depth(atoms: List[str], attacks: Set[Tuple[str,str]]) -> Dict[str, Optional[int]]:
    depth = {a: None for a in atoms}
    S = set(); i = 0
    while True:
        T = _F(atoms, attacks, S)
        if T == S: break
        wave = T - S; i += 1
        for a in wave:
            if depth[a] is None: depth[a] = i
        S = T
    return depth

def grounded_roadblocks(atoms: List[str], attacks: Set[Tuple[str,str]], target: str) -> List[str]:
    G = set(af_clingo.grounded(atoms, attacks))
    if target in G: return []
    atk = {a:set() for a in atoms}
    for (u,v) in attacks:
        atk[v].add(u)
    return sorted([b for b in atk.get(target, set())
                   if not any((c,b) in attacks for c in G)])

def preferred_persistent_soft(atoms: List[str], attacks: Set[Tuple[str,str]], target: str):
    prefs = af_clingo.preferred(atoms, attacks)
    if not prefs:
        return [], []
    inter = set(atoms); union = set()
    for S in prefs:
        inter &= set(S); union |= set(S)
    atk = {a:set() for a in atoms}
    for (u,v) in attacks:
        atk[v].add(u)
    A = atk.get(target, set())
    return sorted(list(inter & A)), sorted(list((union - inter) & A))

# -------- Naming translation --------
def translate_set(S: FrozenSet[str], atom2id: Dict[str,str]) -> List[str]:
    return sorted([atom2id.get(a, a) for a in S])

def translate_sets(sets: List[FrozenSet[str]], atom2id: Dict[str,str]) -> List[List[str]]:
    return [translate_set(S, atom2id) for S in sets]

# -------- Provenance tags on edges --------
def _edge_provenance(meta: Dict) -> Dict[Tuple[int,int], List[str]]:
    prov: Dict[Tuple[int,int], List[str]] = {}
    def add(lst, tag):
        for e in lst or []:
            prov.setdefault(tuple(e), []).append(tag)
    add(meta.get("explicit_edges"), "exp")
    add(meta.get("heuristic_edges"), "heu")
    add(meta.get("llm_edges"), "llm")
    return prov

# -------- Markdown report --------
def markdown_report(path: str,
                    ids: List[str],
                    id2text: Dict[str,str],
                    atoms: List[str],
                    id2atom: Dict[str,str],
                    atom2id: Dict[str,str],
                    attacks: Set[Tuple[str,str]],
                    meta: Dict,
                    target_id: Optional[str] = None,
                    stance_limit: int = 4,
                    llm_summarize: bool = False) -> str:
    # Semantics
    G  = af_clingo.grounded(atoms, attacks)
    PR = af_clingo.preferred(atoms, attacks)
    ST = af_clingo.stable(atoms, attacks)
    CO = af_clingo.complete(atoms, attacks)
    SG = af_clingo.stage(atoms, attacks)
    SS = af_clingo.semi_stable(atoms, attacks)

    # Per-argument membership & depth
    depth = defense_depth(atoms, attacks)
    def in_many(fams: List[FrozenSet[str]], a: str) -> str:
        return f"{sum(1 for S in fams if a in S)}/{len(fams) or 0}"
    row = {a: {
        "grounded": (a in G),
        "preferred": in_many(PR, a),
        "stable":    in_many(ST, a),
        "complete":  in_many(CO, a),
        "stage":     in_many(SG, a),
        "semistable": in_many(SS, a),
        "depth": depth[a]
    } for a in atoms}

    # Edges with provenance
    idx_map = {ids[i]: i for i in range(len(ids))}
    prov_idx = _edge_provenance(meta)
    edge_lines = []
    for (u,v) in sorted(attacks):
        uid, vid = atom2id[u], atom2id[v]
        ui, vi = idx_map.get(uid), idx_map.get(vid)
        tags = prov_idx.get((ui,vi), []) if (ui is not None and vi is not None) else []
        label = (" [" + ",".join(tags) + "]") if tags else ""
        edge_lines.append(f"- {uid} ({u}) → {vid} ({v}){label}")

    # Target & blockers
    tgt_id = target_id if (target_id in ids) else (ids[0] if ids else None)
    tgt_atom = id2atom.get(tgt_id) if tgt_id else None
    road = grounded_roadblocks(atoms, attacks, tgt_atom) if tgt_atom else []
    pers, soft = preferred_persistent_soft(atoms, attacks, tgt_atom) if tgt_atom else ([], [])

    # Preferred stance cards
    cards = []
    for i, S in enumerate(PR[:stance_limit], 1):
        ids_in = [atom2id[a] for a in sorted(S)]
        preview = "; ".join(_short(id2text[_id], 60) for _id in ids_in[:3] if _id in id2text)
        cards.append(f"**S{i}** = {{{', '.join(ids_in)}}}\n  - preview: {preview}")

    # Optional LLM summary
    summary = ""
    if llm_summarize:
        client = _llm_client_or_none()
        if client:
            try:
                listing = "\n".join([f"{_id}: {_short(id2text[_id], 140)}" for _id in ids])
                G_ids = ", ".join(sorted(atom2id[a] for a in G))
                P_ids = "; ".join("{" + ", ".join(sorted(atom2id[a] for a in S)) + "}" for S in PR[:stance_limit])
                prompt = f"""
You summarize a Dung-style debate result for a human audience.
Arguments (ID: text):
{listing}

Grounded core: {G_ids if G_ids else "(empty)"}
Preferred samples: {P_ids if P_ids else "(none)"}
Target: {tgt_id or "(none)"}; Grounded roadblocks: {", ".join(road) if road else "(none)"}.
Write 4–6 sentences: 1–2 about the grounded core (safe consensus), 2–3 about the stances (how they differ),
and one sentence about what blocks the target (if any). Avoid jargon.
"""
                cfg = types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_budget=0))
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
                summary = resp.text.strip()
            except Exception as e:
                summary = f"(LLM summary unavailable: {e})"

    # Render markdown
    lines = []
    lines.append(f"# Argumentation Semantics Report — {os.path.basename(path)}\n")
    lines.append("## Arguments (ID → APX atom)")
    for _id in ids:
        a = id2atom[_id]
        lines.append(f"- **{_id}** ({a}): {_short(id2text[_id], 140)}")
    lines.append("\n## Attacks")
    lines.extend(edge_lines if edge_lines else ["(none)"])

    lines.append("\n## Semantics (membership & depth)")
    lines.append("| ID | Atom | Grounded | Pref | Stable | Complete | Stage | SemiSt | Depth |")
    lines.append("|---:|:-----|:--------:|:----:|:------:|:--------:|:-----:|:------:|:-----:|")
    for _id in ids:
        a = id2atom[_id]; r = row[a]
        lines.append(f"| {_id} | `{a}` | {'✓' if r['grounded'] else ''} | {r['preferred']} | {r['stable']} | {r['complete']} | {r['stage']} | {r['semistable']} | {r['depth'] if r['depth'] is not None else ''} |")

    if PR:
        lines.append("\n## Preferred “stance cards”")
        lines.extend(cards)

    if tgt_id:
        lines.append(f"\n## Why {tgt_id} may be out (grounded)")
        lines.append(f"- Grounded roadblocks (undefeated attackers): {', '.join(road) if road else '(none)'}")
        lines.append(f"- Across preferred: persistent attackers: {', '.join(pers) if pers else '(none)'}; soft attackers: {', '.join(soft) if soft else '(none)'}")

    if summary:
        lines.append("\n## Narrative (LLM)")
        lines.append(summary)

    return "\n".join(lines) + "\n"

# -------- CLI --------
def main():
    ap = argparse.ArgumentParser(description="argsem.py — unified end-to-end AF extraction + clingo semantics + reports")
    ap.add_argument("path", help="Text file of arguments (blocks separated by blank lines)")

    # Extraction controls
    ap.add_argument("--relation", default="auto", choices=["auto","explicit","none"], help="Use ATTACKS or induce by heuristics; 'auto' uses ATTACKS if present else heuristics.")
    ap.add_argument("--jaccard", type=float, default=0.45, help="Heuristic Jaccard threshold (auto mode).")
    ap.add_argument("--min-overlap", type=int, default=3, help="Heuristic min shared content tokens (auto mode).")
    ap.add_argument("--use-llm", action="store_true", help="Use LLM for edge inference.")
    ap.add_argument("--llm-threshold", type=float, default=0.55, help="Confidence cutoff for LLM edges.")
    ap.add_argument("--llm-mode", default="augment", choices=["augment","override"], help="Augment (union) or override other edges with LLM edges.")

    # Semantics & queries
    ap.add_argument("--sem", default="all", choices=["grounded","preferred","stable","complete","stage","semi-stable","semistable","all"], help="Which semantics to compute (controls JSON content; Markdown always shows multiple).")
    ap.add_argument("--query", type=str, default=None, help="Acceptance query for an argument (ID or APX atom).")
    ap.add_argument("--mode", type=str, default=None, choices=["credulous","skeptical"], help="Query mode.")

    # Outputs
    ap.add_argument("--apx-out", type=str, default=None, help="Write generated APX to this path.")
    ap.add_argument("--dot", type=str, default=None, help="Export DOT graph (APX atoms).")
    ap.add_argument("--names", default="apx", choices=["apx","ids","both"], help="Name scheme in JSON semantics (APX atoms, original IDs, or both).")

    # Report channels
    ap.add_argument("--md", action="store_true", help="Print Markdown report to stdout.")
    ap.add_argument("--md-out", type=str, default=None, help="Write Markdown report to file.")
    ap.add_argument("--json", action="store_true", help="Print JSON to stdout.")
    ap.add_argument("--json-out", type=str, default=None, help="Write JSON to file.")

    # Pretty options
    ap.add_argument("--target", type=str, default=None, help="Target ID for why-not analysis (Markdown & JSON insights).")
    ap.add_argument("--llm-summarize", action="store_true", help="Ask LLM to add a short narrative to Markdown.")
    ap.add_argument("--max-pref-cards", type=int, default=4, help="Limit number of preferred 'stance cards' in Markdown.")
    args = ap.parse_args()

    # 1) Build AF (in memory)
    ids, id2text, atoms, id2atom, atom2id, attacks, meta = build_af(
        args.path,
        relation=args.relation, jaccard=args.jaccard, min_overlap=args.min_overlap,
        use_llm=args.use_llm, llm_threshold=args.llm_threshold, llm_mode=args.llm_mode
    )

    # 2) Optionally write APX and DOT
    if args.apx_out:
        # reconstruct index edges so we can reuse nl2apx.emit_apx
        idx_map = {ids[i]: i for i in range(len(ids))}
        idx_edges = set()
        for (u,v) in attacks:
            uid, vid = atom2id[u], atom2id[v]
            if uid in idx_map and vid in idx_map:
                idx_edges.add((idx_map[uid], idx_map[vid]))
        with open(args.apx_out, "w", encoding="utf-8") as f:
            f.write(nl2apx.emit_apx(ids, id2text, idx_edges, provenance=meta))
    if args.dot:
        af_clingo.export_dot(atoms, attacks, args.dot)

    # 3) Solve semantics with clingo
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

    # 4) Queries
    query_ans = None
    if args.query and args.mode:
        q = args.query
        q_atom = id2atom.get(q, q)  # accept ID or atom
        fam = None
        if args.sem == "grounded":
            fam = [Sem] if isinstance(Sem, frozenset) else [af_clingo.grounded(atoms, attacks)]
        elif args.sem == "all":
            fam = Sem["preferred"]
        else:
            fam = Sem if isinstance(Sem, list) else [Sem]
        query_ans = (af_clingo.credulous(fam, q_atom) if args.mode == "credulous"
                     else af_clingo.skeptical(fam, q_atom))

    # 5) Insights (for both JSON and Markdown)
    tgt_id = args.target if (args.target in ids) else (ids[0] if ids else None)
    tgt_atom = id2atom.get(tgt_id) if tgt_id else None
    depth = defense_depth(atoms, attacks)
    G_core = sorted(list(af_clingo.grounded(atoms, attacks)))
    rb   = grounded_roadblocks(atoms, attacks, tgt_atom) if tgt_atom else []
    pers, soft = preferred_persistent_soft(atoms, attacks, tgt_atom) if tgt_atom else ([], [])

    # 6) JSON output
    def translate(obj):
        if isinstance(obj, frozenset): return translate_set(obj, atom2id)
        if isinstance(obj, list):      return [translate_set(S, atom2id) for S in obj]
        if isinstance(obj, dict):      return {k: translate(v) for (k,v) in obj.items()}
        return obj

    if args.json or args.json_out:
        payload = {
            "input": {
                "path": args.path,
                "ids": ids,
                "id_to_atom": id2atom,
                "meta": meta,
            },
            "af": {
                "atoms": atoms,
                "attacks": sorted(list(attacks)),
            },
            "semantics": None,
            "insights": {
                "target": {"id": tgt_id, "atom": tgt_atom},
                "grounded_core": G_core,
                "defense_depth": depth,
                "grounded_roadblocks": rb,
                "preferred_attackers_of_target": {"persistent": pers, "soft": soft},
            }
        }
        if args.names == "apx":
            if args.sem == "all":
                payload["semantics"] = {
                    "grounded": sorted(list(Sem["grounded"])),
                    "preferred": [sorted(list(S)) for S in Sem["preferred"]],
                    "stable": [sorted(list(S)) for S in Sem["stable"]],
                    "complete": [sorted(list(S)) for S in Sem["complete"]],
                    "stage": [sorted(list(S)) for S in Sem["stage"]],
                    "semi-stable": [sorted(list(S)) for S in Sem["semi-stable"]],
                }
            else:
                payload["semantics"] = (sorted(list(Sem)) if isinstance(Sem, frozenset)
                                        else [sorted(list(S)) for S in Sem])
        elif args.names == "ids":
            payload["semantics"] = translate(Sem)
            payload["af"]["attacks_ids"] = [(atom2id[u], atom2id[v]) for (u,v) in payload["af"]["attacks"]]
        else:
            payload["semantics"] = {"apx": None, "ids": None}
            if args.sem == "all":
                payload["semantics"]["apx"] = {
                    "grounded": sorted(list(Sem["grounded"])),
                    "preferred": [sorted(list(S)) for S in Sem["preferred"]],
                    "stable": [sorted(list(S)) for S in Sem["stable"]],
                    "complete": [sorted(list(S)) for S in Sem["complete"]],
                    "stage": [sorted(list(S)) for S in Sem["stage"]],
                    "semi-stable": [sorted(list(S)) for S in Sem["semi-stable"]],
                }
            else:
                payload["semantics"]["apx"] = (sorted(list(Sem)) if isinstance(Sem, frozenset)
                                               else [sorted(list(S)) for S in Sem])
            payload["semantics"]["ids"] = translate(Sem)
            payload["af"]["attacks_ids"] = [(atom2id[u], atom2id[v]) for (u,v) in payload["af"]["attacks"]]

        if query_ans is not None:
            payload["query"] = {"arg": args.query, "mode": args.mode, "answer": bool(query_ans)}

        if args.json and not args.json_out:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as jf:
                jf.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    # 7) Markdown report
    if args.md or args.md_out or (not args.json and not args.json_out):
        md = markdown_report(args.path, ids, id2text, atoms, id2atom, atom2id, attacks, meta,
                             target_id=tgt_id, stance_limit=args.max_pref_cards, llm_summarize=args.llm_summarize)
        if args.md:
            print(md, end="")
        if args.md_out:
            with open(args.md_out, "w", encoding="utf-8") as mf:
                mf.write(md)

if __name__ == "__main__":
    main()
