# unified_core.py
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

import nl2apx as NL
import af_clingo

try:
    import ad as AD
    HAVE_AD = True
except Exception:
    AD = None  # type: ignore
    HAVE_AD = False


# -------------------------
# AF build & sanitization
# -------------------------

def sanitize_atom(s: str) -> str:
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
    """Build AF from raw text (blocks separated by blank lines), returning
    ids, id2text, atoms, attacks(set of (a,b)), id2atom, atom2id, meta."""
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

    # IDs → atoms (stable names)
    id2atom: Dict[str, str] = {}
    used = set()
    for _id in ids:
        base = sanitize_atom(_id)
        k = base; i = 1
        while k in used:
            i += 1; k = f"{base}_{i}"
        id2atom[_id] = k; used.add(k)
    atom2id = {v: k for k, v in id2atom.items()}

    # idx_edges → attacks in atom space
    atoms = [id2atom[_id] for _id in ids]
    attacks: Set[Tuple[str,str]] = set()
    L = list(ids)
    for (i, j) in idx_edges:
        attacks.add((id2atom[L[i]], id2atom[L[j]]))

    return ids, id2text, atoms, attacks, id2atom, atom2id, meta


# -------------------------
# Semantics & insights
# -------------------------

def compute_semantics(atoms: List[str], attacks: Set[Tuple[str,str]]):
    return dict(
        grounded=list(af_clingo.grounded(atoms, attacks)),
        preferred=[list(S) for S in af_clingo.preferred(atoms, attacks)],
        stable=[list(S) for S in af_clingo.stable(atoms, attacks)],
        complete=[list(S) for S in af_clingo.complete(atoms, attacks)],
        stage=[list(S) for S in af_clingo.stage(atoms, attacks)],
        semi_stable=[list(S) for S in af_clingo.semi_stable(atoms, attacks)],
    )


def id_attacks_from_atoms(attacks_atom: Set[Tuple[str,str]], atom2id: Dict[str,str]) -> Set[Tuple[str,str]]:
    return {(atom2id[u], atom2id[v]) for (u, v) in attacks_atom}


def attacks_by_tag(ids: List[str], meta: Dict) -> Dict[str, List[Tuple[str,str]]]:
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


def grounded_fixpoint_depth(ids: List[str], id_attacks: Set[Tuple[str,str]]):
    # Classic grounded iteration with per-node "entry" depth
    attackers: Dict[str, Set[str]] = {x: set() for x in ids}
    attacks_of: Dict[str, Set[str]] = {x: set() for x in ids}
    for u, v in id_attacks:
        attacks_of[u].add(v)
        attackers[v].add(u)

    def defended(S: Set[str], a: str) -> bool:
        for b in attackers[a]:
            if not any((c in S and (b in attacks_of[c])) for c in S):
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


def preferred_cards(ids: List[str], id2text: Dict[str,str], id2atom: Dict[str,str], sem: Dict[str, Any], k: int = 4):
    cards = []
    for S_atoms in (sem["preferred"] or [])[:k]:
        Sset = set(S_atoms)
        members = [i for i in ids if id2atom[i] in Sset]
        preview = "; ".join(short(id2text[i], 80) for i in members[:3])
        cards.append({"members": members, "preview": preview})
    return cards


def winners(atoms: List[str], attacks: Set[Tuple[str,str]], mode: str):
    m = (mode or "preferred").lower()
    if m == "grounded":   return [set(af_clingo.grounded(atoms, attacks))]
    if m == "preferred":  return [set(S) for S in af_clingo.preferred(atoms, attacks)]
    if m == "stable":     return [set(S) for S in af_clingo.stable(atoms, attacks)]
    if m == "complete":   return [set(S) for S in af_clingo.complete(atoms, attacks)]
    if m == "stage":      return [set(S) for S in af_clingo.stage(atoms, attacks)]
    if m in ("semi-stable","semistable","semi_stable"): return [set(S) for S in af_clingo.semi_stable(atoms, attacks)]
    raise ValueError(m)


