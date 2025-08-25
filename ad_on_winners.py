#!/usr/bin/env python3
"""
ad_on_winners.py — Analyze *winning sets* (extensions) with ad.py

Purpose
-------
- Build an Abstract Argumentation Framework (AF) from arguments.txt via nl2apx.py.
- Compute *winning sets* (extensions) under a chosen semantics (preferred by default).
- For each extension (stance), *concatenate the member blocks* and ask ad.py to:
  - extract claims & inferences,
  - flag issues (missing link, unsupported premise, circularity, false dichotomy, slippery slope),
  - (optionally) generate a concise repair and a cleaned stance argument.

Outputs
-------
- Markdown report with one section per stance: members, **claims table**, **inferences list**,
  **detailed issues with claim texts**, and optional repair excerpt.
- JSON with structured results (stances, ad.py analyses).
- Optional: APX + DOT for the AF (for reference).

Assumptions
-----------
- You have nl2apx.py and af_clingo.py importable.
- You have ad.py; it will use your configured LLM env vars if needed.
"""

from __future__ import annotations
import argparse
import json
import sys
from typing import Dict, List, Set, Tuple, Optional

# Local deps
try:
    import nl2apx as NL
    import af_clingo
except Exception as e:
    print("ERROR: ad_on_winners.py requires nl2apx.py and af_clingo.py importable.", file=sys.stderr)
    raise

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


