#!/usr/bin/env python3
"""
Unified server.py — Argument Debugger (AF + ad.py on winners)

Exposes two JSON endpoints used by the frontend:
- POST /api/run/af      → Build AF from text with nl2apx, compute semantics with af_clingo
- POST /api/ad/winners  → Compute winning sets (preferred/stable/...), run ad.py on each stance

This file has no external app routers; everything is self-contained.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Core dependencies from this repo ---
import nl2apx as NL
import af_clingo

# ad.py is optional; the winners endpoint will report if not available
try:
    import ad as AD
    _HAVE_AD = True
except Exception:  # pragma: no cover
    AD = None  # type: ignore
    _HAVE_AD = False


# -----------------------------
# Helpers (AF build + semantics)
# -----------------------------

def _sanitize_atom(s: str) -> str:
    import re
    s0 = (s or "").strip().lower()
    s1 = re.sub(r"[^a-z0-9_]+", "_", s0)
    if not re.match(r"^[a-z]", s1):
        s1 = "n_" + s1
    s1 = re.sub(r"__+", "_", s1).strip("_")
    return s1 or "n"


def build_af_from_text(
    text: str,
    relation: str = "auto",
    jaccard: float = 0.45,
    min_overlap: int = 3,
    use_llm: bool = False,
    llm_threshold: float = 0.55,
    llm_mode: str = "augment",
):
    """Build AF from raw text (blocks separated by blank lines)."""
    # nl2apx.parse_blocks expects a file path; use temp file for safety
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
        tf.write(text or "")
        tmp_path = tf.name
    try:
        blocks = NL.parse_blocks(tmp_path)
        ids, id2text, idx_edges, meta = NL.build_edges(
            blocks,
            relation_mode=relation,
            jac_threshold=jaccard,
            min_overlap=min_overlap,
            use_llm=use_llm,
            llm_threshold=llm_threshold,
            llm_mode=llm_mode,
        )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    # Map IDs → APX atoms (stable, human-readable)
    id2atom: Dict[str, str] = {}
    used = set()
    for _id in ids:
        base = _sanitize_atom(_id)
        k = base
        i = 1
        while k in used:
            i += 1
            k = f"{base}_{i}"
        id2atom[_id] = k
        used.add(k)
    atom2id = {v: k for k, v in id2atom.items()}

    # Translate index edges into atom-space attacks
    attacks: Set[Tuple[str, str]] = set()
    L = list(ids)
    for (i, j) in idx_edges:
        attacks.add((id2atom[L[i]], id2atom[L[j]]))

    atoms = [id2atom[_id] for _id in ids]
    return ids, id2text, atoms, attacks, id2atom, atom2id, meta


def compute_semantics(atoms: List[str], attacks: Set[Tuple[str, str]]):
    """Return all core semantics in one dict."""
    return dict(
        grounded=list(af_clingo.grounded(atoms, attacks)),
        preferred=[list(S) for S in af_clingo.preferred(atoms, attacks)],
        stable=[list(S) for S in af_clingo.stable(atoms, attacks)],
        complete=[list(S) for S in af_clingo.complete(atoms, attacks)],
        stage=[list(S) for S in af_clingo.stage(atoms, attacks)],
        semi_stable=[list(S) for S in af_clingo.semi_stable(atoms, attacks)],
    )


def winners(atoms: List[str], attacks: Set[Tuple[str, str]], mode: str):
    m = (mode or "preferred").lower()
    if m == "grounded":
        return [set(af_clingo.grounded(atoms, attacks))]
    if m == "preferred":
        return [set(S) for S in af_clingo.preferred(atoms, attacks)]
    if m == "stable":
        return [set(S) for S in af_clingo.stable(atoms, attacks)]
    if m == "complete":
        return [set(S) for S in af_clingo.complete(atoms, attacks)]
    if m == "stage":
        return [set(S) for S in af_clingo.stage(atoms, attacks)]
    if m in ("semi-stable", "semistable", "semi_stable"):
        return [set(S) for S in af_clingo.semi_stable(atoms, attacks)]
    raise ValueError(f"Unknown winners mode: {mode}")


def _stance_text(member_ids: List[str], id2text: Dict[str, str]) -> str:
    parts = []
    for mid in member_ids:
        t = (id2text.get(mid) or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts).strip()


# ---------------------------------
# ad.py analysis for a stance (text)
# ---------------------------------

def _analyze_stance_with_ad(text: str, want_repair: bool = False) -> Dict[str, Any]:
    if not _HAVE_AD:
        return {"error": "ad.py not available"}
    try:
        parser = AD.ArgumentParser()
        argument = parser.parse_argument(text)
        issues = AD.ASPDebugger(debug=False).analyze(argument)
        payload: Dict[str, Any] = {
            "claims": [
                {"id": c.id, "type": c.type, "content": c.content} for c in argument.claims
            ],
            "inferences": [
                {"from": i.from_claims, "to": i.to_claim, "rule_type": i.rule_type}
                for i in argument.inferences
            ],
            "goal_claim": argument.goal_claim,
            "issues": [
                {"type": it.type, "description": it.description, "claims": it.involved_claims}
                for it in issues
            ],
        }
        if want_repair and issues:
            rep = AD.RepairGenerator(debug=False)
            commentary, clean = rep.generate_repair(text, argument, issues)
            payload["repair"] = {"commentary": commentary, "clean_argument": clean}
        return payload
    except Exception as e:  # pragma: no cover
        return {"error": f"ad.py failed: {e.__class__.__name__}: {e}"}


# ----------------
# Pydantic models
# ----------------

class RunRequest(BaseModel):
    text: str
    relation: str = "auto"                  # auto|explicit|none
    use_llm: bool = False
    llm_mode: str = "augment"               # augment|override
    llm_threshold: float = 0.55
    jaccard: float = 0.45
    min_overlap: int = 3


class WinnersRequest(RunRequest):
    winners: str = "preferred"              # preferred|stable|grounded|complete|stage|semi-stable
    limit_stances: int = 5
    repair_stance: bool = False


# ---------
# FastAPI
# ---------

app = FastAPI(title="Argument Debugger Server", version="1.0-unified")

# CORS for local dev; adjust allow_origins for prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "ad_available": _HAVE_AD}


@app.post("/api/run/af")
def api_run_af(req: RunRequest):
    try:
        ids, id2text, atoms, attacks, id2atom, atom2id, meta = build_af_from_text(
            text=req.text,
            relation=req.relation,
            jaccard=req.jaccard,
            min_overlap=req.min_overlap,
            use_llm=req.use_llm,
            llm_threshold=req.llm_threshold,
            llm_mode=req.llm_mode,
        )
        sem = compute_semantics(atoms, set(attacks))
        return {
            "input": {
                "ids": ids,
                "id2text": id2text,
                "id2atom": id2atom,
                "atom2id": atom2id,
                "attacks": sorted(list(attacks)),
                "meta": {
                    "explicit_edges": meta.get("explicit_edges") or [],
                    "heuristic_edges": meta.get("heuristic_edges") or [],
                    "llm_edges": meta.get("llm_edges") or [],
                },
            },
            "semantics": sem,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AF build failed: {e}")


@app.post("/api/ad/winners")
def api_ad_winners(req: WinnersRequest):
    try:
        ids, id2text, atoms, attacks, id2atom, atom2id, meta = build_af_from_text(
            text=req.text,
            relation=req.relation,
            jaccard=req.jaccard,
            min_overlap=req.min_overlap,
            use_llm=req.use_llm,
            llm_threshold=req.llm_threshold,
            llm_mode=req.llm_mode,
        )
        ext = winners(atoms, attacks, req.winners)
        if req.limit_stances and len(ext) > req.limit_stances:
            ext = ext[: req.limit_stances]

        stances = []
        for i, S in enumerate(ext, 1):
            mids = sorted([atom2id[a] for a in S])
            text = _stance_text(mids, id2text)
            ad_res = _analyze_stance_with_ad(text, want_repair=req.repair_stance) if text else {"error": "empty stance text"}
            stances.append({"name": f"S{i}", "members_ids": mids, "ad": ad_res})

        # Simple Markdown (frontend renders this directly)
        def _md_escape(s: str) -> str:
            return (s or "").replace("|", "\\|")

        def _preview(s: str, n: int = 140) -> str:
            s = (s or "").strip().replace("\n", " ")
            return s if len(s) <= n else s[: n - 1] + "…"

        lines = []
        exp = len(meta.get("explicit_edges") or [])
        heu = len(meta.get("heuristic_edges") or [])
        llm = len(meta.get("llm_edges") or [])
        lines += [
            "# Winning sets analyzed by ad.py",
            "",
            "## AF Extraction",
            f"- explicit attacks: **{exp}**, heuristic: **{heu}**, llm: **{llm}**",
            f"- winners semantics: **{req.winners}**",
            "",
        ]
        if not stances:
            lines.append("_No winning sets under this semantics._")
        for i2, S2 in enumerate(stances, 1):
            mids = S2["members_ids"]
            lines.append(f"## Stance S{i2} — members ({len(mids)}): {{ " + ", ".join(mids) + " }}")
            for mid in mids:
                atom = id2atom.get(mid, "?")
                snip = _preview(id2text.get(mid, ""))
                lines.append(f"- **{mid}** (`{atom}`): {snip}")
            lines.append("")

            ad = S2.get("ad", {})
            if ad.get("error"):
                lines.append(f"_ad.py analysis skipped: {ad['error']}_")
                lines.append("")
                continue

            claims = ad.get("claims") or []
            infs = ad.get("inferences") or []
            goal = ad.get("goal_claim") or "—"
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
                    to = inf.get("to") or inf.get("to_claim")
                    rt = inf.get("rule_type", "")
                    to_txt = _preview(cmap.get(to, ""))
                    lines.append(f"- [{frm}] → {to} ({rt}) — “{_md_escape(to_txt)}”")

            # Issues (grouped)
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
                            txt = _preview(cmap.get(cid, ""))
                            annot.append(f"`{cid}` — “{_md_escape(txt)}”")
                        ann = "; ".join(annot) if annot else "(no specific claims)"
                        lines.append(f"- {it['description']} {ann}")

            # Repair excerpt
            rep = ad.get("repair")
            if rep and rep.get("commentary"):
                lines.append("")
                lines.append("**Repair commentary (excerpt)**")
                comm = (rep["commentary"] or "").strip()
                if len(comm) > 600:
                    comm = comm[:600] + "…"
                lines.append(comm)

            lines.append("")

        md = "\n".join(lines)

        return {
            "meta": {
                "ids": ids,
                "id2atom": id2atom,
                "winners": req.winners,
                "ad_available": _HAVE_AD,
            },
            "stances": stances,
            "markdown": md,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Winners analysis failed: {e}")


# -------------
# Entrypoint
# -------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
