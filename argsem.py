#!/usr/bin/env python3
"""
argsem.py — Unified AF extraction + clingo semantics + reporting (+ optional repair via --repair)

- Normal mode (default): compute semantics, show pretty Markdown and/or JSON; optional APX/DOT.
- Repair mode (--repair): plan + generate + verify a preferred-credulous, add-nodes-only repair
  and produce an integrated BEFORE/AFTER report in one go.

Requires:
  - nl2apx.py and af_clingo.py importable (same folder recommended)
  - clingo (Python package)
  - Optional: google.genai (Gemini) for LLM narrative (--llm-summarize) and LLM-generated defender text (--llm-generate)

Usage (no repair):
  python argsem.py arguments.txt --relation explicit --target A1 --md-out report.md
  python argsem.py examples.txt --use-llm --sem all --json-out result.json --apx-out graph.apx --dot af.dot

Usage (with repair as a flag):
  python argsem.py arguments_nontrivial.txt --repair --target A1 --relation explicit --k 1 \
    --md-out repair_report.md --json-out repair_plan.json

Notes:
  - In repair mode, APX/DOT flags refer to the AFTER (repaired) AF.
  - To also export BEFORE AF, use --apx-out-before/--dot-before.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Set, Tuple, FrozenSet, Optional

import nl2apx
import af_clingo

# -------- Optional LLM support (Gemini), graceful fallback --------
_HAVE_GENAI = False
try:
    from google import genai
    from google.genai import types
    _HAVE_GENAI = True
except Exception:
    _HAVE_GENAI = False

def _llm_client_or_none():
    if not _HAVE_GENAI:
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
        preview = "; ".join(_short(id2text.get(_id, ""), 60) for _id in ids_in[:3])
        cards.append(f"**S{i}** = {{{', '.join(ids_in)}}}\n  - preview: {preview}")

    # Optional LLM summary
    summary = ""
    if llm_summarize:
        client = _llm_client_or_none()
        if client:
            try:
                listing = "\n".join([f"{_id}: {_short(id2text.get(_id, ''), 140)}" for _id in ids])
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
        txt = id2text.get(_id, "(new)")
        lines.append(f"- **{_id}** ({a}): {_short(txt, 140)}")
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

# -------- Repair planning helpers (preferred-credulous, add-nodes-only) --------
def attackers_of(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> List[str]:
    return sorted({u for (u,v) in attacks if v == target_atom})

def preferred_accepts(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> bool:
    prefs = af_clingo.preferred(atoms, attacks)
    return any(target_atom in S for S in prefs)

def preferred_coverage(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> Tuple[int,int,float]:
    prefs = af_clingo.preferred(atoms, attacks)
    n = len(prefs)
    if n == 0:
        return (0, 0, 0.0)
    k = sum(1 for S in prefs if target_atom in S)
    return (k, n, k/n if n > 0 else 0.0)

def preferred_attacker_frequencies(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> Dict[str, int]:
    prefs = af_clingo.preferred(atoms, attacks)
    counts = {a: 0 for a in atoms}
    for S in prefs:
        for a in S:
            counts[a] += 1
    return {b: counts.get(b, 0) for b in attackers_of(atoms, attacks, target_atom)}

def group_blockers(blockers: List[str], k: int, fanout: int) -> List[List[str]]:
    if not blockers or k <= 0:
        return []
    if fanout <= 0:
        return [blockers[:]] if k >= 1 else []
    if fanout == 1:
        return [[b] for b in blockers[:k]]
    gcount = min(k, max(1, (len(blockers)+fanout-1)//fanout))
    groups = [[] for _ in range(gcount)]
    i = 0
    for b in blockers:
        groups[i % gcount].append(b); i += 1
    return groups

def next_new_ids(existing_ids: List[str], n: int, prefix: str = "R") -> List[str]:
    base = 1; used = set(existing_ids); out = []
    while len(out) < n:
        cand = f"{prefix}{base}"
        if cand not in used:
            out.append(cand); used.add(cand)
        base += 1
    return out

def text_for_group_llm(group_ids: List[str], id_to_text: Dict[str,str]) -> str:
    client = _llm_client_or_none()
    if not client: return ""
    listing = "\n".join([f"- {gid}: {id_to_text.get(gid,'').strip()}" for gid in group_ids])
    prompt = f"""
