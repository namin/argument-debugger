#!/usr/bin/env python3
"""
Unified server.py — Argument Debugger (AF + rich report + ad.py on winners)

Endpoints:
- POST /api/run/af      → Build AF from text; rich argsem-style JSON + Markdown
- POST /api/ad/winners  → Compute winning sets; run ad.py on each stance
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import nl2apx as NL
import af_clingo

try:
    import ad as AD
    _HAVE_AD = True
except Exception:
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
        try: os.remove(tmp_path)
        except Exception: pass

    # Map IDs → APX atoms
    id2atom: Dict[str, str] = {}
    used = set()
    for _id in ids:
        base = _sanitize_atom(_id)
        k = base; i = 1
        while k in used:
            i += 1; k = f"{base}_{i}"
        id2atom[_id] = k; used.add(k)
    atom2id = {v: k for k, v in id2atom.items()}

    # idx_edges → atom-space attacks
    attacks: Set[Tuple[str, str]] = set()
    L = list(ids)
    for (i, j) in idx_edges:
        attacks.add((id2atom[L[i]], id2atom[L[j]]))

    atoms = [id2atom[_id] for _id in ids]
    return ids, id2text, atoms, attacks, id2atom, atom2id, meta


def compute_semantics(atoms: List[str], attacks: Set[Tuple[str, str]]):
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
    if m == "grounded":   return [set(af_clingo.grounded(atoms, attacks))]
    if m == "preferred":  return [set(S) for S in af_clingo.preferred(atoms, attacks)]
    if m == "stable":     return [set(S) for S in af_clingo.stable(atoms, attacks)]
    if m == "complete":   return [set(S) for S in af_clingo.complete(atoms, attacks)]
    if m == "stage":      return [set(S) for S in af_clingo.stage(atoms, attacks)]
    if m in ("semi-stable", "semistable", "semi_stable"):
        return [set(S) for S in af_clingo.semi_stable(atoms, attacks)]
    raise ValueError(f"Unknown winners mode: {mode}")


# -----------------------------
# Rich report helpers (argsem-like)
# -----------------------------

def _short(s: str, n: int = 110) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _id_attacks_from_atoms(attacks_atom: Set[Tuple[str,str]], atom2id: Dict[str,str]) -> Set[Tuple[str,str]]:
    return {(atom2id[u], atom2id[v]) for (u, v) in attacks_atom}


def _attacks_by_tag(ids: List[str], meta: Dict) -> Dict[str, List[Tuple[str,str]]]:
    # meta has lists of (i,j) pairs
    def to_id_pairs(key: str) -> List[Tuple[str,str]]:
        pairs = meta.get(key) or []
        out = []
        for (i, j) in pairs:
            if 0 <= i < len(ids) and 0 <= j < len(ids):
                out.append((ids[i], ids[j]))
        return out
    return {
        "explicit": to_id_pairs("explicit_edges"),
        "heuristic": to_id_pairs("heuristic_edges"),
        "llm": to_id_pairs("llm_edges"),
    }


def _defense_depth(ids: List[str], id_attacks: Set[Tuple[str,str]]) -> Tuple[Set[str], Dict[str, Optional[int]]]:
    # Grounded fixpoint with iteration depths (1-based)
    attackers: Dict[str, Set[str]] = {x: set() for x in ids}
    attacks_of: Dict[str, Set[str]] = {x: set() for x in ids}
    for u, v in id_attacks:
        attacks_of[u].add(v)
        attackers[v].add(u)

    def defended(S: Set[str], a: str) -> bool:
        # For every b attacking a, some c in S attacks b
        for b in attackers[a]:
            ok = False
            for c in S:
                if b in attacks_of[c]:
                    ok = True; break
            if not ok:
                return False
        return True

    S: Set[str] = set()
    depth: Dict[str, Optional[int]] = {x: None for x in ids}
    k = 0
    while True:
        T = {a for a in ids if defended(S, a)}
        if T == S:
            break
        k += 1
        for a in (T - S):
            depth[a] = k
        S = T
    return S, depth


def _membership_counts(ids: List[str], id2atom: Dict[str,str], sem: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    # For each id, produce booleans / counts per semantics family
    res: Dict[str, Dict[str, Any]] = {i: {} for i in ids}
    # Grounded
    grounded_atoms = set(sem["grounded"])
    for i in ids:
        res[i]["grounded"] = id2atom[i] in grounded_atoms
    # k-ary families
    def count_in(fam: List[List[str]]) -> Dict[str, int]:
        # fam is list of extensions (atoms)
        cnt = {i: 0 for i in ids}
        for S in fam or []:
            Sset = set(S)
            for i in ids:
                if id2atom[i] in Sset:
                    cnt[i] += 1
        return cnt
    res_pref = count_in(sem["preferred"])
    res_stab = count_in(sem["stable"])
    res_comp = count_in(sem["complete"])
    res_stage = count_in(sem["stage"])
    res_semi  = count_in(sem["semi_stable"])
    for i in ids:
        res[i]["preferred"] = (res_pref[i], len(sem["preferred"]))
        res[i]["stable"]    = (res_stab[i], len(sem["stable"]))
        res[i]["complete"]  = (res_comp[i], len(sem["complete"]))
        res[i]["stage"]     = (res_stage[i], len(sem["stage"]))
        res[i]["semi"]      = (res_semi[i], len(sem["semi_stable"]))
    return res


def _preferred_cards(ids: List[str], id2text: Dict[str,str], id2atom: Dict[str,str], sem: Dict[str, Any], k: int = 4) -> List[Dict[str, Any]]:
    cards = []
    for S_atoms in (sem["preferred"] or [])[:k]:
        members = [i for i in ids if id2atom[i] in set(S_atoms)]
        preview = "; ".join(_short(id2text[i], 80) for i in members[:3])
        cards.append({"members": members, "preview": preview})
    return cards


def _why_not_target(target: Optional[str], ids: List[str], id2atom: Dict[str,str],
                    id_attacks: Set[Tuple[str,str]], sem: Dict[str, Any]) -> Dict[str, Any]:
    if not target or target not in ids:
        return {}
    # Prepare maps
    attackers_of: Dict[str, Set[str]] = {x: set() for x in ids}
    for u, v in id_attacks:
        attackers_of[v].add(u)

    grounded_atoms = set(sem["grounded"])
    grounded_ids   = {i for i in ids if id2atom[i] in grounded_atoms}
    target_in_grounded = target in grounded_ids

    # Roadblocks: attackers of target that are not attacked by grounded
    # (strict: "undefeated attackers by the grounded set")
    attacks_of: Dict[str, Set[str]] = {x: set() for x in ids}
    for u, v in id_attacks:
        attacks_of[u].add(v)
    grounded_attack_set = set()
    for g in grounded_ids:
        grounded_attack_set |= {(g, x) for x in attacks_of[g]}
    roadblocks = []
    for a in sorted(attackers_of[target]):
        # a is undefeated if no grounded member attacks a
        if not any((g, a) in grounded_attack_set for g in grounded_ids):
            roadblocks.append(a)

    # Preferred coverage
    pref = [set(S) for S in sem["preferred"] or []]            # atoms
    pref_ids = [{i for i in ids if id2atom[i] in S} for S in pref]
    k = len(pref_ids)
    target_in_pref = sum(1 for S in pref_ids if target in S)

    # Persistent vs soft attackers across preferred stances
    if k > 0:
        att = attackers_of[target]
        per = set(att)
        anyset = set()
        for S in pref_ids:
            S_att = S & att
            anyset |= S_att
            per &= S_att
        soft = anyset - per
    else:
        per, soft = set(), set()

    return dict(
        grounded_in = target_in_grounded,
        preferred_coverage = [target_in_pref, k],
        grounded_roadblocks = roadblocks,
        preferred_persistent_attackers = sorted(per),
        preferred_soft_attackers = sorted(soft),
    )


def _make_argsem_markdown(filename: str,
                          ids: List[str], id2text: Dict[str,str], id2atom: Dict[str,str],
                          attacks_tagged: Dict[str, List[Tuple[str,str]]],
                          id_attacks: Set[Tuple[str,str]],
                          sem: Dict[str, Any],
                          depth: Dict[str, Optional[int]],
                          pref_cards: List[Dict[str, Any]],
                          why: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Argumentation Semantics Report — {filename}")
    lines.append("")
    # Arguments
    lines.append("## Arguments (ID → APX atom)")
    for i in ids:
        lines.append(f"- **{i}** (`{id2atom[i]}`): {_short(id2text[i])}")
    lines.append("")

    # Attacks with provenance tags
    lines.append("## Attacks")
    tags_for = {}
    for tag, pairs in attacks_tagged.items():
        for (u, v) in pairs:
            tags_for.setdefault((u, v), []).append({"explicit":"exp","heuristic":"heu","llm":"llm"}[tag])
    if not id_attacks:
        lines.append("_none_")
    else:
        for (u, v) in sorted(id_attacks):
            tag = tags_for.get((u, v), [])
            tstr = f" [{' ,'.join(tag)}]" if tag else ""
            lines.append(f"- {u} ({id2atom[u]}) → {v} ({id2atom[v]}){tstr}")
    lines.append("")

    # Semantics table
    lines.append("## Semantics (membership & depth)")
    lines.append("| ID | Atom | Grounded | Pref | Stable | Complete | Stage | SemiSt | Depth |")
    lines.append("|---:|:-----|:--------:|:----:|:------:|:--------:|:-----:|:------:|:-----:|")
    mem = _membership_counts(ids, id2atom, sem)
    for i in ids:
        g = "✓" if mem[i]["grounded"] else ""
        p = mem[i]["preferred"]; pstr = f"{p[0]}/{p[1]}"
        s = mem[i]["stable"];    sstr = f"{s[0]}/{s[1]}"
        c = mem[i]["complete"];  cstr = f"{c[0]}/{c[1]}"
        st= mem[i]["stage"];     ststr= f"{st[0]}/{st[1]}"
        se= mem[i]["semi"];      sestr= f"{se[0]}/{se[1]}"
        d = depth.get(i) or ""
        lines.append(f"| {i} | `{id2atom[i]}` | {g} | {pstr} | {sstr} | {cstr} | {ststr} | {sestr} | {d} |")
    lines.append("")

    # Preferred “stance cards”
    if pref_cards:
        lines.append("## Preferred “stance cards”")
        for idx, card in enumerate(pref_cards, 1):
            members = ", ".join(card["members"])
            lines.append(f"**S{idx}** = {{{members}}}")
            lines.append(f"  - preview: {card['preview']}")
        lines.append("")

    # Why/Why-not
    if why:
        lines.append("## Why (not) target")
        gi = "YES" if why.get("grounded_in") else "NO"
        pc = why.get("preferred_coverage") or [0,0]
        lines.append(f"- In grounded? **{gi}**")
        lines.append(f"- Preferred coverage: **{pc[0]}/{pc[1]}**")
        rb = why.get("grounded_roadblocks") or []
        if rb:
            lines.append(f"- Grounded roadblocks (undefeated attackers): {', '.join(rb)}")
        per = why.get("preferred_persistent_attackers") or []
        soft = why.get("preferred_soft_attackers") or []
        lines.append(f"- Across preferred: persistent attackers: {', '.join(per) if per else '(none)'}; soft attackers: {', '.join(soft) if soft else '(none)'}")
        lines.append("")
    return "\n".join(lines)


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
            "claims": [{"id": c.id, "type": c.type, "content": c.content} for c in argument.claims],
            "inferences": [{"from": i.from_claims, "to": i.to_claim, "rule_type": i.rule_type} for i in argument.inferences],
            "goal_claim": argument.goal_claim,
            "issues": [{"type": it.type, "description": it.description, "claims": it.involved_claims} for it in issues],
        }
        if want_repair and issues:
            rep = AD.RepairGenerator(debug=False)
            commentary, clean = rep.generate_repair(text, argument, issues)
            payload["repair"] = {"commentary": commentary, "clean_argument": clean}
        return payload
    except Exception as e:
        return {"error": f"ad.py failed: {e.__class__.__name__}: {e}"}


# ----------------
# Pydantic models
# ----------------

class RunRequest(BaseModel):
    text: str
    relation: str = "auto"         # auto|explicit|none
    use_llm: bool = False
    llm_mode: str = "augment"
    llm_threshold: float = 0.55
    jaccard: float = 0.45
    min_overlap: int = 3
    target: Optional[str] = None
    include_markdown: bool = True
    max_pref_cards: int = 4


class WinnersRequest(RunRequest):
    winners: str = "preferred"     # preferred|stable|grounded|complete|stage|semi-stable
    limit_stances: int = 5
    repair_stance: bool = False


# ---------
# FastAPI
# ---------

app = FastAPI(title="Argument Debugger Server", version="1.1-unified")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
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

        # Provenance & depth & why-not
        attacks_by_tag = _attacks_by_tag(ids, meta)
        id_attacks = _id_attacks_from_atoms(set(attacks), atom2id)
        grounded_ids, depth = _defense_depth(ids, id_attacks)
        pref_cards = _preferred_cards(ids, id2text, id2atom, sem, k=req.max_pref_cards)
        why = _why_not_target(req.target, ids, id2atom, id_attacks, sem) if req.target else {}

        report_md = None
        if req.include_markdown:
            report_md = _make_argsem_markdown(
                filename="session",
                ids=ids, id2text=id2text, id2atom=id2atom,
                attacks_tagged=attacks_by_tag,
                id_attacks=id_attacks,
                sem=sem, depth=depth,
                pref_cards=pref_cards,
                why=why,
            )

        return {
            "input": {
                "ids": ids,
                "id2text": id2text,
                "id2atom": id2atom,
                "atom2id": atom2id,
                "attacks": sorted(list(attacks)),
                "attacks_by_tag": attacks_by_tag,
                "meta": {
                    "explicit_edges": meta.get("explicit_edges") or [],
                    "heuristic_edges": meta.get("heuristic_edges") or [],
                    "llm_edges": meta.get("llm_edges") or [],
                },
            },
            "semantics": sem,
            "insights": {
                "grounded_set_ids": sorted(list(grounded_ids)),
                "defense_depth": depth,
                "preferred_cards": pref_cards,
                "why": why,
            },
            "report_markdown": report_md,
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
            text = "\n\n".join([(id2text.get(mid) or "").strip() for mid in mids if (id2text.get(mid) or "").strip()])
            ad_res = _analyze_stance_with_ad(text, want_repair=req.repair_stance) if text else {"error": "empty stance text"}
            stances.append({"name": f"S{i}", "members_ids": mids, "ad": ad_res})

        # simple Markdown (same as before)
        def _md_escape(s: str) -> str: return (s or "").replace("|","\\|")
        def _preview(s: str, n: int = 140) -> str:
            s = (s or "").strip().replace("\n"," ")
            return s if len(s) <= n else s[: n - 1] + "…"

        lines = []
        exp = len(meta.get("explicit_edges") or [])
        heu = len(meta.get("heuristic_edges") or [])
        llm = len(meta.get("llm_edges") or [])
        lines += [
            "# Winning sets analyzed by ad.py", "", "## AF Extraction",
            f"- explicit attacks: **{exp}**, heuristic: **{heu}**, llm: **{llm}**",
            f"- winners semantics: **{req.winners}**", "",
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
                lines.append(f"_ad.py analysis skipped: {ad['error']}_"); lines.append(""); continue
            claims = ad.get("claims") or []
            infs   = ad.get("inferences") or []
            goal   = ad.get("goal_claim") or "—"
            issues = ad.get("issues") or []
            lines.append(f"**ad.py parse:** claims={len(claims)}, inferences={len(infs)}, goal={goal}")
            lines.append(""); lines.append("**Claims parsed**")
            if not claims:
                lines.append("_no claims parsed_")
            else:
                lines.append("| Claim | Type | Text |"); lines.append("|:-----:|:-----|:-----|")
                for c in claims:
                    lines.append(f"| `{c['id']}` | {c['type']} | {_md_escape(_preview(c['content']))} |")
            lines.append(""); lines.append("**Inferences**")
            cmap = {c["id"]: c["content"] for c in claims}
            if not infs:
                lines.append("_no inferences_")
            else:
                for inf in infs:
                    frm = ", ".join(inf.get("from") or inf.get("from_claims", []))
                    to  = inf.get("to") or inf.get("to_claim")
                    rt  = inf.get("rule_type", "")
                    to_txt = _preview(cmap.get(to, ""))
                    lines.append(f"- [{frm}] → {to} ({rt}) — “{_md_escape(to_txt)}”")
            lines.append(""); lines.append("**Issues (detailed)**")
            if not issues:
                lines.append("_no issues detected_")
            else:
                from collections import defaultdict
                g = defaultdict(list)
                for it in issues: g[it["type"]].append(it)
                for t in sorted(g):
                    lines.append(f"**{t}**")
                    for it in g[t]:
                        cl = it.get("claims") or []
                        annot = []
                        for cid in cl:
                            txt = _preview(cmap.get(cid, "")); annot.append(f"`{cid}` — “{_md_escape(txt)}”")
                        ann = "; ".join(annot) if annot else "(no specific claims)"
                        lines.append(f"- {it['description']} {ann}")
            rep = ad.get("repair")
            if rep and rep.get("commentary"):
                lines.append(""); lines.append("**Repair commentary (excerpt)**")
                comm = (rep["commentary"] or "").strip()
                if len(comm) > 600: comm = comm[:600] + "…"
                lines.append(comm)
            lines.append("")
        md = "\n".join(lines)

        return {
            "meta": {"ids": ids, "id2atom": id2atom, "winners": req.winners, "ad_available": _HAVE_AD},
            "stances": stances,
            "markdown": md,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Winners analysis failed: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
