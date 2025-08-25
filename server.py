#!/usr/bin/env python3
"""
server.py — FastAPI backend for Argumentation Semantics Playground

Endpoints:
  POST /api/run      — extract AF + compute semantics; returns JSON + markdown + APX/DOT strings
  POST /api/repair   — plan/generate/verify preferred-credulous (add-nodes-only); returns BEFORE/AFTER JSON and augmented text

Assumes you have the toolkit modules alongside this server:
  - nl2apx.py
  - af_clingo.py
  - (optional) argsem.py (some helper functions are reused if available)

Run:
  pip install fastapi uvicorn pydantic clingo
  uvicorn server:app --reload --port 8000
"""
from __future__ import annotations

import os
import json
from typing import List, Dict, Tuple, Set, Optional, Any
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from server_winners_router import router as winners_router

# Try to import toolkit modules (must be present)
try:
    import nl2apx
    import af_clingo
    from llm import set_request_api_key, LLMConfigurationError
except Exception as e:
    raise RuntimeError("This backend requires nl2apx.py and af_clingo.py in the same folder.") from e

# Optional: use argsem helpers if available
_HAVE_ARGSEM = False
try:
    import argsem as AS
    _HAVE_ARGSEM = True
except Exception:
    _HAVE_ARGSEM = False

# ---------------- Utility (shared with argsem) ----------------
def _make_mappings(ids: List[str]) -> Tuple[List[str], Dict[str,str], Dict[str,str]]:
    atoms = nl2apx.make_unique([nl2apx.sanitize_atom(i) for i in ids])
    id2atom = {ids[i]: atoms[i] for i in range(len(ids))}
    atom2id = {v: k for k, v in id2atom.items()}
    return atoms, id2atom, atom2id