You are drafting a concise defender claim that undermines ALL of the following claims:

{listing}

Write 1–2 sentences that directly target their shared flaw (overgeneralization, missing assumptions, counterevidence, limiting conditions, etc.).
The text must be assertive and specific, without hedging or rhetorical flourishes.
Do NOT restate the original claims. Output only the new defender text.
"""
    cfg = types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_budget=0))
    try:
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
        return (resp.text or "").strip()
    except Exception:
        return ""

def text_for_group_template(group_ids: List[str], id_to_text: Dict[str,str]) -> str:
    return ("This claim relies on a contested assumption and overlooks countervailing evidence that limits its conclusion in this context."
            if len(group_ids) == 1 else
            "These claims share a contested assumption and ignore limiting conditions; taken together, they overstate their conclusion in this context.")

def build_new_blocks(new_ids: List[str], groups_ids: List[List[str]], id_to_text: Dict[str,str],
                     use_llm_text: bool = False) -> List[str]:
    blocks = []
    for nid, gids in zip(new_ids, groups_ids):
        attacks_line = "ATTACKS: " + ", ".join(gids)
        body = text_for_group_llm(gids, id_to_text) if use_llm_text else ""
        if not body.strip():
            body = text_for_group_template(gids, id_to_text)
        block = f"ID: {nid}\n{attacks_line}\n{body.strip()}\n"
        blocks.append(block)
    return blocks

def verify_after(original_path: str, new_blocks: List[str], target_id: str) -> Dict:
    tmp_path = original_path + ".repaired.txt"
    with open(original_path, "r", encoding="utf-8") as f:
        original = f.read().strip()
    augmented = original + "\n\n" + ("\n\n".join([b.strip() for b in new_blocks])) + "\n"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(augmented)

    ids2, id2text2, atoms2, id2atom2, atom2id2, attacks2, meta2 = build_af(
        tmp_path, relation="explicit", use_llm=False
    )
    t_atom2 = id2atom2.get(target_id, None)
    cred_after = preferred_accepts(atoms2, attacks2, t_atom2) if t_atom2 else False
    k_after, n_after, cov_after = preferred_coverage(atoms2, attacks2, t_atom2) if t_atom2 else (0,0,0.0)

    return {
        "repaired_path": tmp_path,
        "atoms": atoms2,
        "ids": ids2,
        "id2text": id2text2,    # include id→text for AFTER to avoid KeyError
        "id2atom": id2atom2,
        "atom2id": atom2id2,
        "attacks": sorted(list(attacks2)),
        "meta": meta2,
        "preferred_credulous_target": bool(cred_after),
        "preferred_coverage_after": {"k": k_after, "n": n_after, "frac": cov_after},
    }

# -------- Main flow --------
def main():
    ap = argparse.ArgumentParser(description="argsem.py — AF extraction + clingo semantics + reporting (+ repair via --repair)")
    ap.add_argument("path", help="Text file of arguments (blocks separated by blank lines)")

    # Extraction controls
    ap.add_argument("--relation", default="auto", choices=["auto","explicit","none"], help="Use ATTACKS or induce by heuristics; 'auto' uses ATTACKS if present else heuristics.")
    ap.add_argument("--jaccard", type=float, default=0.45, help="Heuristic Jaccard threshold (auto mode).")
    ap.add_argument("--min-overlap", type=int, default=3, help="Heuristic min shared content tokens (auto mode).")
    ap.add_argument("--use-llm", action="store_true", help="Use LLM for edge inference (baseline AF).")
    ap.add_argument("--llm-threshold", type=float, default=0.55, help="Confidence cutoff for LLM edges.")
    ap.add_argument("--llm-mode", default="augment", choices=["augment","override"], help="Augment (union) or override other edges with LLM edges.")

    # Semantics & reporting
    ap.add_argument("--sem", default="all", choices=["grounded","preferred","stable","complete","stage","semi-stable","semistable","all"], help="Which semantics to compute (controls JSON content; Markdown always shows multiple).")
    ap.add_argument("--query", type=str, default=None, help="Acceptance query for an argument (ID or APX atom).")
    ap.add_argument("--mode", type=str, default=None, choices=["credulous","skeptical"], help="Query mode.")
    ap.add_argument("--apx-out", type=str, default=None, help="Write APX (BEFORE AF unless --repair; then AFTER AF).")
    ap.add_argument("--dot", type=str, default=None, help="Export DOT (BEFORE AF unless --repair; then AFTER AF).")
    ap.add_argument("--apx-out-before", type=str, default=None, help="Write APX for BEFORE AF (repair mode only).")
    ap.add_argument("--dot-before", type=str, default=None, help="Write DOT for BEFORE AF (repair mode only).")
    ap.add_argument("--names", default="apx", choices=["apx","ids","both"], help="Name scheme in JSON semantics (APX atoms, original IDs, or both).")
    ap.add_argument("--md", action="store_true", help="Print Markdown report to stdout.")
    ap.add_argument("--md-out", type=str, default=None, help="Write Markdown report to file.")
    ap.add_argument("--json", action="store_true", help="Print JSON to stdout.")
    ap.add_argument("--json-out", type=str, default=None, help="Write JSON to file.")
    ap.add_argument("--target", type=str, default=None, help="Target ID for why-not analysis (and required for --repair).")
    ap.add_argument("--llm-summarize", action="store_true", help="Ask LLM to add a short narrative to Markdown (BEFORE only).")
    ap.add_argument("--max-pref-cards", type=int, default=4, help="Limit number of preferred 'stance cards' in Markdown.")

    # Repair flags
    ap.add_argument("--repair", action="store_true", help="Run the preferred-credulous add-nodes-only repair and produce an integrated BEFORE/AFTER report.")
    ap.add_argument("--k", type=int, default=1, help="(repair) Max number of new defender nodes.")
    ap.add_argument("--fanout", type=int, default=0, help="(repair) Max blockers attacked by one new node; 0 = unlimited (default).")
    ap.add_argument("--new-prefix", type=str, default="R", help="(repair) Prefix for auto-assigned new claim IDs (R1, R2, ...).")
    ap.add_argument("--llm-generate", action="store_true", help="(repair) Use LLM to write defender sentences.")
    ap.add_argument("--force", action="store_true", help="(repair) Proceed even if target already credulously preferred before repair.")
    ap.add_argument("--min-coverage", type=float, default=None, help="(repair) Require target to appear in at least this fraction of preferred extensions before skipping (e.g., 1.0).")

    args = ap.parse_args()

    # 1) Build BEFORE AF
    ids, id2text, atoms, id2atom, atom2id, attacks, meta = build_af(
        args.path, relation=args.relation, jaccard=args.jaccard, min_overlap=args.min_overlap,
        use_llm=args.use_llm, llm_threshold=args.llm_threshold, llm_mode=args.llm_mode
    )

    # If not repairing: run normal reporting and exit
    if not args.repair:
        # Optionally write APX and DOT for BEFORE AF
        if args.apx_out:
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

        # Solve semantics according to --sem
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
            q_atom = id2atom.get(q, q)
            fam = None
            if args.sem == "grounded":
                fam = [Sem] if isinstance(Sem, frozenset) else [af_clingo.grounded(atoms, attacks)]
            elif args.sem == "all":
                fam = Sem["preferred"]
            else:
                fam = Sem if isinstance(Sem, list) else [Sem]
            query_ans = (af_clingo.credulous(fam, q_atom) if args.mode == "credulous"
                         else af_clingo.skeptical(fam, q_atom))

        # Insights
        tgt_id = args.target if (args.target in ids) else (ids[0] if (args.target is None and ids) else None)
        tgt_atom = id2atom.get(tgt_id) if tgt_id else None
        depth = defense_depth(atoms, attacks)
        G_core = sorted(list(af_clingo.grounded(atoms, attacks)))
        rb   = grounded_roadblocks(atoms, attacks, tgt_atom) if tgt_atom else []
        pers, soft = preferred_persistent_soft(atoms, attacks, tgt_atom) if tgt_atom else ([], [])

        # JSON
        def translate(obj):
            if isinstance(obj, frozenset): return translate_set(obj, atom2id)
            if isinstance(obj, list):      return [translate_set(S, atom2id) for S in obj]
            if isinstance(obj, dict):      return {k: translate(v) for (k,v) in obj.items()}
            return obj

        if args.json or args.json_out:
            payload = {
                "input": {"path": args.path, "ids": ids, "id_to_atom": id2atom, "meta": meta},
                "af": {"atoms": atoms, "attacks": sorted(list(attacks))},
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

            if args.query and args.mode:
                payload["query"] = {"arg": args.query, "mode": args.mode, "answer": bool(query_ans)}

            if args.json and not args.json_out:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            if args.json_out:
                with open(args.json_out, "w", encoding="utf-8") as jf:
                    jf.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

        # Markdown
        if args.md or args.md_out or (not args.json and not args.json_out):
            md = markdown_report(args.path, ids, id2text, atoms, id2atom, atom2id, attacks, meta,
                                 target_id=tgt_id, stance_limit=args.max_pref_cards, llm_summarize=args.llm_summarize)
            if args.md:
                print(md, end="")
            if args.md_out:
                with open(args.md_out, "w", encoding="utf-8") as mf:
                    mf.write(md)
        return

    # 2) Repair mode
    if args.target is None:
        raise SystemExit("--repair requires --target <ID>")

    # Baseline stats
    t_atom = id2atom.get(args.target)
    if t_atom is None:
        raise SystemExit(f"Target ID {args.target!r} not found. Known IDs: {ids}")

    cred_before = preferred_accepts(atoms, attacks, t_atom)
    k_in, n_pf, cov_before = preferred_coverage(atoms, attacks, t_atom)

    # Early exit if already satisfied and not forced
    goal_ok = cred_before
    if args.min_coverage is not None:
        goal_ok = goal_ok and (cov_before >= args.min_coverage)
    if goal_ok and not args.force:
        before_md = markdown_report(args.path, ids, id2text, atoms, id2atom, atom2id, attacks, meta,
                                    target_id=args.target, stance_limit=args.max_pref_cards, llm_summarize=args.llm_summarize)
        result = {
            "action": "skipped",
            "reason": "goal already satisfied (use --force or increase --min-coverage)",
            "before": {
                "credulous_preferred": bool(cred_before),
                "preferred_coverage": {"k": k_in, "n": n_pf, "frac": cov_before},
            }
        }
        if args.json or args.json_out:
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            if args.json_out:
                with open(args.json_out, "w", encoding="utf-8") as jf:
                    jf.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        if args.md or args.md_out:
            md = "# Repair skipped\n\n" + \
                 f"- Target: {args.target}\n" + \
                 f"- Credulous preferred before: **{'YES' if cred_before else 'NO'}**\n" + \
                 f"- Preferred coverage before: **{k_in}/{n_pf} ≈ {cov_before:.2f}**\n" + \
                 f"- Reason: goal already satisfied. Use `--force` or `--min-coverage` to proceed.\n\n" + \
                 "## Baseline report\n\n" + before_md
            if args.md:
                print(md, end="")
            if args.md_out:
                with open(args.md_out, "w", encoding="utf-8") as mf:
                    mf.write(md)
        return

    # Compute direct blockers & rank by persistence
    direct_blockers = attackers_of(atoms, attacks, t_atom)
    freqs = preferred_attacker_frequencies(atoms, attacks, t_atom)
    direct_blockers_sorted = sorted(direct_blockers, key=lambda b: (-freqs.get(b,0), b))
    blocker_ids = [atom2id[b] for b in direct_blockers_sorted]

    # Group into <= k defender nodes
    kmax = max(1, args.k)
    groups_ids = group_blockers(blocker_ids, k=kmax, fanout=args.fanout)
    new_ids = next_new_ids(ids, len(groups_ids), prefix=args.new_prefix)

    # Generate blocks (text)
    new_blocks = build_new_blocks(new_ids, groups_ids, id2text, use_llm_text=args.llm_generate)

    # Verify (explicit mode for combined file)
    after = verify_after(args.path, new_blocks, args.target)

    # Write BEFORE APX/DOT if requested
    if args.apx_out_before:
        idx_map = {ids[i]: i for i in range(len(ids))}
        idx_edges = set()
        for (u,v) in attacks:
            uid, vid = atom2id[u], atom2id[v]
            if uid in idx_map and vid in idx_map:
                idx_edges.add((idx_map[uid], idx_map[vid]))
        with open(args.apx_out_before, "w", encoding="utf-8") as f:
            f.write(nl2apx.emit_apx(ids, id2text, idx_edges, provenance=meta))
    if args.dot_before:
        af_clingo.export_dot(atoms, attacks, args.dot_before)

    # Write AFTER APX/DOT if requested (or if apx-out/dot are provided, they refer to AFTER in repair mode)
    if args.apx_out or args.apx_out_before:
        apx_after_path = args.apx_out or (args.apx_out_before + ".after.apx")
        ids2 = after["ids"]; id2atom2 = after["id2atom"]; atom2id2 = after["atom2id"]; meta2 = after["meta"]; id2text2 = after["id2text"]
        idx_map2 = {ids2[i]: i for i in range(len(ids2))}
        idx_edges2 = set()
        for (u,v) in after["attacks"]:
            uid, vid = atom2id2[u], atom2id2[v]
            if uid in idx_map2 and vid in idx_map2:
                idx_edges2.add((idx_map2[uid], idx_map2[vid]))
        with open(apx_after_path, "w", encoding="utf-8") as f:
            f.write(nl2apx.emit_apx(ids2, id2text2, idx_edges2, provenance=meta2))
    if args.dot or args.dot_before:
        dot_after_path = args.dot or (args.dot_before + ".after.dot")
        af_clingo.export_dot(after["atoms"], set(after["attacks"]), dot_after_path)

    # JSON (integrated)
    if args.json or args.json_out:
        out = {
            "target": args.target,
            "before": {
                "credulous_preferred": bool(cred_before),
                "preferred_coverage": {"k": k_in, "n": n_pf, "frac": cov_before},
                "blockers_ids": blocker_ids,
                "groups": [{"new_id": nid, "attacks_ids": gids} for nid, gids in zip(new_ids, groups_ids)],
            },
            "new_claims": new_blocks,
            "after": after
        }
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as jf:
                jf.write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    # Markdown (integrated BEFORE + NEW CLAIMS + AFTER)
    if args.md or args.md_out or (not args.json and not args.json_out):
        before_md = markdown_report(args.path, ids, id2text, atoms, id2atom, atom2id, attacks, meta,
                                    target_id=args.target, stance_limit=args.max_pref_cards, llm_summarize=args.llm_summarize)
        # AFTER report from AFTER AF (use AFTER id2text to include new claims; fixes KeyError)
        ids2 = after["ids"]; id2atom2 = after["id2atom"]; atom2id2 = after["atom2id"]
        atoms2 = after["atoms"]; att2 = set(after["attacks"]); meta2 = after["meta"]; id2text2 = after["id2text"]
        after_md = markdown_report(after["repaired_path"], ids2, id2text2, atoms2, id2atom2, atom2id2, att2, meta2,
                                   target_id=args.target, stance_limit=args.max_pref_cards, llm_summarize=False)
        lines = []
        lines.append(f"# Integrated Repair Report — target {args.target}\n")
        lines.append(f"- Credulous preferred before? **{'YES' if cred_before else 'NO'}**")
        lines.append(f"- Preferred coverage before: **{k_in}/{n_pf} ≈ {cov_before:.2f}**")
        lines.append(f"- Direct blockers (ranked): {', '.join(blocker_ids) if blocker_ids else '(none)'}")
        lines.append(f"- Groups → new nodes: " + "; ".join(f"{nid}→({', '.join(gids)})" for nid, gids in zip(new_ids, groups_ids)))
        lines.append("\n## New claims")
        for nb in new_blocks:
            lines.append(nb.strip()); lines.append("")
        pc = after["preferred_coverage_after"]
        lines.append("## Verification")
        lines.append(f"- Preferred credulous after? **{'YES' if after['preferred_credulous_target'] else 'NO'}**")
        lines.append(f"- Preferred coverage after: **{pc['k']}/{pc['n']} ≈ {pc['frac']:.2f}**")
        lines.append("\n---\n\n## BEFORE (baseline semantics)\n")
        lines.append(before_md)
        lines.append("\n---\n\n## AFTER (semantics on repaired file)\n")
        lines.append(after_md)
        md = "\n".join(lines)
        if args.md:
            print(md, end="")
        if args.md_out:
            with open(args.md_out, "w", encoding="utf-8") as mf:
                mf.write(md)

if __name__ == "__main__":
    main()