def build_af(text_path: str,
             relation: str = "auto",
             jaccard: float = 0.45,
             min_overlap: int = 3,
             use_llm: bool = False,
             llm_threshold: float = 0.55,
             llm_mode: str = "augment"):
    """Parse blocks and build an AF (atoms, attacks) and mappings."""
    blocks = NL.parse_blocks(text_path)
    ids, id2text, idx_edges, meta = NL.build_edges(
        blocks,
        relation_mode=relation,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    # Map IDs to atoms
    id2atom: Dict[str, str] = {}
    used = set()
    for _id in ids:
        a = sanitize_atom(_id)
        k = a; j = 1
        while k in used:
            j += 1; k = f"{a}_{j}"
        id2atom[_id] = k; used.add(k)
    atom2id = {v:k for k,v in id2atom.items()}

    # Attacks in atom space
    ids_list = list(ids)
    attacks = set()
    for (i, j) in idx_edges:
        u = id2atom[ids_list[i]]
        v = id2atom[ids_list[j]]
        attacks.add((u, v))

    atoms = [id2atom[_id] for _id in ids]
    return ids, id2text, atoms, attacks, id2atom, atom2id, meta


def winners(atoms: List[str], attacks: Set[Tuple[str,str]], mode: str):
    """Return list[set[atom]] for the chosen semantics mode."""
    mode = (mode or "preferred").lower()
    if mode == "grounded":
        return [set(af_clingo.grounded(atoms, attacks))]
    if mode == "preferred":
        return [set(S) for S in af_clingo.preferred(atoms, attacks)]
    if mode == "stable":
        return [set(S) for S in af_clingo.stable(atoms, attacks)]
    if mode == "complete":
        return [set(S) for S in af_clingo.complete(atoms, attacks)]
    if mode == "stage":
        return [set(S) for S in af_clingo.stage(atoms, attacks)]
    if mode in ("semi-stable","semistable","semi_stable"):
        return [set(S) for S in af_clingo.semi_stable(atoms, attacks)]
    raise ValueError(f"Unknown winners mode: {mode}")


def stance_text(members_ids: List[str], id2text: Dict[str,str]) -> str:
    """Concatenate the member blocks with blank lines for ad.py to parse."""
    parts = []
    for mid in members_ids:
        t = (id2text.get(mid) or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts).strip()


def analyze_stance(text: str, want_repair: bool = False):
    """Run ad.py on the stance text; return structure, issues, and optional repair."""
    if not HAVE_AD:
        return {"error": "ad.py not available"}
    parser = AD.ArgumentParser()
    argument = parser.parse_argument(text)
    issues = AD.ASPDebugger(debug=False).analyze(argument)

    out = {
        "claims": [{"id": c.id, "type": c.type, "content": c.content} for c in argument.claims],
        "inferences": [{"from": i.from_claims, "to": i.to_claim, "rule_type": i.rule_type} for i in argument.inferences],
        "goal_claim": argument.goal_claim,
        "issues": [{"type": it.type, "desc": it.description, "claims": it.involved_claims} for it in issues],
        "issue_counts": _count_issues(issues),
    }
    if want_repair and issues:
        repairer = AD.RepairGenerator(debug=False)
        rep_text, clean = repairer.generate_repair(text, argument, issues)
        out["repair"] = {"commentary": rep_text, "clean_argument": clean}
    return out


def _count_issues(issues) -> Dict[str,int]:
    d = {}
    for it in issues or []:
        d[it.type] = d.get(it.type, 0) + 1
    return d


def _md_escape(s: str) -> str:
    return (s or "").replace("|","\\|")


def _preview(s: str, n: int = 140) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _claims_table(ad: dict):
    claims = ad.get("claims") or []
    if not claims:
        return ["_no claims parsed_"]
    lines = []
    lines.append("| Claim | Type | Text |")
    lines.append("|:-----:|:-----|:-----|")
    for c in claims:
        cid = c.get("id","?"); ctype = c.get("type","")
        txt = _md_escape(_preview(c.get("content","")))
        lines.append(f"| `{cid}` | {ctype} | {txt} |")
    return lines


def _inferences_list(ad: dict):
    infs = ad.get("inferences") or []
    if not infs:
        return ["_no inferences_"]
    cmap = {c.get("id"): c.get("content","") for c in (ad.get("claims") or [])}
    lines = []
    for i in infs:
        frm_ids = i.get("from") or i.get("from_claims", [])
        frm = ", ".join(frm_ids)
        to  = i.get("to") or i.get("to_claim")
        rt  = i.get("rule_type","")
        to_txt = _preview(cmap.get(to,""))
        lines.append(f"- [{frm}] → {to} ({rt}) — “{_md_escape(to_txt)}”")
    return lines


def _issues_detailed(ad: dict):
    issues = ad.get("issues") or []
    if not issues:
        return ["_no issues detected_"]
    cmap = {c.get("id"): c.get("content","") for c in (ad.get("claims") or [])}
    # group by type
    from collections import defaultdict
    g = defaultdict(list)
    for it in issues:
        g[it.get("type","other")].append(it)
    lines = []
    for t in sorted(g.keys()):
        lines.append(f"**{t}**")
        for it in g[t]:
            cl = it.get("claims") or []
            if cl:
                annot = "; ".join(f"`{cid}` — “{_md_escape(_preview(cmap.get(cid,'')))}”" for cid in cl)
            else:
                annot = "(no specific claims)"
            desc = it.get("desc") or it.get("description","")
            lines.append(f"- {desc} {annot}")
    return lines


def markdown_report(title: str,
                    sem_mode: str,
                    ids: List[str],
                    id2text: Dict[str,str],
                    id2atom: Dict[str,str],
                    ex_meta: Dict,
                    stances: List[Dict],
                    limit_claim_preview: int = 110) -> str:
    """Pretty report across all stances with detailed ad.py info."""
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    # Extraction summary
    exp = len(ex_meta.get("explicit_edges") or [])
    heu = len(ex_meta.get("heuristic_edges") or [])
    llm = len(ex_meta.get("llm_edges") or [])
    lines.append("## AF Extraction")
    lines.append(f"- explicit attacks: **{exp}**, heuristic: **{heu}**, llm: **{llm}**")
    lines.append(f"- winners semantics: **{sem_mode}**")
    lines.append("")

    # Stances
    if not stances:
        lines.append("_No winning sets found under this semantics._")
        return "\n".join(lines)

    for i, S in enumerate(stances, 1):
        mids = S["members_ids"]
        lines.append(f"## Stance S{i} — members ({len(mids)}): {{ " + ", ".join(mids) + " }}")
        # Preview
        for mid in mids:
            snippet = (id2text.get(mid,"").strip().replace("\n"," "))
            if len(snippet) > limit_claim_preview: snippet = snippet[:limit_claim_preview] + "…"
            atom = id2atom.get(mid, "?")
            lines.append(f"- **{mid}** (`{atom}`): {snippet}")
        lines.append("")

        # ad.py summary
        if "ad" in S and isinstance(S["ad"], dict) and not S["ad"].get("error"):
            ad = S["ad"]
            nC = len(ad.get("claims",[])); nI = len(ad.get("inferences",[]))
            lines.append(f"**ad.py parse:** claims={nC}, inferences={nI}, goal={ad.get('goal_claim') or '—'}")
            ic = ad.get("issue_counts") or {}
            if ic:
                bag = ", ".join(f"{k}:{v}" for k,v in sorted(ic.items()))
                lines.append(f"**issues (counts):** {bag}")
            else:
                lines.append("**issues:** none detected")

            # Claims table
            lines.append("")
            lines.append("**Claims parsed**")
            lines.extend(_claims_table(ad))

            # Inferences
            lines.append("")
            lines.append("**Inferences**")
            lines.extend(_inferences_list(ad))

            # Issues with claim texts
            lines.append("")
            lines.append("**Issues (detailed)**")
            lines.extend(_issues_detailed(ad))

            # Repair preview
            rep = ad.get("repair")
            if rep and rep.get("commentary"):
                lines.append("")
                lines.append("**Repair commentary (excerpt)**")
                comm = rep["commentary"].strip()
                if len(comm) > 600: comm = comm[:600] + "…"
                lines.append(comm)
            lines.append("")
        else:
            err = S.get("ad",{}).get("error","(ad.py unavailable)")
            lines.append(f"_ad.py analysis skipped: {err}_")
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Analyze winning sets (extensions) with ad.py")
    ap.add_argument("file", help="arguments.txt (blocks separated by blank lines)")

    # AF extraction
    ap.add_argument("--relation", choices=["auto","explicit","none"], default="auto")
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--llm-mode", choices=["augment","override"], default="augment")
    ap.add_argument("--llm-threshold", type=float, default=0.55)
    ap.add_argument("--jaccard", type=float, default=0.45)
    ap.add_argument("--min-overlap", type=int, default=3)

    # Winners semantics
    ap.add_argument("--winners", choices=["preferred","stable","grounded","complete","stage","semi-stable"],
                    default="preferred")
    ap.add_argument("--limit-stances", type=int, default=5, help="max number of stances to analyze")

    # ad.py options
    ap.add_argument("--repair-stance", action="store_true", help="attempt a repair for each stance with issues")

    # Outputs
    ap.add_argument("--md", action="store_true", help="print Markdown to stdout")
    ap.add_argument("--md-out", default=None, help="write Markdown to file")
    ap.add_argument("--json", action="store_true", help="print JSON to stdout")
    ap.add_argument("--json-out", default=None, help="write JSON to file")
    ap.add_argument("--apx-out", default=None, help="write AF as APX")
    ap.add_argument("--dot-out", default=None, help="write AF as DOT")

    args = ap.parse_args()

    ids, id2text, atoms, attacks, id2atom, atom2id, meta = build_af(
        text_path=args.file,
        relation=args.relation,
        jaccard=args.jaccard,
        min_overlap=args.min_overlap,
        use_llm=args.use_llm,
        llm_threshold=args.llm_threshold,
        llm_mode=args.llm_mode,
    )

    # Compute winning sets
    ext = winners(atoms, attacks, mode=args.winners)
    if args.limit_stances and len(ext) > args.limit_stances:
        ext = ext[:args.limit_stances]

    # Analyze each stance with ad.py
    stances = []
    for i, S_atoms in enumerate(ext, 1):
        mids = sorted([atom2id[a] for a in S_atoms])
        text = stance_text(mids, id2text)
        ad_res = analyze_stance(text, want_repair=args.repair_stance) if text else {"error": "empty stance text"}
        stances.append({
            "name": f"S{i}",
            "members_ids": mids,
            "ad": ad_res,
            "text_len": len(text or ""),
        })

    # Markdown
    if args.md or args.md_out:
        md = markdown_report("Winning sets analyzed by ad.py", args.winners, ids, id2text, id2atom, meta, stances)
        if args.md:
            print(md)
        if args.md_out:
            with open(args.md_out, "w", encoding="utf-8") as f:
                f.write(md)

    # JSON (include full ad.py result per stance)
    if args.json or args.json_out:
        payload = {
            "input": {
                "ids": ids,
                "attacks": sorted(list(attacks)),
                "id2atom": id2atom,
                "atom2id": atom2id,
                "extraction_meta": {
                    "explicit_edges": meta.get("explicit_edges") or [],
                    "heuristic_edges": meta.get("heuristic_edges") or [],
                    "llm_edges": meta.get("llm_edges") or [],
                },
            },
            "winners_semantics": args.winners,
            "stances": stances,
        }
        js = json.dumps(payload, indent=2, ensure_ascii=False)
        if args.json:
            print(js)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as f:
                f.write(js)

    # Optional APX/DOT of AF (for reference)
    if args.apx_out:
        lines = []
        for _id, atom in sorted(id2atom.items(), key=lambda kv: kv[1]):
            lines.append(f"arg({atom}).")
        for (u, v) in sorted(attacks):
            lines.append(f"att({u},{v}).")
        with open(args.apx_out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines)+"\n")
    if args.dot_out:
        out = []
        out.append("digraph AF {")
        out.append('  rankdir=LR;')
        for _id, atom in sorted(id2atom.items(), key=lambda kv: kv[1]):
            out.append(f'  "{atom}" [shape=box, label="{_id}\\n({atom})"];')
        for (u, v) in sorted(attacks):
            out.append(f'  "{u}" -> "{v}" [color="#ff6b6b"];')
        out.append("}")
        with open(args.dot_out, "w", encoding="utf-8") as f:
            f.write("\n".join(out)+"\n")


if __name__ == "__main__":
    main()
