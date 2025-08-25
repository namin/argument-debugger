#!/usr/bin/env python3
"""
argsem_repair.py — Semantics-guided repairs (preferred, credulous, add-nodes-only)

Goal
-----
Given a text file of argument blocks, plan and optionally generate *new claims*
that attack the current blockers of a target argument T so that T becomes
**credulously accepted under preferred semantics** — *adding nodes only*.
No existing edges are changed.

Approach
---------
1) Build the AF from the file using nl2apx (explicit/heuristic/LLM per flags).
2) Compute direct attackers of T and rank them (persistent vs soft across preferred).
3) Group blockers into ≤ k new defender nodes; each new node attacks one or more blockers.
4) Generate natural-language text for each new node (optional, via Gemini).
5) Emit a `new_claims.txt` with:
      ID: R1
      ATTACKS: A2, A3
      <1–2 sentence defender text>
6) Verify by recomputing semantics on the **original + new** blocks with
   `--relation explicit` (so only the stated new edges are added) and check if
   T is now credulously accepted under preferred.

Why this works
---------------
Preferred requires admissibility. By adding new nodes that attack *all direct
attackers of T*, and by ensuring no one attacks these new nodes (no incoming
edges are added in explicit mode), the set {T} ∪ {new nodes} is admissible and
extends to a preferred extension — hence T becomes *credulously accepted*.

Usage
------
# Plan + generate text + verify, allow a single new node that covers all blockers
python argsem_repair.py arguments.txt --target A1 --k 1 --use-llm-extract --llm-generate

# Plan with up to 3 new nodes, one blocker per node (fanout=1), no LLM text (templates)
python argsem_repair.py arguments.txt --target A1 --k 3 --fanout 1 --write-new new_claims.txt

# Produce JSON plan only (no files written)
python argsem_repair.py arguments.txt --target A1 --k 2 --json-out plan.json --dry-run

# Verify only (when you already have a new_claims.txt)
python argsem_repair.py arguments.txt --target A1 --verify-only --new new_claims.txt

Outputs
--------
- new_claims.txt (unless --dry-run or --verify-only)
- repaired.txt (original + new, unless --no-apply)
- repair_report.md (optional --md-out), plus JSON (--json-out)

Requires
---------
- nl2apx.py and af_clingo.py importable (same folder recommended)
- clingo python package
- (optional) google.genai for --llm-generate
"""
from __future__ import annotations

import argparse
import os
import json
from typing import Dict, List, Set, Tuple, FrozenSet, Optional

import nl2apx
import af_clingo

# ---- Optional Gemini client (same pattern as ad.py) ----
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
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    google_cloud_project = os.getenv('GOOGLE_CLOUD_PROJECT')
    google_cloud_location = os.getenv('GOOGLE_CLOUD_LOCATION', "us-central1")
    try:
        if gemini_api_key:
            return genai.Client(api_key=gemini_api_key)
        elif google_cloud_project:
            return genai.Client(vertexai=True, project=google_cloud_project, location=google_cloud_location)
    except Exception:
        return None
    return None

# ---- AF helpers ----

