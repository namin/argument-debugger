#!/usr/bin/env python3
"""
as_pretty.py — Pretty-print end-to-end:
Natural language blocks (with optional ID/ATTACKS) → AF (via nl2apx) → Semantics (via af_clingo)
and a readable report that connects back to the original text.

Features
- Shows the AF with provenance tags per edge: [exp] explicit, [heu] heuristic, [llm] LLM
- Summarizes grounded/preferred/stable/complete/stage/semi-stable
- For each argument: membership across semantics + defense depth + attackers/attackees
- "Stance cards" for preferred extensions
- "Why-not" for a target: grounded roadblocks + persistent/soft attackers across preferred
- Optional LLM narrative summaries (Gemini), with graceful fallback to deterministic text

Usage
  python as_pretty.py arguments.txt --use-llm
  python as_pretty.py arguments.txt --relation explicit --target A1
  python as_pretty.py examples_llm_messy.txt --use-llm --llm-summarize

Notes
- Requires nl2apx.py and af_clingo.py in the same directory (importable).
- LLM summaries require GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT env (optional).
"""

from __future__ import annotations
import argparse
import os
from typing import Dict, List, Set, Tuple, FrozenSet, Optional
import nl2apx
import af_clingo

# Optional Gemini client (mirrors your ad.py style)
_HAVE_LLM = False
try:
    from google import genai
    from google.genai import types
    _HAVE_LLM = True
except Exception:
    _HAVE_LLM = False

def init_llm_client():
    if not _HAVE_LLM:
        return None
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    try:
        if gemini_api_key:
            return genai.Client(api_key=gemini_api_key)
        elif google_cloud_project:
            return genai.Client(vertexai=True, project=google_cloud_project, location=google_cloud_location)
    except Exception:
        return None
    return None

def shorten(s: str, n: int = 100) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"

def build_af(blocks_path: str,
             relation: str = "auto",
             jaccard: float = 0.45,
             min_overlap: int = 3,
             use_llm: bool = False,
             llm_threshold: float = 0.55,
             llm_mode: str = "augment"):
    blocks = nl2apx.parse_blocks(blocks_path)
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
    atom2id = {v: k for k, v in id2atom.items()}
    # Convert index edges to atom attacks
    attacks = set((atoms[i], atoms[j]) for (i, j) in idx_edges)
    return ids, id_to_text, atoms, id2atom, atom2id, attacks, meta

def status_table(atoms: List[str],
                 attacks: Set[Tuple[str,str]]):
    G = af_clingo.grounded(atoms, attacks)
    P = af_clingo.preferred(atoms, attacks)
    S = af_clingo.stable(atoms, attacks)
    C = af_clingo.complete(atoms, attacks)
    STG = af_clingo.stage(atoms, attacks)
    SST = af_clingo.semi_stable(atoms, attacks)

    # Defense depth (by iterating F)
    def _F(Sset: Set[str]) -> Set[str]:
        atk = {a: set() for a in atoms}
        for (u,v) in attacks:
            if v in atk: atk[v].add(u)
        defended = set()
        for a in atoms:
            ok = True
            for b in atk[a]:
                if not any((c,b) in attacks for c in Sset):
                    ok = False; break
            if ok: defended.add(a)
        return defended

    depth = {a: None for a in atoms}
    S0 = set()
    i = 0
    while True:
        T = _F(S0)
        if T == S0: break
        wave = T - S0
        i += 1
        for a in wave:
            if depth[a] is None:
                depth[a] = i
        S0 = T

    # membership counts
    def in_many(fams: List[FrozenSet[str]], a: str) -> str:
        if not fams: return "0/0"
        k = sum(1 for S in fams if a in S)
        return f"{k}/{len(fams)}"

    table = {}
    for a in atoms:
        table[a] = {
            "grounded": (a in G),
            "preferred": in_many(P, a),
            "stable":   in_many(S, a),
            "complete": in_many(C, a),
            "stage":    in_many(STG, a),
            "semistable": in_many(SST, a),
            "depth": depth[a],
        }
    return table, G, P, S, C, STG, SST

