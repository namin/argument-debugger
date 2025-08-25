# server_winners_router.py
"""
FastAPI router that exposes /api/ad/winners:
- Builds AF from the posted text (nl2apx).
- Computes winning sets under a selected semantics.
- Runs ad.py on each winning set (stance).
- Returns Markdown + structured JSON.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel
from fastapi import APIRouter
import tempfile, os

import nl2apx as NL
import af_clingo

# ad.py is optional at import time; endpoint will report if missing
try:
    import ad as AD
    _HAVE_AD = True
except Exception:
    _HAVE_AD = False

router = APIRouter()

# ---------------- models ----------------

class WinnersRequest(BaseModel):
    text: str
    relation: str = "auto"                 # auto|explicit|none
    use_llm: bool = False
    llm_mode: str = "augment"              # augment|override
    llm_threshold: float = 0.55
    jaccard: float = 0.45
    min_overlap: int = 3
    winners: str = "preferred"             # preferred|stable|grounded|complete|stage|semi-stable
    limit_stances: int = 5
    repair_stance: bool = False            # run ad.py repair on each stance

# ---------------- helpers ----------------

def _sanitize_atom(s: str) -> str:
    import re
    s0 = s.strip().lower()
    s1 = re.sub(r"[^a-z0-9_]+", "_", s0)
    if not re.match(r"^[a-z]", s1):
        s1 = "n_" + s1
    s1 = re.sub(r"__+", "_", s1).strip("_")
    return s1 or "n"

def _build_af_from_text(req: WinnersRequest):
    # nl2apx.parse_blocks expects a file path
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
        tf.write(req.text)
        tmp_path = tf.name
    try:
        blocks = NL.parse_blocks(tmp_path)
        ids, id2text, idx_edges, meta = NL.build_edges(
            blocks,
            relation_mode=req.relation,
            jac_threshold=req.jaccard,
            min_overlap=req.min_overlap,
            use_llm=req.use_llm,
            llm_threshold=req.llm_threshold,
            llm_mode=req.llm_mode,
        )
    finally:
        try: os.remove(tmp_path)
        except: pass

    id2atom: Dict[str, str] = {}
    used = set()
    for _id in ids:
        a = _sanitize_atom(_id)
        k, j = a, 1
        while k in used:
            j += 1
            k = f"{a}_{j}"
        id2atom[_id] = k
        used.add(k)
    atom2id = {v: k for k, v in id2atom.items()}

    attacks: Set[Tuple[str,str]] = set()
    id_list = list(ids)
    for (i, j) in idx_edges:
        attacks.add((id2atom[id_list[i]], id2atom[id_list[j]]))

    atoms = [id2atom[_id] for _id in ids]
    return ids, id2text, atoms, attacks, id2atom, atom2id, meta

def _winners(atoms, attacks, mode: str):
    m = (mode or "preferred").lower()
    if m == "grounded":   return [set(af_clingo.grounded(atoms, attacks))]
    if m == "preferred":  return [set(S) for S in af_clingo.preferred(atoms, attacks)]
    if m == "stable":     return [set(S) for S in af_clingo.stable(atoms, attacks)]
    if m == "complete":   return [set(S) for S in af_clingo.complete(atoms, attacks)]
    if m == "stage":      return [set(S) for S in af_clingo.stage(atoms, attacks)]
    if m in ("semi-stable","semistable","semi_stable"):
        return [set(S) for S in af_clingo.semi_stable(atoms, attacks)]
    raise ValueError(f"Unknown winners mode: {mode}")

def _stance_text(member_ids: List[str], id2text: Dict[str,str]) -> str:
    return "\n\n".join([(id2text.get(i) or "").strip() for i in member_ids if (id2text.get(i) or "").strip()]).strip()

def _analyze_stance_with_ad(text: str, want_repair: bool = False) -> Dict[str, Any]:
    if not _HAVE_AD:
        return {"error": "ad.py not available"}
    parser = AD.ArgumentParser()
    argument = parser.parse_argument(text)
    issues = AD.ASPDebugger(debug=False).analyze(argument)
    out = {
        "claims": [{"id": c.id, "type": c.type, "content": c.content} for c in argument.claims],
        "inferences": [{"from": i.from_claims, "to": i.to_claim, "rule_type": i.rule_type} for i in argument.inferences],
        "goal_claim": argument.goal_claim,
        "issues": [{"type": it.type, "description": it.description, "claims": it.involved_claims} for it in issues],
    }
    if want_repair and issues:
        rep = AD.RepairGenerator(debug=False)
        commentary, clean = rep.generate_repair(text, argument, issues)
        out["repair"] = {"commentary": commentary, "clean_argument": clean}
    return out

def _md_escape(s: str) -> str: return (s or "").replace("|","\\|")
def _preview(s: str, n: int = 140) -> str:
    s = (s or "").strip().replace("\\n"," ")
    return s if len(s) <= n else s[: n - 1] + "…"

def _md_winners_report(sem_mode: str, ids, id2text, id2atom, meta, stances):
    lines = []
    exp = len(meta.get("explicit_edges") or [])
    heu = len(meta.get("heuristic_edges") or [])
    llm = len(meta.get("llm_edges") or [])
    lines += [
        "# Winning sets analyzed by ad.py",
        "",
        "## AF Extraction",
        f"- explicit attacks: **{exp}**, heuristic: **{heu}**, llm: **{llm}**",
        f"- winners semantics: **{sem_mode}**",
        "",
    ]
    if not stances:
        lines.append("_No winning sets under this semantics._")
        return "\\n".join(lines)

    for i, S in enumerate(stances, 1):
        mids = S["members_ids"]
        lines.append(f"## Stance S{i} — members ({len(mids)}): {{ " + ", ".join(mids) + " }}")
        for mid in mids:
            atom = id2atom.get(mid, "?")
            snip = _preview(id2text.get(mid,""))
            lines.append(f"- **{mid}** (`{atom}`): {snip}")
        lines.append("")

        ad = S.get("ad", {})
        if ad.get("error"):
            lines.append(f"_ad.py analysis skipped: {ad['error']}_")
            lines.append("")
            continue

        claims = ad.get("claims") or []
        infs   = ad.get("inferences") or []
        goal   = ad.get("goal_claim") or "—"
        issues = ad.get("issues") or []
        lines.append(f"**ad.py parse:** claims={len(claims)}, inferences={len(infs)}, goal={goal}")

        # Claims table
        lines.append("")
        lines.append("**Claims parsed**")
        if not claims:
            lines.append("_no claims parsed_")
        else:
            lines.append("| Claim | Type | Text |")
            lines.append("|:-----:|:-----|:-----|")
            for c in claims:
                lines.append(f"| `{c['id']}` | {c['type']} | {_md_escape(_preview(c['content']))} |")

        # Inferences
        lines.append("")
        lines.append("**Inferences**")
        cmap = {c["id"]: c["content"] for c in claims}
        if not infs:
            lines.append("_no inferences_")
        else:
            for inf in infs:
                frm = ", ".join(inf.get("from") or inf.get("from_claims", []))
                to  = inf.get("to") or inf.get("to_claim")
                rt  = inf.get("rule_type","")
                to_txt = _preview(cmap.get(to,""))
                lines.append(f"- [{frm}] → {to} ({rt}) — “{_md_escape(to_txt)}”")

        # Issues (detailed)
        lines.append("")
        lines.append("**Issues (detailed)**")
        if not issues:
            lines.append("_no issues detected_")
        else:
            from collections import defaultdict
            g = defaultdict(list)
            for it in issues:
                g[it["type"]].append(it)
            for t in sorted(g):
                lines.append(f"**{t}**")
                for it in g[t]:
                    cl = it.get("claims") or []
                    annot = []
                    for cid in cl:
                        txt = _preview(cmap.get(cid,""))
                        annot.append(f"`{cid}` — “{_md_escape(txt)}”")
                    ann = "; ".join(annot) if annot else "(no specific claims)"
                    lines.append(f"- {it['description']} {ann}")

        # Repair excerpt
        rep = ad.get("repair")
        if rep and rep.get("commentary"):
            lines.append("")
            lines.append("**Repair commentary (excerpt)**")
            comm = rep["commentary"].strip()
            if len(comm) > 600: comm = comm[:600] + "…"
            lines.append(comm)

        lines.append("")
    return "\\n".join(lines)

# ---------------- endpoint ----------------

@router.post("/winners")
def winners_endpoint(req: WinnersRequest):
    ids, id2text, atoms, attacks, id2atom, atom2id, meta = _build_af_from_text(req)
    ext = _winners(atoms, attacks, req.winners)
    if req.limit_stances and len(ext) > req.limit_stances:
        ext = ext[:req.limit_stances]

    stances = []
    for i, S_atoms in enumerate(ext, 1):
        mids = sorted([atom2id[a] for a in S_atoms])
        text = _stance_text(mids, id2text)
        ad_res = _analyze_stance_with_ad(text, want_repair=req.repair_stance) if text else {"error": "empty stance text"}
        stances.append({"name": f"S{i}", "members_ids": mids, "ad": ad_res})

    md = _md_winners_report(req.winners, ids, id2text, id2atom, meta, stances)
    return {
        "meta": {
            "ids": ids,
            "id2atom": id2atom,
            "winners": req.winners,
            "ad_available": _HAVE_AD
        },
        "stances": stances,
        "markdown": md
    }