def why_not_target(target: Optional[str], ids: List[str], id2atom: Dict[str,str],
                   id_attacks: Set[Tuple[str,str]], sem: Dict[str, Any]) -> Dict[str, Any]:
    if not target or target not in ids:
        return {}
    attackers_of: Dict[str, Set[str]] = {x: set() for x in ids}
    attacks_of: Dict[str, Set[str]] = {x: set() for x in ids}
    for u, v in id_attacks:
        attackers_of[v].add(u)
        attacks_of[u].add(v)
    grounded_atoms = set(sem["grounded"])
    grounded_ids   = {i for i in ids if id2atom[i] in grounded_atoms}
    target_in_grounded = target in grounded_ids
    grounded_attack_set = {(g, t) for g in grounded_ids for t in attacks_of[g]}
    roadblocks = [a for a in sorted(attackers_of[target]) if not any((g, a) in grounded_attack_set for g in grounded_ids)]
    # preferred coverage + persistent/soft attackers
    pref = [set(S) for S in sem["preferred"] or []]
    pref_ids = [{i for i in ids if id2atom[i] in S} for S in pref]
    k = len(pref_ids)
    target_in_pref = sum(1 for S in pref_ids if target in S)
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


# -------------------------
# ad.py analysis
# -------------------------

def analyze_stance_with_ad(text: str, want_repair: bool = False, cqs: bool = False) -> Dict[str, Any]:
    if not HAVE_AD:
        return {"error": "ad.py not available"}
    parser = AD.ArgumentParser()
    argument = parser.parse_argument(text)
    
    # Attach CQ analysis if enabled
    if cqs:
        debugger = AD.ArgumentDebugger(debug=False, cq=cqs)
        debugger._attach_cq(argument, text)
    
    issues = AD.ASPDebugger(debug=False, cq=cqs).analyze(argument)
    out = {
        "claims": [{"id": c.id, "type": c.type, "content": c.content} for c in argument.claims],
        "inferences": [{"from": i.from_claims, "to": i.to_claim, "rule_type": i.rule_type} for i in argument.inferences],
        "goal_claim": argument.goal_claim,
        "issues": [{"type": it.type, "description": it.description, "claims": it.involved_claims} for it in issues],
    }
    if want_repair and issues:
        rep = AD.RepairGenerator(debug=False)
        comm, clean = rep.generate_repair(text, argument, issues)
        out["repair"] = {"commentary": comm, "clean_argument": clean}
    return out


# -------------------------
# Markdown builders
# -------------------------

def short(s: str, n: int = 110) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"

def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|")