def build_af_from_text(text: str,
                       relation: str = "auto",
                       jaccard: float = 0.45,
                       min_overlap: int = 3,
                       use_llm: bool = False,
                       llm_threshold: float = 0.55,
                       llm_mode: str = "augment"):
    blocks = nl2apx.parse_blocks_text(text)
    ids, id_to_text, idx_edges, meta = nl2apx.build_edges(
        blocks,
        relation_mode=relation,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    atoms, id2atom, atom2id = _make_mappings(ids)
    attacks = set((atoms[i], atoms[j]) for (i,j) in idx_edges)
    return ids, id_to_text, atoms, id2atom, atom2id, attacks, meta

def export_dot_string(atoms: List[str], attacks: Set[Tuple[str,str]], atom2id: Dict[str,str]) -> str:
    lines = ["digraph AF {", '  rankdir=LR;', '  node [shape=box, style="rounded,filled", fillcolor="#f8f9fb"];']
    for a in atoms:
        label = atom2id.get(a, a)
        lines.append(f'  "{a}" [label="{label}\\n({a})"];')
    for (u,v) in sorted(attacks):
        lines.append(f'  "{u}" -> "{v}" [color="#555"];')
    lines.append("}")
    return "\n".join(lines)

def idx_edges_from_attacks(ids: List[str], atom2id: Dict[str,str], attacks: Set[Tuple[str,str]]):
    idx_map = {ids[i]: i for i in range(len(ids))}
    idx_edges = set()
    for (u,v) in attacks:
        uid = atom2id.get(u, u)  # actually maps atom->id
        vid = atom2id.get(v, v)
        if uid in idx_map and vid in idx_map:
            idx_edges.add((idx_map[uid], idx_map[vid]))
    return idx_edges

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

def defense_depth(atoms: List[str], attacks: Set[Tuple[str,str]]):
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

def extraction_summary(meta: Dict[str, Any], attacks: Set[Tuple[str,str]]):
    exp = len(meta.get("explicit_edges") or [])
    heu = len(meta.get("heuristic_edges") or [])
    llm = len(meta.get("llm_edges") or [])
    return {
        "explicit": exp,
        "heuristic": heu,
        "llm": llm,
        "total_edges": len(attacks),
        "auto_note": meta.get("auto_note")
    }

def translate_set(S: frozenset, atom2id: Dict[str,str]) -> List[str]:
    return sorted([atom2id.get(a, a) for a in S])

# ---------------- Middleware ----------------
class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle request-scoped API keys via X-Gemini-API-Key header."""
    
    async def dispatch(self, request: Request, call_next):
        # Extract API key from header
        api_key = request.headers.get("X-Gemini-API-Key")
        if api_key:
            set_request_api_key(api_key)
        
        response = await call_next(request)
        return response

# ---------------- API models ----------------
class RunRequest(BaseModel):
    text: str = Field(..., description="Full arguments.txt content (blocks separated by blank lines)")
    relation: str = Field("auto", description="auto | explicit | none")
    jaccard: float = 0.45
    min_overlap: int = 3
    use_llm: bool = False
    llm_threshold: float = 0.55
    llm_mode: str = "augment"  # augment | override
    sem: str = "all"           # which semantics set to return in 'semantics' key
    target: Optional[str] = None
    max_pref_cards: int = 4
    want_markdown: bool = True

class RepairRequest(RunRequest):
    repair: bool = True
    k: int = 1
    fanout: int = 0
    new_prefix: str = "R"
    llm_generate: bool = False
    force: bool = False
    min_coverage: Optional[float] = None
    verify_relation: str = "explicit"  # "explicit" or "same"

# ---------------- App ----------------
app = FastAPI(title="AS Playground API", version="0.1.0")
app.add_middleware(APIKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(winners_router, prefix="/api/ad")

# ---------------- Core handlers ----------------
@app.post("/api/run")
def api_run(req: RunRequest):
    try:
        ids, id2text, atoms, id2atom, atom2id, attacks, meta = build_af_from_text(
            req.text, relation=req.relation,
            jaccard=req.jaccard, min_overlap=req.min_overlap,
            use_llm=req.use_llm, llm_threshold=req.llm_threshold, llm_mode=req.llm_mode
        )
    except (LLMConfigurationError, RuntimeError) as e:
        if req.use_llm:
            raise HTTPException(400, f"LLM requested but not available: {str(e)}")
        else:
            # This shouldn't happen if use_llm=False, but handle gracefully
            raise HTTPException(500, f"Unexpected LLM error: {str(e)}")

    # Semantics
    G  = af_clingo.grounded(atoms, attacks)
    PR = af_clingo.preferred(atoms, attacks)
    ST = af_clingo.stable(atoms, attacks)
    CO = af_clingo.complete(atoms, attacks)
    SG = af_clingo.stage(atoms, attacks)
    SS = af_clingo.semi_stable(atoms, attacks)

    depth = defense_depth(atoms, attacks)

    # Nodes
    def in_many(fams, a): return f"{sum(1 for S in fams if a in S)}/{len(fams) or 0}"
    nodes = []
    for a in atoms:
        _id = atom2id.get(a, a)
        nodes.append({
            "id": _id, "atom": a, "text": id2text.get(_id, ""),
            "depth": depth[a],
            "grounded": (a in G),
            "preferred": in_many(PR, a),
            "stable": in_many(ST, a),
            "complete": in_many(CO, a),
            "stage": in_many(SG, a),
            "semistable": in_many(SS, a),
        })

    # Edges
    idx_map = {ids[i]: i for i in range(len(ids))}
    prov_idx = {}
    def add(lst, tag):
        for e in lst or []:
            prov_idx.setdefault(tuple(e), []).append(tag)
    add(meta.get("explicit_edges"), "exp")
    add(meta.get("heuristic_edges"), "heu")
    add(meta.get("llm_edges"), "llm")

    edges = []
    for (u,v) in sorted(attacks):
        uid, vid = atom2id[u], atom2id[v]
        ui, vi = idx_map.get(uid), idx_map.get(vid)
        tags = prov_idx.get((ui,vi), []) if (ui is not None and vi is not None) else []
        edges.append({"source": uid, "target": vid, "provenance": tags, "sourceAtom": u, "targetAtom": v})

    # Preferred stance cards
    cards = []
    for i, S in enumerate(PR[: req.max_pref_cards], 1):
        ids_in = [atom2id[a] for a in sorted(S)]
        preview = "; ".join(id2text.get(_id, "")[:60].replace("\n"," ") for _id in ids_in[:3])
        cards.append({"name": f"S{i}", "members": ids_in, "preview": preview})

    # Dot & APX
    dot = export_dot_string(atoms, attacks, atom2id)
    idx_edges = idx_edges_from_attacks(ids, atom2id, attacks)
    apx = nl2apx.emit_apx(ids, id2text, idx_edges, provenance=meta)

    # Why-not insights for target (optional)
    tgt_id = req.target if (req.target in ids) else (ids[0] if (req.target is None and ids) else None)
    tgt_atom = id2atom.get(tgt_id) if tgt_id else None

    def grounded_roadblocks(target_atom: Optional[str]):
        if not target_atom: return []
        Gs = set(G)
        if target_atom in Gs: return []
        atk = {a:set() for a in atoms}
        for (u,v) in attacks:
            atk[v].add(u)
        return sorted([atom2id[b] for b in atk.get(target_atom, set())
                       if not any((c,b) in attacks for c in Gs)])

    def preferred_persistent_soft(target_atom: Optional[str]):
        if not target_atom: return [], []
        if not PR: return [], []
        inter = set(atoms); union = set()
        for S in PR:
            inter &= set(S); union |= set(S)
        atk = {a:set() for a in atoms}
        for (u,v) in attacks:
            atk[v].add(u)
        A = atk.get(target_atom, set())
        persistent = sorted([atom2id[a] for a in (inter & A)])
        soft = sorted([atom2id[a] for a in ((union - inter) & A)])
        return persistent, soft

    rb = grounded_roadblocks(tgt_atom)
    pers, soft = preferred_persistent_soft(tgt_atom)

    # Markdown: reuse argsem if available
    markdown = ""
    if req.want_markdown and _HAVE_ARGSEM:
        try:
            markdown = AS.markdown_report("(from-POST)", ids, id2text, atoms, id2atom, atom2id, attacks, meta,
                                          target_id=tgt_id, stance_limit=req.max_pref_cards, llm_summarize=False)
        except Exception as e:
            markdown = f"(markdown unavailable: {e})"

    # Choose semantics family to return compactly
    def tr_family(fams):
        return [sorted([atom2id[a] for a in S]) for S in fams]

    if req.sem == "all":
        semantics = {
            "grounded": sorted([atom2id[a] for a in G]),
            "preferred": tr_family(PR),
            "stable": tr_family(ST),
            "complete": tr_family(CO),
            "stage": tr_family(SG),
            "semi-stable": tr_family(SS),
        }
    else:
        fam = {
            "grounded": [G],
            "preferred": PR,
            "stable": ST,
            "complete": CO,
            "stage": SG,
            "semi-stable": SS
        }.get(req.sem, PR)
        semantics = tr_family(fam)

    return {
        "nodes": nodes,
        "edges": edges,
        "semantics": semantics,
        "preferred_cards": cards,
        "dot": dot,
        "apx": apx,
        "insights": {
            "target": {"id": tgt_id, "atom": tgt_atom},
            "grounded_roadblocks": rb,
            "preferred_attackers": {"persistent": pers, "soft": soft},
            "extraction": extraction_summary(meta, attacks),
        },
        "markdown": markdown,
    }

# ----- Repair helpers (subset of argsem logic) -----
def attackers_of(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> List[str]:
    return sorted({u for (u,v) in attacks if v == target_atom})

def preferred_accepts(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> bool:
    prefs = af_clingo.preferred(atoms, attacks)
    return any(target_atom in S for S in prefs)

def preferred_coverage(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str):
    prefs = af_clingo.preferred(atoms, attacks)
    n = len(prefs)
    if n == 0: return (0, 0, 0.0)
    k = sum(1 for S in prefs if target_atom in S)
    return (k, n, k/n if n>0 else 0.0)

def preferred_attacker_frequencies(atoms: List[str], attacks: Set[Tuple[str,str]], target_atom: str) -> Dict[str,int]:
    prefs = af_clingo.preferred(atoms, attacks); counts = {a:0 for a in atoms}
    for S in prefs:
        for a in S: counts[a]+=1
    return {b: counts.get(b,0) for b in attackers_of(atoms, attacks, target_atom)}

def group_blockers(blockers: List[str], k: int, fanout: int) -> List[List[str]]:
    if not blockers or k <= 0: return []
    if fanout <= 0: return [blockers[:]] if k >= 1 else []
    if fanout == 1: return [[b] for b in blockers[:k]]
    gcount = min(k, max(1, (len(blockers)+fanout-1)//fanout))
    groups = [[] for _ in range(gcount)]
    i = 0
    for b in blockers:
        groups[i % gcount].append(b); i += 1
    return groups

def next_new_ids(existing_ids: List[str], n: int, prefix: str = "R") -> List[str]:
    base=1; used=set(existing_ids); out=[]
    while len(out)<n:
        cand=f"{prefix}{base}"
        if cand not in used:
            out.append(cand); used.add(cand)
        base += 1
    return out

def _defender_template(gids: List[str], id2text: Dict[str,str]) -> str:
    return ("This claim relies on a contested assumption and overlooks countervailing evidence that limits its conclusion in this context."
            if len(gids)==1 else
            "These claims share a contested assumption and ignore limiting conditions; taken together, they overstate their conclusion in this context.")

def build_new_blocks(new_ids: List[str], groups_ids: List[List[str]], id_to_text: Dict[str,str],
                     use_llm_text: bool = False) -> List[str]:
    # For now: deterministic text (LLM text optional to add later)
    blocks = []
    for nid, gids in zip(new_ids, groups_ids):
        body = _defender_template(gids, id_to_text)
        blocks.append(f"ID: {nid}\nATTACKS: {', '.join(gids)}\n{body}\n")
    return blocks

def verify_after_text(original_text: str, new_blocks: List[str], verify_relation: str = "explicit"):
    augmented = original_text.strip() + "\n\n" + ("\n\n".join([b.strip() for b in new_blocks])) + "\n"
    ids2, id2text2, atoms2, id2atom2, atom2id2, attacks2, meta2 = build_af_from_text(
        augmented, relation=verify_relation, use_llm=False
    )
    return augmented, (ids2, id2text2, atoms2, id2atom2, atom2id2, attacks2, meta2)

@app.post("/api/repair")
def api_repair(req: RepairRequest):
    # 1) Baseline AF
    try:
        ids, id2text, atoms, id2atom, atom2id, attacks, meta = build_af_from_text(
            req.text, relation=req.relation,
            jaccard=req.jaccard, min_overlap=req.min_overlap,
            use_llm=req.use_llm, llm_threshold=req.llm_threshold, llm_mode=req.llm_mode
        )
    except (LLMConfigurationError, RuntimeError) as e:
        if req.use_llm:
            raise HTTPException(400, f"LLM requested but not available: {str(e)}")
        else:
            # This shouldn't happen if use_llm=False, but handle gracefully
            raise HTTPException(500, f"Unexpected LLM error: {str(e)}")
    if req.target not in ids:
        raise HTTPException(400, f"Target {req.target!r} not found. Known: {ids}")
    t_atom = id2atom[req.target]

    cred_before = preferred_accepts(atoms, attacks, t_atom)
    k_in, n_pf, cov_before = preferred_coverage(atoms, attacks, t_atom)

    # Early exit
    goal_ok = cred_before and (req.min_coverage is None or cov_before >= req.min_coverage)
    if goal_ok and not req.force:
        # Still return baseline result
        run_payload = api_run(RunRequest(**req.model_dump()))
        run_payload["repair"] = {"skipped": True, "reason": "goal already satisfied"}
        return run_payload

    # 2) Plan
    direct_blockers = attackers_of(atoms, attacks, t_atom)
    freqs = preferred_attacker_frequencies(atoms, attacks, t_atom)
    direct_blockers_sorted = sorted(direct_blockers, key=lambda b: (-freqs.get(b,0), b))
    blocker_ids = [atom2id[b] for b in direct_blockers_sorted]

    # 3) Group & new IDs
    groups_ids = group_blockers(blocker_ids, k=max(1,req.k), fanout=req.fanout)
    new_ids = next_new_ids(ids, len(groups_ids), prefix=req.new_prefix)

    # 4) Generate new blocks
    new_blocks = build_new_blocks(new_ids, groups_ids, id2text, use_llm_text=req.llm_generate)

    # 5) Verify on augmented text
    try:
        augmented_text, after_tuple = verify_after_text(req.text, new_blocks, verify_relation=req.verify_relation)
    except (LLMConfigurationError, RuntimeError) as e:
        # verify_after_text uses use_llm=False, so this shouldn't happen, but handle gracefully
        raise HTTPException(500, f"Unexpected LLM error during verification: {str(e)}")
    ids2, id2text2, atoms2, id2atom2, atom2id2, attacks2, meta2 = after_tuple

    t_atom2 = id2atom2.get(req.target)
    cred_after = preferred_accepts(atoms2, attacks2, t_atom2) if t_atom2 else False
    k_out, n_out, cov_after = preferred_coverage(atoms2, attacks2, t_atom2) if t_atom2 else (0,0,0.0)

    # Build quick AFTER summary and dot/apx
    dot_after = export_dot_string(atoms2, attacks2, atom2id2)
    idx_edges2 = idx_edges_from_attacks(ids2, atom2id2, attacks2)
    apx_after = nl2apx.emit_apx(ids2, id2text2, idx_edges2, provenance=meta2)

    before_md = ""
    after_md = ""
    integrated_md = ""
    if _HAVE_ARGSEM:
        try:
            before_md = AS.markdown_report("(before)", ids, id2text, atoms, id2atom, atom2id, attacks, meta,
                                        target_id=req.target, stance_limit=req.max_pref_cards if hasattr(req, "max_pref_cards") else 4, llm_summarize=False)
            after_md  = AS.markdown_report("(after)",  ids2, id2text2, atoms2, id2atom2, atom2id2, attacks2, meta2,
                                        target_id=req.target, stance_limit=req.max_pref_cards if hasattr(req, "max_pref_cards") else 4, llm_summarize=False)
            # Light integrated header
            pc = {"k": k_out, "n": n_out, "frac": cov_after}
            integrated_md = (
                f"# Integrated Repair Report — target {req.target}\n\n"
                f"- Preferred credulous before? **{'YES' if cred_before else 'NO'}**\n"
                f"- Preferred coverage before: **{k_in}/{n_pf} ≈ {cov_before:.2f}**\n"
                f"- Direct blockers: {', '.join(blocker_ids) if blocker_ids else '(none)'}\n"
                f"- Groups → new nodes: " + "; ".join(f"{nid}→({', '.join(gids)})" for nid, gids in zip(new_ids, groups_ids)) + "\n\n"
                "## New claims\n" + "\n\n".join(new_blocks) + "\n\n"
                "## Verification\n"
                f"- Preferred credulous after? **{'YES' if cred_after else 'NO'}**\n"
                f"- Preferred coverage after: **{pc['k']}/{pc['n']} ≈ {pc['frac']:.2f}**\n\n"
                "----\n\n## BEFORE\n\n" + before_md + "\n----\n\n## AFTER\n\n" + after_md
            )
        except Exception as e:
            integrated_md = f"(integrated markdown unavailable: {e})"

    # Return integrated payload
    return {
        "before": api_run(RunRequest(**{**req.model_dump(), "want_markdown": True, "repair": False})),
        "new_claims": new_blocks,
        "after": {
            "nodes": [
                {
                    "id": atom2id2[a],
                    "atom": a,
                    "text": id2text2.get(atom2id2[a], ""),
                } for a in atoms2
            ],
            "edges": [
                {"source": atom2id2[u], "target": atom2id2[v]} for (u,v) in sorted(attacks2)
            ],
            "dot": dot_after,
            "apx": apx_after,
            "insights": {
                "preferred_credulous": bool(cred_after),
                "preferred_coverage": {"k": k_out, "n": n_out, "frac": cov_after},
                "extraction": extraction_summary(meta2, attacks2),
            },
        },
        "augmented_text": augmented_text,
        "plan": {
            "target": req.target,
            "blockers": blocker_ids,
            "groups": [{"new_id": nid, "attacks": gids} for nid, gids in zip(new_ids, groups_ids)],
        },
        "markdown": { "before": before_md, "after": after_md, "integrated": integrated_md }
    }

# Health check
@app.get("/api/health")
def health():
    return {"ok": True}