def provenance_for(attacks_idx: Set[Tuple[int,int]], meta: Dict, ids: List[str]):
    """Map (atom_u, atom_v) -> provenance label(s)."""
    prov: Dict[Tuple[int,int], List[str]] = {}
    def add_many(lst, tag):
        for e in lst:
            prov.setdefault(tuple(e), []).append(tag)
    add_many(meta.get("explicit_edges", []), "exp")
    add_many(meta.get("heuristic_edges", []), "heu")
    add_many(meta.get("llm_edges", []), "llm")
    # Build readable map
    return prov

def pretty_report(path: str,
                  ids: List[str],
                  id_to_text: Dict[str,str],
                  atoms: List[str],
                  id2atom: Dict[str,str],
                  atom2id: Dict[str,str],
                  attacks: Set[Tuple[str,str]],
                  meta: Dict,
                  target: Optional[str] = None,
                  use_llm_summaries: bool = False) -> str:

    # Semantics
    table, G, P, S, C, STG, SST = status_table(atoms, attacks)

    # Provenance
    # We want per-edge provenance tags: build index map first
    idx_map = {ids[i]: i for i in range(len(ids))}
    prov_idx = provenance_for(set(), meta, ids)  # uses meta only
    # Edge lines
    edge_lines = []
    for (u,v) in sorted(attacks):
        uid, vid = atom2id[u], atom2id[v]
        ui, vi = idx_map.get(uid), idx_map.get(vid)
        tags = []
        if ui is not None and vi is not None:
            tags = prov_idx.get((ui,vi), [])
        label = "[" + ",".join(tags) + "]" if tags else ""
        edge_lines.append(f"- {uid} ({u}) → {vid} ({v}) {label}")

    # Choose target
    tgt_id = target if target in ids else (ids[0] if ids else None)
    tgt_atom = id2atom.get(tgt_id) if tgt_id else None

    # Why-not for target (grounded roadblocks & preferred persistent/soft)
    roadblocks = []
    persistent = []
    soft = []
    if tgt_atom:
        roadblocks = grounded_roadblocks(atoms, attacks, tgt_atom)
        # Preferred persistent/soft
        if P:
            inter = set(atoms)
            union = set()
            for Sx in P:
                inter &= set(Sx)
                union |= set(Sx)
            atk_of = {a: set() for a in atoms}
            for (x,y) in attacks:
                atk_of[y].add(x)
            att = atk_of.get(tgt_atom, set())
            persistent = sorted(list(inter & att))
            soft = sorted(list((union - inter) & att))

    # Stance cards (preferred)
    stance_cards = []
    for i, Sx in enumerate(P, 1):
        ids_in = [atom2id[a] for a in sorted(Sx)]
        preview = "; ".join(shorten(id_to_text[id], 60) for id in ids_in[:3])
        stance_cards.append(f"**S{i}** = {{{', '.join(ids_in)}}}\n  - preview: {preview}")

    # Summaries (optional LLM)
    llm_text = ""
    if use_llm_summaries and _HAVE_LLM:
        client = init_llm_client()
        if client is not None:
            try:
                listing = "\n".join([f"{ids[i]}: {shorten(id_to_text[ids[i]], 140)}" for i in range(len(ids))])
                G_ids = ", ".join(sorted(atom2id[a] for a in G))
                P_ids = "; ".join("{" + ", ".join(sorted(atom2id[a] for a in Sx)) + "}" for Sx in P[:4])
                prompt = f"""
You are summarizing a Dung-style argumentation result for a human reader.
Arguments (ID: text):
{listing}

Grounded core: {G_ids if G_ids else "(empty)"}
Preferred samples: {P_ids if P_ids else "(none)"}
Target: {tgt_id or "(none)"}
Grounded roadblocks for target: {", ".join(roadblocks) if roadblocks else "(none)"}

Write at most 6 sentences: 1-2 about the grounded core (what is safely supported),
2-3 about the stances (how positions split), and 1 about what blocks the target (if any).
Use plain language and avoid jargon.
"""
                cfg = types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_budget=0))
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
                llm_text = resp.text.strip()
            except Exception as e:
                llm_text = f"(LLM summary unavailable: {e})"

    # Build final markdown
    lines = []
    lines.append(f"# AF Report — {os.path.basename(path)}")
    lines.append("")
    lines.append("## Arguments (original IDs → APX atoms)")
    for i, id_ in enumerate(ids, 1):
        a = id2atom[id_]
        lines.append(f"- **{id_}** ({a}): {shorten(id_to_text[id_], 140)}")
    lines.append("")
    lines.append("## Attacks")
    lines.extend(edge_lines if edge_lines else ["(none)"])
    lines.append("")
    lines.append("## Semantics (membership & depth)")
    header = "| ID | Atom | Grounded | Pref | Stable | Complete | Stage | SemiSt | Depth |"
    sep    = "|---:|:-----|:--------:|:----:|:------:|:--------:|:-----:|:------:|:-----:|"
    lines.append(header); lines.append(sep)
    for id_ in ids:
        a = id2atom[id_]
        row = table[a]
        lines.append(f"| {id_} | `{a}` | {'✓' if row['grounded'] else ''} | {row['preferred']} | {row['stable']} | {row['complete']} | {row['stage']} | {row['semistable']} | {row['depth'] if row['depth'] is not None else ''} |")

    if P:
        lines.append("")
        lines.append("## Preferred “stance cards”")
        lines.extend(stance_cards)

    if tgt_id:
        lines.append("")
        lines.append(f"## Why {tgt_id} may be out (grounded)")
        lines.append(f"- Grounded roadblocks (undefeated attackers): {', '.join(roadblocks) if roadblocks else '(none)'}")
        if persistent or soft:
            lines.append(f"- Across preferred: persistent attackers: {', '.join(persistent) if persistent else '(none)'}; soft attackers: {', '.join(soft) if soft else '(none)'}")

    if llm_text:
        lines.append("")
        lines.append("## Narrative (LLM)")
        lines.append(llm_text)

    return "\n".join(lines)