def make_af_markdown(filename: str,
                     ids: List[str], id2text: Dict[str,str], id2atom: Dict[str,str],
                     attacks_tagged: Dict[str, List[Tuple[str,str]]],
                     id_attacks: Set[Tuple[str,str]],
                     sem: Dict[str, Any],
                     depth: Dict[str, Optional[int]],
                     pref_cards: List[Dict[str, Any]],
                     why: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# AF Report — {filename}")
    lines.append("")
    lines.append("## Arguments (ID → APX atom)")
    for i in ids:
        lines.append(f"- **{i}** (`{id2atom[i]}`): {short(id2text[i])}")
    lines.append("")
    lines.append("## Attacks")
    tag_map = {}
    for tag, pairs in attacks_tagged.items():
        for (u, v) in pairs:
            tag_map.setdefault((u, v), []).append({"explicit":"exp","heuristic":"heu","llm":"llm"}[tag])
    if not id_attacks:
        lines.append("_none_")
    else:
        for (u, v) in sorted(id_attacks):
            tags = tag_map.get((u, v), [])
            tstr = f" [{' ,'.join(tags)}]" if tags else ""
            lines.append(f"- {u} ({id2atom[u]}) → {v} ({id2atom[v]}){tstr}")
    lines.append("")
    lines.append("## Semantics (membership & depth)")
    lines.append("| ID | Atom | Grounded | Pref | Stable | Complete | Stage | SemiSt | Depth |")
    lines.append("|---:|:-----|:--------:|:----:|:------:|:--------:|:-----:|:------:|:-----:|")
    # membership counts
    mem = {}
    grounded_atoms = set(sem["grounded"])
    for i in ids:
        mem[i] = {"grounded": (id2atom[i] in grounded_atoms)}
    def cnt(fam: List[List[str]]):
        c = {i:0 for i in ids}
        for S in fam or []:
            Sset = set(S)
            for i in ids:
                if id2atom[i] in Sset:
                    c[i]+=1
        return c, len(fam or [])
    cp, kp = cnt(sem["preferred"])
    cs, ks = cnt(sem["stable"])
    cc, kc = cnt(sem["complete"])
    cg, kg = cnt(sem["stage"])
    ce, ke = cnt(sem["semi_stable"])
    for i in ids:
        g = "✓" if mem[i]["grounded"] else ""
        p = f"{cp[i]}/{kp}"; s=f"{cs[i]}/{ks}"; c=f"{cc[i]}/{kc}"; st=f"{cg[i]}/{kg}"; se=f"{ce[i]}/{ke}"
        d = depth.get(i) or ""
        lines.append(f"| {i} | `{id2atom[i]}` | {g} | {p} | {s} | {c} | {st} | {se} | {d} |")
    lines.append("")
    if pref_cards:
        lines.append("## Preferred “stance cards”")
        for idx, card in enumerate(pref_cards, 1):
            members = ", ".join(card["members"])
            lines.append(f"**S{idx}** = {{ {members} }}")
            lines.append(f"  - preview: {card['preview']}")
        lines.append("")
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


def make_ad_markdown(ids: List[str], id2text: Dict[str,str], id2atom: Dict[str,str],
                     sem_winners: List[Set[str]], atom2id: Dict[str,str],
                     repair: bool = False, cqs: bool = False) -> str:
    if not sem_winners:
        return "_No winning sets under this semantics._"
    lines = []
    for idx, S_atoms in enumerate(sem_winners, 1):
        mids = sorted([atom2id[a] for a in S_atoms])
        lines.append(f"## Stance S{idx} — members ({len(mids)}): {{ " + ", ".join(mids) + " }}")
        for mid in mids:
            lines.append(f"- **{mid}** (`{id2atom[mid]}`): {short(id2text[mid])}")
        lines.append("")
        stance_text = "\n\n".join([(id2text.get(mid) or "").strip() for mid in mids if (id2text.get(mid) or "").strip()]).strip()
        if not stance_text:
            lines.append("_empty stance text_"); lines.append(""); continue
        ad = analyze_stance_with_ad(stance_text, want_repair=repair, cqs=cqs) if HAVE_AD else {"error":"ad.py not available"}
        if ad.get("error"):
            lines.append(f"_ad.py analysis skipped: {ad['error']}_"); lines.append(""); continue
        claims = ad.get("claims") or []
        infs   = ad.get("inferences") or []
        goal   = ad.get("goal_claim") or "—"
        issues = ad.get("issues") or []
        lines.append(f"**ad.py parse:** claims={len(claims)}, inferences={len(infs)}, goal={goal}")
        lines.append("")
        lines.append("**Claims parsed**")
        if not claims:
            lines.append("_no claims parsed_")
        else:
            lines.append("| Claim | Type | Text |"); lines.append("|:-----:|:-----|:-----|")
            for c in claims:
                lines.append(f"| `{c['id']}` | {c['type']} | {md_escape(short(c['content'], 140))} |")
        lines.append("")
        lines.append("**Inferences**")
        cmap = {c["id"]: c["content"] for c in claims}
        if not infs:
            lines.append("_no inferences_")
        else:
            for inf in infs:
                frm = ", ".join(inf.get("from") or inf.get("from_claims", []))
                to  = inf.get("to") or inf.get("to_claim")
                rt  = inf.get("rule_type", "")
                to_txt = short(cmap.get(to, ""), 140)
                lines.append(f"- [{frm}] → {to} ({rt}) — “{md_escape(to_txt)}”")
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
                        txt = short(cmap.get(cid, ""), 140)
                        annot.append(f"`{cid}` — “{md_escape(txt)}”")
                    ann = "; ".join(annot) if annot else "(no specific claims)"
                    lines.append(f"- {it['description']} {ann}")
        rep = ad.get("repair")
        if rep and rep.get("commentary"):
            lines.append("")
            lines.append("**Repair commentary (excerpt)**")
            comm = (rep["commentary"] or "").strip()
            lines.append(comm)
        lines.append("")
    return "\n".join(lines)


def make_unified_markdown(filename: str,
                          ids: List[str], id2text: Dict[str,str], id2atom: Dict[str,str], atom2id: Dict[str,str],
                          attacks_tagged: Dict[str, List[Tuple[str,str]]],
                          id_attacks: Set[Tuple[str,str]],
                          sem: Dict[str, Any],
                          depth: Dict[str, Optional[int]],
                          pref_cards: List[Dict[str, Any]],
                          why: Dict[str, Any],
                          winners_sets: List[Set[str]],
                          winners_name: str,
                          repair: bool, cqs: bool = False) -> str:
    af_md = make_af_markdown(filename, ids, id2text, id2atom, attacks_tagged, id_attacks, sem, depth, pref_cards, why)
    ad_md = make_ad_markdown(ids, id2text, id2atom, winners_sets, atom2id, repair=repair, cqs=cqs)
    parts = [
        "# Unified AF + ad.py Report",
        "",
        "## Part 1 — AF (one graph, consistent edges)",
        af_md,
        "---",
        f"## Part 2 — Winners analyzed by ad.py (semantics: {winners_name})",
        ad_md
    ]
    return "\n".join(parts)


# -------------------------
# Unified API for CLI/server
# -------------------------

def generate_unified_report(
    text: str,
    relation: str = "auto",
    use_llm: bool = False,
    llm_mode: str = "augment",
    llm_threshold: float = 0.55,
    jaccard: float = 0.45,
    min_overlap: int = 3,
    target: Optional[str] = None,
    max_pref_cards: int = 4,
    winners_semantics: str = "stable",
    repair_stance: bool = False,
    cqs: bool = False,
    filename: str = "session",
) -> Dict[str, Any]:
    ids, id2text, atoms, attacks, id2atom, atom2id, meta = build_af_from_text(
        text=text,
        relation=relation,
        jaccard=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    sem = compute_semantics(atoms, set(attacks))
    id_att = id_attacks_from_atoms(set(attacks), atom2id)
    atk_by_tag = attacks_by_tag(ids, meta)
    grounded_ids, depth = grounded_fixpoint_depth(ids, id_att)
    cards = preferred_cards(ids, id2text, id2atom, sem, k=max_pref_cards)
    why = why_not_target(target, ids, id2atom, id_att, sem) if target else {}
    # winners (shared graph)
    win_sets = winners(atoms, set(attacks), winners_semantics)
    unified_md = make_unified_markdown(
        filename=filename,
        ids=ids, id2text=id2text, id2atom=id2atom, atom2id=atom2id,
        attacks_tagged=atk_by_tag, id_attacks=id_att,
        sem=sem, depth=depth, pref_cards=cards, why=why,
        winners_sets=win_sets, winners_name=winners_semantics, repair=repair_stance,
        cqs=cqs
    )
    return {
        "markdown": unified_md,
        "af": {
            "ids": ids, "id2text": id2text, "id2atom": id2atom, "atom2id": atom2id,
            "attacks_by_tag": atk_by_tag, "id_attacks": sorted(list(id_att)),
        },
        "semantics": sem,
        "insights": {
            "grounded_ids": sorted(list(grounded_ids)),
            "defense_depth": depth,
            "preferred_cards": cards,
            "why": why,
        },
        "winners": {
            "name": winners_semantics,
            "count": len(win_sets),
            "sets_atoms": [sorted(list(S)) for S in win_sets],
        },
        "ad_available": HAVE_AD,
    }