def build_af_from_text(
    path: str,
    relation: str = "auto",
    jaccard: float = 0.45,
    min_overlap: int = 3,
    use_llm_extract: bool = False,
    llm_threshold: float = 0.55,
    llm_mode: str = "augment",
):
    blocks = nl2apx.parse_blocks(path)
    ids, id_to_text, idx_edges, meta = nl2apx.build_edges(
        blocks,
        relation_mode=relation,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm_extract,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    atoms = nl2apx.make_unique([nl2apx.sanitize_atom(i) for i in ids])
    id2atom = {ids[i]: atoms[i] for i in range(len(ids))}
    atom2id = {v:k for k,v in id2atom.items()}
    attacks = set((atoms[i], atoms[j]) for (i,j) in idx_edges)
    return ids, id_to_text, atoms, id2atom, atom2id, attacks, meta

def attackers_of(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> List[str]:
    return sorted({u for (u,v) in attacks if v == target_atom})

def preferred_accepts(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> bool:
    prefs = af_clingo.preferred(atoms, attacks)
    return any(target_atom in S for S in prefs)

def preferred_attacker_frequencies(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> Dict[str, int]:
    """How many preferred extensions contain each attacker. Useful to rank 'persistent' vs 'soft'."""
    prefs = af_clingo.preferred(atoms, attacks)
    counts = {a: 0 for a in atoms}
    for S in prefs:
        for a in S:
            counts[a] += 1
    freqs = {}
    for b in attackers_of(atoms, attacks, target_atom):
        freqs[b] = counts.get(b, 0)
    return freqs

# ---- Planning ----

def group_blockers(blockers: List[str], k: int, fanout: int) -> List[List[str]]:
    """
    Partition blockers into <= k groups; each group will be handled by one new defender node.
    - fanout=1  -> one blocker per new node (up to k blockers covered)
    - fanout>1  -> round-robin packing (<= fanout per node)
    - fanout<=0 -> unlimited (try to fit all blockers into the first node if k>=1)
    """
    if not blockers or k <= 0:
        return []
    if fanout <= 0:
        # unlimited: one node can cover all blockers; respect k by making 1 group
        return [blockers[:]] if k >= 1 else []
    if fanout == 1:
        return [[b] for b in blockers[:k]]
    # bounded fanout: distribute in round-robin across up to k groups
    groups = [[] for _ in range(min(k, max(1, (len(blockers)+fanout-1)//fanout)))]
    i = 0
    for b in blockers:
        groups[i % len(groups)].append(b)
        i += 1
    return groups

def next_new_ids(existing_ids: List[str], n: int, prefix: str = "R") -> List[str]:
    base = 1
    used = set(existing_ids)
    out = []
    while len(out) < n:
        cand = f"{prefix}{base}"
        if cand not in used:
            out.append(cand)
            used.add(cand)
        base += 1
    return out

# ---- Generation ----

def text_for_group_llm(client, group_ids: List[str], id_to_text: Dict[str,str]) -> str:
    listing = "\n".join([f"- {gid}: {id_to_text.get(gid,'').strip()}" for gid in group_ids])
    prompt = f"""
You are drafting a concise defender claim that undermines ALL of the following claims:

{listing}

Write 1–2 sentences that directly target their shared flaw (overgeneralization, missing assumptions, counterevidence, limiting conditions, etc.).
The text must be assertive and specific, without hedging or rhetorical flourishes.
Do NOT restate the original claims. Output only the new defender text.
"""
    cfg = types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_budget=0))
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
    return (resp.text or "").strip()

def text_for_group_template(group_ids: List[str], id_to_text: Dict[str,str]) -> str:
    # Deterministic fallback template (no LLM). Short, generic, yet serviceable.
    if len(group_ids) == 1:
        return "This claim relies on a contested assumption and overlooks countervailing evidence that limits its conclusion in this context."
    else:
        return "These claims share a contested assumption and ignore limiting conditions; taken together, they overstate their conclusion in this context."

def build_new_blocks(new_ids: List[str], groups_ids: List[List[str]], id_to_text: Dict[str,str],
                     llm_generate: bool = False) -> List[str]:
    client = init_llm_client() if llm_generate else None
    blocks = []
    for nid, gids in zip(new_ids, groups_ids):
        attacks_line = "ATTACKS: " + ", ".join(gids)
        if llm_generate and client is not None:
            body = text_for_group_llm(client, gids, id_to_text)
            if not body.strip():
                body = text_for_group_template(gids, id_to_text)
        else:
            body = text_for_group_template(gids, id_to_text)
        block = f"ID: {nid}\n{attacks_line}\n{body.strip()}\n"
        blocks.append(block)
    return blocks

# ---- Verification ----

def verify_after(original_path: str, new_blocks: List[str], target_id: str) -> Dict:
    tmp_path = original_path + ".repaired.txt"
    with open(original_path, "r", encoding="utf-8") as f:
        original = f.read().strip()
    augmented = original + "\n\n" + ("\n\n".join([b.strip() for b in new_blocks])) + "\n"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(augmented)

    # Recompute with EXPLICIT edges to avoid spurious inferences into the new nodes
    ids2, id2text2, atoms2, id2atom2, atom2id2, attacks2, meta2 = build_af_from_text(
        tmp_path, relation="explicit", use_llm_extract=False
    )
    t_atom2 = id2atom2.get(target_id, None)
    cred_after = preferred_accepts(atoms2, attacks2, t_atom2) if t_atom2 else False

    return {
        "repaired_path": tmp_path,
        "ids": ids2,
        "id2atom": id2atom2,
        "attacks": sorted(list(attacks2)),
        "preferred_credulous_target": bool(cred_after),
    }

# ---- CLI ----

def main():
    ap = argparse.ArgumentParser(description="Plan + generate add-nodes-only repairs to make target credulously preferred.")
    ap.add_argument("path", help="Text file of arguments (blocks separated by blank lines).")
    ap.add_argument("--target", required=True, help="Target ID (e.g., A1) to make credulously accepted under preferred.")
    ap.add_argument("--k", type=int, default=1, help="Max number of new defender nodes.")
    ap.add_argument("--fanout", type=int, default=0, help="Max blockers attacked by one new node; 0 = unlimited (default).")
    # Extraction settings for baseline analysis
    ap.add_argument("--relation", default="auto", choices=["auto","explicit","none"], help="Use ATTACKS (explicit) or heuristics/LLM.")
    ap.add_argument("--jaccard", type=float, default=0.45)
    ap.add_argument("--min-overlap", type=int, default=3)
    ap.add_argument("--use-llm-extract", action="store_true", help="Use LLM for baseline edge inference.")
    ap.add_argument("--llm-threshold", type=float, default=0.55)
    ap.add_argument("--llm-mode", default="augment", choices=["augment","override"])
    # Generation
    ap.add_argument("--llm-generate", action="store_true", help="Use LLM to write defender sentences.")
    ap.add_argument("--write-new", type=str, default="new_claims.txt", help="Write new blocks to this path.")
    # Verify / outputs
    ap.add_argument("--verify-only", action="store_true", help="Skip planning/generation; just verify with --new file.")
    ap.add_argument("--new", type=str, default=None, help="Path to a prewritten new_claims.txt for --verify-only.")
    ap.add_argument("--no-apply", action="store_true", help="Do not write repaired.txt; only emit new_claims.txt and JSON report.")
    ap.add_argument("--json-out", type=str, default=None, help="Write JSON plan/report to this path.")
    ap.add_argument("--md-out", type=str, default=None, help="Write a Markdown summary report to this path.")
    ap.add_argument("--dry-run", action="store_true", help="Do not write files; just print plan/JSON.")
    args = ap.parse_args()

    # 1) Baseline AF
    ids, id2text, atoms, id2atom, atom2id, attacks, meta = build_af_from_text(
        args.path,
        relation=args.relation,
        jaccard=args.jaccard,
        min_overlap=args.min_overlap,
        use_llm_extract=args.use_llm_extract,
        llm_threshold=args.llm_threshold,
        llm_mode=args.llm_mode,
    )

    if args.target not in ids:
        raise SystemExit(f"Target ID {args.target!r} not found. Known IDs: {ids}")

    t_atom = id2atom[args.target]
    cred_before = preferred_accepts(atoms, attacks, t_atom)

    plan = {
        "path": args.path,
        "target": {"id": args.target, "atom": t_atom},
        "credulous_preferred_before": bool(cred_before),
    }

    if args.verify_only:
        if not args.new or not os.path.exists(args.new):
            raise SystemExit("--verify-only requires --new pointing to new_claims.txt")
        with open(args.new, "r", encoding="utf-8") as f:
            new_txt = f.read().strip()
        new_blocks = [b.strip() for b in new_txt.split("\n\n") if b.strip()]
        after = verify_after(args.path, new_blocks, args.target)
        plan["verify_only"] = True
        plan["after"] = after
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as jf:
                jf.write(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
        if args.md_out:
            ok = "YES" if after["preferred_credulous_target"] else "NO"
            with open(args.md_out, "w", encoding="utf-8") as mf:
                mf.write(f"# Repair Verification\n\nTarget: {args.target}\n\nPreferred credulous after? **{ok}**\n")
        if not (args.json_out or args.md_out):
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        return

    # 2) Compute blockers & rank
    direct_blockers = attackers_of(atoms, attacks, t_atom)
    freqs = preferred_attacker_frequencies(atoms, attacks, t_atom)
    # sort blockers: most 'persistent' (higher count) first
    direct_blockers_sorted = sorted(direct_blockers, key=lambda b: (-freqs.get(b,0), b))

    # Map blockers to original IDs (for ATTACKS lines)
    blocker_ids = [atom2id[b] for b in direct_blockers_sorted]

    # 3) Group into <= k defender nodes
    k = max(1, args.k)
    fanout = args.fanout
    groups_ids = group_blockers(blocker_ids, k=k, fanout=fanout)
    new_ids = next_new_ids(ids, len(groups_ids), prefix="R")

    plan.update({
        "blockers": {"atoms": direct_blockers_sorted, "ids": blocker_ids, "freqs": freqs},
        "groups": [{"new_id": nid, "attacks_ids": gids} for nid, gids in zip(new_ids, groups_ids)],
        "llm_generate": bool(args.llm_generate),
        "fanout": fanout,
        "k": k,
    })

    # 4) Generate blocks (text)
    new_blocks = build_new_blocks(new_ids, groups_ids, id2text, llm_generate=args.llm_generate)
    plan["new_blocks"] = [{"id": nid, "text": nb.split("\n",2)[2].strip(), "attacks_ids": gids}
                          for nid, gids, nb in zip(new_ids, groups_ids, new_blocks)]

    # 5) Emit files (unless dry-run)
    if not args.dry_run:
        if args.write_new:
            with open(args.write_new, "w", encoding="utf-8") as f:
                f.write(("\n\n".join(new_blocks)).strip() + "\n")
            plan["new_file"] = os.path.abspath(args.write_new)

    # 6) Verify (unless no-apply)
    if not args.no_apply and not args.dry_run:
        after = verify_after(args.path, new_blocks, args.target)
        plan["after"] = after

    # 7) Reports
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as jf:
            jf.write(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    if args.md_out:
        lines = []
        lines.append(f"# Repair Plan — target {args.target}\n")
        lines.append(f"- Credulous preferred before? **{'YES' if cred_before else 'NO'}**")
        lines.append(f"- Direct blockers (by preferred frequency): {', '.join(blocker_ids) if blocker_ids else '(none)'}")
        lines.append(f"- Groups → new nodes: " + "; ".join([f"{g['new_id']}→({', '.join(g['attacks_ids'])})" for g in plan['groups']]) )
        lines.append("")
        lines.append("## New claims")
        for nb in new_blocks:
            lines.append(nb.strip()); lines.append("")
        if "after" in plan:
            ok = "YES" if plan['after']['preferred_credulous_target'] else "NO"
            lines.append(f"## Verification\nPreferred credulous after? **{ok}**")
        with open(args.md_out, "w", encoding="utf-8") as mf:
            mf.write("\n".join(lines) + "\n")

    # 8) Default stdout (if nothing else requested)
    if not (args.json_out or args.md_out):
        print(json.dumps(plan, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