def grounded_roadblocks(atoms: List[str], attacks: Set[Tuple[str,str]], target: str) -> List[str]:
    G = set(af_clingo.grounded(atoms, attacks))
    if target in G: return []
    atk = {a: set() for a in atoms}
    for (u,v) in attacks:
        atk[v].add(u)
    return sorted([b for b in atk.get(target, set()) if not any((c,b) in attacks for c in G)])

def main():
    ap = argparse.ArgumentParser(description="Pretty-print AF semantics mapped to original text.")
    ap.add_argument("path", help="Text file of arguments (blocks separated by blank lines)")
    # Extraction options
    ap.add_argument("--relation", default="auto", choices=["auto","explicit","none"])
    ap.add_argument("--jaccard", type=float, default=0.45)
    ap.add_argument("--min-overlap", type=int, default=3)
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--llm-threshold", type=float, default=0.55)
    ap.add_argument("--llm-mode", default="augment", choices=["augment","override"])
    # Pretty-print options
    ap.add_argument("--target", type=str, default=None, help="Target ID (e.g., A2) for why-not analysis")
    ap.add_argument("--llm-summarize", action="store_true", help="Ask an LLM to write a short narrative summary")
    ap.add_argument("--out", type=str, default=None, help="Write markdown report to this path (default: stdout)")
    args = ap.parse_args()

    ids, id2text, atoms, id2atom, atom2id, attacks, meta = build_af(
        args.path, relation=args.relation, jaccard=args.jaccard, min_overlap=args.min_overlap,
        use_llm=args.use_llm, llm_threshold=args.llm_threshold, llm_mode=args.llm_mode
    )
    report = pretty_report(args.path, ids, id2text, atoms, id2atom, atom2id, attacks, meta,
                           target=args.target, use_llm_summaries=args.llm_summarize and _HAVE_LLM)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    else:
        print(report)

if __name__ == "__main__":
    main()
