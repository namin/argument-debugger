#!/usr/bin/env python3
"""
ad_multilevel.py — capability-driven orchestrator

- Baseline heuristics/LLM edges via nl2apx
- FOL-derived rebuttals from contradictory CONCLUSIONS (ATTACK)
- Lightweight MP entailment; optional Lean verification
- DOT/APX/Argdown exports
- Multi-provenance on edges (collect multiple sources per (from,to)).
- Derive SUPPORT and UNDERMINE relations from FOL:
    * SUPPORT: concl(Ai) matches a premise literal in Aj (same predicate/const/polarity).
    * UNDERMINE: concl(Ai) contradicts a premise literal in Aj (same predicate/const, opposite polarity).
  Both relations include 'witness'. Only ATTACK and (optionally) UNDERMINE are fed to AF semantics.
- Switch to control AF treatment of undermine edges:
    * --af-include-undermine=true (default): treat UNDERMINE as ATTACK in AF.
    * --af-include-undermine=false: exclude UNDERMINE from AF (kept for display only).
- Optional alt-semantics cross-check with apxsolve if available; records agreement/disagreement.
"""

from __future__ import annotations
import argparse, json, re, importlib
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Tuple, Set, DefaultDict
from collections import defaultdict

def _try_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None

nl2apx = _try_import("nl2apx")
af_clingo = _try_import("af_clingo")
ad_mod = _try_import("ad")
scheme_layer = _try_import("scheme_layer")
logical_form = _try_import("logical_form")
lean_bridge = _try_import("lean_bridge")
schemes_io = _try_import("schemes_io")
ad_debate = _try_import("ad_debate")
ad_baseline = _try_import("ad_baseline")
unified_core = _try_import("unified_core")
apxsolve = _try_import("apxsolve")

CAPS = {k: bool(v) for k,v in {
    "nl2apx": nl2apx, "af_clingo": af_clingo, "ad": ad_mod, "scheme_layer": scheme_layer,
    "logical_form": logical_form, "lean_bridge": lean_bridge, "schemes_io": schemes_io,
    "ad_debate": ad_debate, "ad_baseline": ad_baseline, "unified_core": unified_core, "apxsolve": apxsolve
}.items()}

def _dcd(x):
    if is_dataclass(x): return {k: _dcd(v) for k,v in asdict(x).items()}
    if isinstance(x,(list,tuple)): return [_dcd(v) for v in x]
    if isinstance(x,dict): return {k: _dcd(v) for k,v in x.items()}
    return x

def _json(obj: Any, pretty: bool) -> str:
    return json.dumps(obj, indent=(2 if pretty else None), ensure_ascii=False)

def _scope_id(arg_id: str, inner_id: str) -> str:
    inner = (inner_id or "").strip()
    return f"{arg_id}.{inner}" if inner else arg_id

# ---- FOL literal parsing & MP ----
_CONNECTIVES = ("→","↔","∧","∨")
_QUANTS = ("∀","∃")
_PRED_CALL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([A-Za-z0-9_]+)\s*\)\s*$")

def _strip_outer_parens_balanced(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0; ok = True
        for ch in s[1:-1]:
            if ch == "(": depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0: ok = False; break
        if ok and depth == 0: s = s[1:-1].strip()
        else: break
    return s

def _normalize_literal_str(s: str) -> Optional[Tuple[int,str]]:
    if not s: return None
    t = _strip_outer_parens_balanced(s.strip())
    if any(sym in t for sym in _CONNECTIVES) or any(sym in t for sym in _QUANTS):
        return None
    u = t.replace("~","¬").strip()
    if u.lower().startswith("not "): u = "¬" + u[4:].strip()
    if u.startswith("¬"):
        atom = _strip_outer_parens_balanced(u[1:].strip())
        return (-1, atom)
    if "(" in u and u.endswith(")"):
        return (+1, u)
    return None

def _parse_fact_lit(s: str) -> Optional[Tuple[str,str,bool,str]]:
    """Return (pred, const, is_neg, pretty) for 'pred(c)' or '¬pred(c)'; else None."""
    lit = _normalize_literal_str(s)
    if lit is None: return None
    pol, atom = lit
    m = _PRED_CALL.match(atom)
    if not m: return None
    pred, const = m.group(1), m.group(2)
    return (pred, const, pol < 0, f"{'¬' if pol<0 else ''}{pred}({const})")

def _parse_universal_rule(s: str) -> Optional[Tuple[str, List[Tuple[str, bool]]]]:
    if "∀" not in s: return None
    t = s.replace("->","→")
    m = re.match(r"^\s*∀\s*([A-Za-z](?:\s*,\s*[A-Za-z])*)\s*\.?\s*(.*)$", t)
    if not m: return None
    body = _strip_outer_parens_balanced(m.group(2).strip())
    if "→" not in body: return None
    left, right = body.split("→",1)
    left = _strip_outer_parens_balanced(left.strip())
    right = _strip_outer_parens_balanced(right.strip())
    mL = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*[A-Za-z]\s*\)\s*$", left)
    if not mL: return None
    ante_pred = mL.group(1)
    rhs_parts = re.split(r"\s*∧\s*|\s+\band\b\s+", right, flags=re.IGNORECASE)
    rhs_lits: List[Tuple[str,bool]] = []
    for p in rhs_parts:
        p = _strip_outer_parens_balanced(p.strip()).replace("~","¬")
        neg = False
        if p.lower().startswith("not "): p = p[4:].strip(); neg = True
        if p.startswith("¬"): p = p[1:].strip(); neg = True
        mR = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*[A-Za-z]\s*\)\s*$", p)
        if not mR: continue
        rhs_lits.append((mR.group(1), neg))
    return (ante_pred, rhs_lits) if rhs_lits else None

def _is_more_specific(fols: List[str]) -> float:
    s = " ".join(f.lower() for f in fols)
    score = 0.0
    if "penguin(" in s: score += 2.0
    if "canary(" in s: score += 1.5
    if "sparrow(" in s: score += 1.5
    if "∀" in s and ("penguin(" in s or "canary(" in s): score += 0.5
    if "bird(" in s: score -= 0.4
    return score

def _grounded_labeling(grounded_ext: List[str], ids: List[str], edges_idx: List[Tuple[int,int]]) -> Dict[str,str]:
    in_set = set(grounded_ext); out_set: Set[str] = set()
    for (i,j) in edges_idx:
        a,b = ids[i], ids[j]
        if a in in_set: out_set.add(b)
    return {aid: ("in" if aid in in_set else "out" if aid in out_set else "undec") for aid in ids}

def _explain_grounded(ids: List[str], edges_idx: List[Tuple[int,int]], grounded_ext: List[str]) -> Dict[str,str]:
    attackers: Dict[str,List[str]] = {aid: [] for aid in ids}
    for (i,j) in edges_idx: attackers[ids[j]].append(ids[i])
    expl: Dict[str,str] = {}; in_set = set(grounded_ext)
    for aid in ids:
        if aid in in_set:
            expl[aid] = f"{aid} is IN because " + ("all attackers are OUT." if attackers[aid] else "it has no attackers.")
        else:
            expl[aid] = f"{aid} is OUT because it is attacked by {', '.join(attackers[aid])} without accepted defenders." if attackers[aid] else f"{aid} is UNDEC (no attackers accepted)."
    return expl

# ---- Exports ----
def _export_apx(ids: List[str], attacks_idx: List[Tuple[int,int]], path: str):
    if not CAPS["nl2apx"]:
        raise RuntimeError("nl2apx required for APX export")
    lines = []
    for aid in ids:
        atom = nl2apx.sanitize_atom(aid)
        lines.append(f"arg({atom}).")
    for (i,j) in attacks_idx:
        a = nl2apx.sanitize_atom(ids[i]); b = nl2apx.sanitize_atom(ids[j])
        lines.append(f"att({a},{b}).")
    with open(path,"w",encoding="utf-8") as f: f.write("\n".join(lines))

def _export_argdown(ids: List[str], id_to_text: Dict[str,str], path: str):
    lines = ["// Argdown-like export"]
    for aid in ids:
        lines.append(f"\n[Argument {aid}]:")
        for line in id_to_text[aid].splitlines():
            lines.append(f"- {line.strip()}")
    with open(path,"w",encoding="utf-8") as f: f.write("\n".join(lines))

# ---- Orchestrator ----
def analyze(
    raw_text: str,
    relation_mode: str = "auto",
    use_llm_edges: bool = False,
    llm_threshold: float = 0.55,
    llm_mode: str = "augment",
    semantics: List[str] = ("grounded","preferred","stable"),
    cq: bool = False,
    cq_topk: int = 2,
    derive_contradictions: str = "none",  # none|mutual|orient
    derive_support: bool = True,
    derive_undermine: bool = True,
    af_include_undermine: bool = True,
    check_entailment: bool = False,
    explain: bool = False,
    lean_verify: bool = False,
    export_apx: Optional[str] = None,
    export_argdown: Optional[str] = None,
    dot_out: Optional[str] = None,
) -> Dict[str,Any]:

    if not (CAPS["nl2apx"] and CAPS["af_clingo"] and CAPS["ad"] and CAPS["logical_form"]):
        missing = [k for k in ("nl2apx","af_clingo","ad","logical_form") if not CAPS[k]]
        raise RuntimeError(f"Required modules missing: {missing}")

    # 0) Blocks
    blocks: List[str] = nl2apx.parse_blocks_text(raw_text)

    # 1) Baseline AF edges
    ids, id_to_text, edges_idx, meta = nl2apx.build_edges(
        blocks, relation_mode=relation_mode,
        use_llm=use_llm_edges, llm_threshold=llm_threshold, llm_mode=llm_mode
    )
    idx_by_id = {aid: i for i,aid in enumerate(ids)}

    # Keep multi-provenance
    prov_sources: DefaultDict[Tuple[int,int], Set[str]] = defaultdict(set)
    for pair in meta.get("explicit_edges", []): prov_sources[tuple(pair)].add("explicit")
    for pair in meta.get("heuristic_edges", []): prov_sources[tuple(pair)].add("heuristic")
    for pair in meta.get("llm_edges", []): prov_sources[tuple(pair)].add("llm")

    # 2) Argument parsing & FOL
    ArgumentParser = getattr(ad_mod,"ArgumentParser")
    arg_parser = ArgumentParser()
    SchemeAssigner = getattr(scheme_layer,"SchemeAssigner") if CAPS["scheme_layer"] else None
    cq_assigner = SchemeAssigner(topk=cq_topk, temperature=0.0) if (cq and SchemeAssigner) else None
    LogicalAnalyzer = getattr(logical_form,"LogicalAnalyzer")
    logical = LogicalAnalyzer(debug=False)

    arguments_out: Dict[str,Any] = {}
    conclusion_literal_by_arg: Dict[str, Tuple[int,str,str]] = {}
    all_fol_strings_by_arg: Dict[str, List[str]] = {}
    premise_literals_by_arg: Dict[str, List[Tuple[str,str,bool,str]]] = defaultdict(list)

    for aid in ids:
        text_block = id_to_text[aid]
        try:
            parsed = arg_parser.parse_argument(text_block)
        except Exception as e:
            arguments_out[aid] = {"text": text_block, "parse_error": str(e)}
            continue

        # CQ
        if cq_assigner is not None:
            try:
                sfacts = cq_assigner.analyze(parsed, text_block, topk=cq_topk)
                parsed.scheme_requires = sfacts.requires; parsed.scheme_answered = sfacts.answered
            except Exception as e:
                parsed.scheme_requires = []; parsed.scheme_answered = []; parsed.scheme_error = str(e)

        arg_dict = _dcd(parsed)

        # per-claim FOL
        fol_sentences: List[Dict[str,Any]] = []
        all_fols: List[str] = []
        for c in parsed.claims:
            scoped = _scope_id(aid, c.id)
            try:
                fol_arg = logical.extract_logical_form(c.content)
                idx = 0
                for stmt in fol_arg.statements:
                    idx += 1
                    pretty = stmt.formula.to_string()
                    fol_sentences.append({"id": f"{scoped}.s{idx}", "claim_id": c.id, "pretty": pretty})
                    all_fols.append(pretty)
                    # Track premises as literal facts if possible
                    if getattr(c, "type", None) == "premise":
                        fact = _parse_fact_lit(pretty)
                        if fact: premise_literals_by_arg[aid].append(fact)
                # Track conclusion literal from goal claim if possible
                if getattr(c, "id", None) == arg_dict.get("goal_claim"):
                    for s in fol_sentences:
                        if s.get("claim_id") == c.id and "pretty" in s:
                            lit = _normalize_literal_str(s["pretty"])
                            if lit is not None:
                                pol, atom = lit
                                conclusion_literal_by_arg[aid] = (pol, atom, s["pretty"])
                                break
            except Exception as e:
                fol_sentences.append({"id": f"{scoped}", "claim_id": c.id, "error": f"FOL parse failed: {e}"})

        all_fol_strings_by_arg[aid] = list(all_fols)

        # whole-argument analysis
        fol_analysis: Optional[Dict[str,Any]] = None
        try:
            result = logical.analyze(logical.extract_logical_form(text_block))
            fol_analysis = {"issues": result.get("issues", []), "valid_inferences": result.get("valid_inferences", [])}
        except Exception:
            fol_analysis = None

        arguments_out[aid] = {"text": text_block, "argument": arg_dict, "fol": {"sentences": fol_sentences, "analysis": fol_analysis}}

    # 3) Derived relations
    derived_attack_idx: Set[Tuple[int,int]] = set()
    derived_support_idx: Set[Tuple[int,int]] = set()
    derived_undermine_idx: Set[Tuple[int,int]] = set()
    edge_witness: Dict[Tuple[int,int], str] = {}
    edge_types: DefaultDict[Tuple[int,int], Set[str]] = defaultdict(set)

    # 3a) Rebuttals (contradictory conclusions)
    if derive_contradictions in ("mutual","orient") and len(conclusion_literal_by_arg) >= 2:
        pos: Dict[str, List[Tuple[str,str]]] = {}
        neg: Dict[str, List[Tuple[str,str]]] = {}
        for aid,(pol,atom,pretty) in conclusion_literal_by_arg.items():
            (pos if pol>0 else neg).setdefault(atom, []).append((aid, pretty))
        for atom in set(pos.keys()).intersection(neg.keys()):
            for (aid_pos, pretty_pos) in pos[atom]:
                for (aid_neg, pretty_neg) in neg[atom]:
                    if derive_contradictions == "mutual":
                        i,j = idx_by_id[aid_pos], idx_by_id[aid_neg]
                        k,l = idx_by_id[aid_neg], idx_by_id[aid_pos]
                        derived_attack_idx.update({(i,j),(k,l)})
                        edge_witness[(i,j)] = f"rebut: {pretty_pos} vs {pretty_neg}"
                        edge_witness[(k,l)] = f"rebut: {pretty_neg} vs {pretty_pos}"
                        edge_types[(i,j)].add("attack"); edge_types[(k,l)].add("attack")
                        prov_sources[(i,j)].add("derived:rebuttal"); prov_sources[(k,l)].add("derived:rebuttal")
                    else:
                        a_score = _is_more_specific(all_fol_strings_by_arg.get(aid_pos, []))
                        b_score = _is_more_specific(all_fol_strings_by_arg.get(aid_neg, []))
                        if a_score >= b_score:
                            i,j = idx_by_id[aid_pos], idx_by_id[aid_neg]; w = f"rebut: {pretty_pos} vs {pretty_neg}"
                        else:
                            i,j = idx_by_id[aid_neg], idx_by_id[aid_pos]; w = f"rebut: {pretty_neg} vs {pretty_pos}"
                        derived_attack_idx.add((i,j)); edge_witness[(i,j)] = w
                        edge_types[(i,j)].add("attack")
                        prov_sources[(i,j)].add("derived:rebuttal")

    # 3b) SUPPORT / UNDERMINE from premise-conclusion alignment
    if derive_support or derive_undermine:
        for ai in ids:
            concl = conclusion_literal_by_arg.get(ai)
            if not concl: continue
            c_pol, c_atom, c_pretty = concl
            m = _PRED_CALL.match(c_atom)
            if not m: continue
            c_pred, c_const = m.group(1), m.group(2)
            for aj in ids:
                if ai == aj: continue
                for (p_pred, p_const, p_neg, p_pretty) in premise_literals_by_arg.get(aj, []):
                    if p_pred == c_pred and p_const == c_const:
                        i,j = idx_by_id[ai], idx_by_id[aj]
                        if derive_support and (p_neg == (c_pol < 0)) and (ai,aj) not in derived_support_idx:
                            derived_support_idx.add((i,j))
                            edge_witness[(i,j)] = f"support: {c_pretty} → premise({aj}): {p_pretty}"
                            edge_types[(i,j)].add("support")
                            prov_sources[(i,j)].add("derived:support")
                        if derive_undermine and (p_neg != (c_pol < 0)) and (ai,aj) not in derived_undermine_idx:
                            derived_undermine_idx.add((i,j))
                            edge_witness[(i,j)] = f"undermine: {c_pretty} ⟂ premise({aj}): {p_pretty}"
                            edge_types[(i,j)].add("undermine")
                            prov_sources[(i,j)].add("derived:undermine")

    # 4) Merge edges
    base_edges = set(tuple(e) for e in edges_idx)
    final_attack_edges = set(base_edges).union(derived_attack_idx)
    if af_include_undermine:
        final_attack_edges = final_attack_edges.union(derived_undermine_idx)

    # 5) Semantics (ATTACK edges only)
    safe_atoms = nl2apx.make_unique([nl2apx.sanitize_atom(i) for i in ids])
    atom_of: Dict[str,str] = {ids[i]: safe_atoms[i] for i in range(len(ids))}
    atoms_list = [atom_of[i] for i in ids]
    attacks_atoms = [(atom_of[ids[i]], atom_of[ids[j]]) for (i,j) in sorted(final_attack_edges)]
    af_sem: Dict[str,Any] = {}
    def _atoms2ids(fams):
        if isinstance(fams,(set,frozenset)):
            return sorted([aid for aid,atom in atom_of.items() if atom in fams])
        out = []
        for fam in fams:
            out.append(sorted([aid for aid,atom in atom_of.items() if atom in fam]))
        return out
    for sem in semantics:
        s = sem.lower()
        if s == "grounded":   af_sem["grounded"] = _atoms2ids(af_clingo.grounded(atoms_list, attacks_atoms))
        elif s == "preferred":af_sem["preferred"] = _atoms2ids(af_clingo.preferred(atoms_list, attacks_atoms))
        elif s == "stable":   af_sem["stable"] = _atoms2ids(af_clingo.stable(atoms_list, attacks_atoms))
        elif s == "complete": af_sem["complete"] = _atoms2ids(af_clingo.complete(atoms_list, attacks_atoms))
        elif s in ("semi-stable","semistable"): af_sem["semi-stable"] = _atoms2ids(af_clingo.semi_stable(atoms_list, attacks_atoms))
        elif s == "stage":    af_sem["stage"] = _atoms2ids(af_clingo.stage(atoms_list, attacks_atoms))

    # alt-semantics cross-check
    semantics_alt: Dict[str,Any] = {}
    semantics_agree: Dict[str, Optional[bool]] = {}
    if CAPS["apxsolve"]:
        try:
            for sem in semantics:
                fn = getattr(apxsolve, sem.lower(), None)
                if callable(fn):
                    alt = fn(atoms_list, attacks_atoms)
                    semantics_alt[sem.lower()] = _atoms2ids(alt)
                    semantics_agree[sem.lower()] = (semantics_alt[sem.lower()] == af_sem.get(sem.lower()))
        except Exception as e:
            semantics_alt["error"] = str(e)

    # 6) DOT export
    exports: Dict[str,Any] = {}
    if dot_out:
        try:
            af_clingo.export_dot(atoms_list, attacks_atoms, dot_out)
            exports["dot_path"] = dot_out
        except Exception as e:
            exports["dot_error"] = str(e)

    # 7) Entailment (MP) + optional Lean verify
    # (reuse already-parsed arguments_out)
    if check_entailment or lean_verify:
        for aid, bundle in arguments_out.items():
            arg = bundle.get("argument", {})
            goal_id = arg.get("goal_claim")
            if not goal_id: continue
            prem_fols: List[str] = []
            concl_fols: List[str] = []
            for s in bundle["fol"]["sentences"]:
                if s.get("claim_id") == goal_id and "pretty" in s: concl_fols.append(s["pretty"])
                elif "pretty" in s: prem_fols.append(s["pretty"])

            facts: List[Tuple[str,str,bool]] = []
            rules: List[Tuple[str, List[Tuple[str,bool]]]] = []
            for f in prem_fols:
                fact = _parse_fact_lit(f)
                if fact: facts.append(fact[:3])
                else:
                    rule = _parse_universal_rule(f)
                    if rule: rules.append(rule)

            valid: List[Dict[str,Any]] = []
            for cf in concl_fols:
                c_fact = _parse_fact_lit(cf)
                if not c_fact: continue
                c_pred, c_const, c_neg, _ = c_fact
                found = False
                for (ante_pred, rhs_lits) in rules:
                    consts = [const for (pred,const,isneg) in facts if pred==ante_pred and not isneg]
                    for const in consts:
                        for (rhs_pred, rhs_neg) in rhs_lits:
                            if rhs_pred==c_pred and rhs_neg==c_neg and const==c_const:
                                valid.append({"rule":"modus_ponens","via":f"∀x({ante_pred}(x) → ...{('¬' if rhs_neg else '')}{rhs_pred}(x)) + {ante_pred}({const}) ⊢ {('¬' if c_neg else '')}{c_pred}({const})"})
                                found = True; break
                        if found: break
                    if found: break
                # Lean verify (best-effort)
                if lean_verify and CAPS["lean_bridge"]:
                    try:
                        verified = None
                        for cand in ("verify","prove","check","entails"):
                            fn = getattr(lean_bridge, cand, None)
                            if callable(fn):
                                try:
                                    ok = fn(prem_fols, cf)
                                    verified = bool(ok); break
                                except TypeError:
                                    try:
                                        ok = fn(prem_fols, cf, 5)
                                        verified = bool(ok); break
                                    except Exception:
                                        pass
                        if verified is not None:
                            valid.append({"rule":"lean","via":"lean_bridge","lean_verified": bool(verified)})
                    except Exception:
                        pass
            if "analysis" not in bundle["fol"] or bundle["fol"]["analysis"] is None:
                bundle["fol"]["analysis"] = {"issues": [], "valid_inferences": valid}
            else:
                bundle["fol"]["analysis"]["valid_inferences"] = bundle["fol"]["analysis"].get("valid_inferences", []) + valid

    # 8) Provenance & edges JSON (with multi-provenance & typed edges)
    base_edge_set = set(tuple(e) for e in edges_idx)
    # Tag base edges with 'attack' type by default
    for pair in base_edge_set:
        edge_types[pair].add("attack")

    def _edge_json_list():
        items: List[Dict[str,Any]] = []
        seen: Set[Tuple[int,int]] = set()
        # include all base + derived sets (support & undermine included for display)
        union_all = base_edge_set.union(derived_attack_idx).union(derived_support_idx).union(derived_undermine_idx)
        for (i,j) in sorted(union_all):
            e = {"from": ids[i], "to": ids[j], "types": sorted(list(edge_types.get((i,j), {"attack"})))}
            srcs = sorted(list(prov_sources.get((i,j), set())))
            if (i,j) in edge_witness:
                e["witness"] = edge_witness[(i,j)]
            if srcs:
                e["provenance_sources"] = srcs
            # legacy 'type' and 'provenance' for backwards-compat
            e["type"] = "attack" if "attack" in e["types"] else e["types"][0]
            if srcs:
                e["provenance"] = ",".join(srcs)
            items.append(e)
            seen.add((i,j))
        return items

    edges_json = _edge_json_list()

    # 9) Grounded labeling + explanation (based on ATTACK edges actually used)
    labeling: Optional[Dict[str,str]] = None
    explanations: Optional[Dict[str,str]] = None
    if "grounded" in af_sem:
        g = af_sem["grounded"]
        if isinstance(g, list):
            labeling = _grounded_labeling(g, ids, sorted(final_attack_edges))
            if explain:
                explanations = _explain_grounded(ids, sorted(final_attack_edges), g)

    # 10) Optional exports
    if export_apx:
        try:
            _export_apx(ids, sorted(final_attack_edges), export_apx)
        except Exception as e:
            exports["apx_error"] = str(e)
        else:
            exports["apx_path"] = export_apx
    if export_argdown:
        try:
            _export_argdown(ids, id_to_text, export_argdown)
        except Exception as e:
            exports["argdown_error"] = str(e)
        else:
            exports["argdown_path"] = export_argdown

    # 11) Assemble IR
    ir = {
        "doc_id": "doc:auto",
        "text": raw_text,
        "af": {
            "nodes": ids,
            "node_text": {aid: id_to_text[aid] for aid in ids},
            "edges": edges_json,
            "semantics": af_sem,
            "semantics_alt": semantics_alt if semantics_alt else None,
            "semantics_agree": semantics_agree if semantics_agree else None,
            "provenance": {
                "explicit_edges": meta.get("explicit_edges", []),
                "heuristic_edges": meta.get("heuristic_edges", []),
                "llm_edges": meta.get("llm_edges", []),
                "derived_rebuttals": sorted(list(derived_attack_idx)),
                "derived_support": sorted(list(derived_support_idx)),
                "derived_undermine": sorted(list(derived_undermine_idx)),
                "final_attack_edges": sorted(list(final_attack_edges)),
                "capabilities": CAPS,
            },
            "labeling_grounded": labeling,
            "explanations": explanations,
        },
        "arguments": arguments_out,
        "exports": exports,
    }
    return ir

def main():
    ap = argparse.ArgumentParser(description="Integrated v2: AF ↔ argument ↔ FOL with multi-provenance and derived support/undermine.")
    ap.add_argument("file", nargs="?", default="examples/examples.txt", help="Input file with blank-line-separated arguments.")
    ap.add_argument("-o","--out", default=None, help="Write JSON IR to this path.")
    ap.add_argument("--no-pretty", action="store_true", help="Disable pretty JSON.")

    # AF baseline
    ap.add_argument("--relation", default="auto", choices=["auto","explicit","none"])
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--llm-threshold", type=float, default=0.55)
    ap.add_argument("--llm-mode", default="augment", choices=["augment","override"])

    # Semantics
    ap.add_argument("--sem", action="append",
        choices=["grounded","preferred","stable","complete","stage","semi-stable","semistable"],
        help="Semantics to compute (repeatable). Default: grounded, preferred, stable.")
    ap.add_argument("--dot", dest="dot_out", default=None)

    # CQ
    ap.add_argument("--cq", default=False, action=argparse.BooleanOptionalAction)
    ap.add_argument("--cq-topk", type=int, default=2)

    # Derived relations
    ap.add_argument("--derive-contradictions", default="none", choices=["none","mutual","orient"])
    ap.add_argument("--derive-support", default=True, type=lambda s: s.lower() not in ("0","false","no"))
    ap.add_argument("--derive-undermine", default=True, type=lambda s: s.lower() not in ("0","false","no"))
    ap.add_argument("--af-include-undermine", default=True, type=lambda s: s.lower() not in ("0","false","no"))

    # Logic
    ap.add_argument("--check-entailment", action="store_true")
    ap.add_argument("--lean-verify", action="store_true")
    ap.add_argument("--explain", action="store_true")

    # Exports
    ap.add_argument("--export-apx", default=None)
    ap.add_argument("--export-argdown", default=None)

    args = ap.parse_args()

    try:
        with open(args.file,"r",encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        print(f"Error: file '{args.file}' not found."); return

    sems = args.sem if args.sem else ["grounded","preferred","stable"]

    ir = analyze(
        raw_text=raw,
        relation_mode=args.relation,
        use_llm_edges=args.use_llm,
        llm_threshold=args.llm_threshold,
        llm_mode=args.llm_mode,
        semantics=sems,
        cq=args.cq,
        cq_topk=args.cq_topk,
        derive_contradictions=args.derive_contradictions,
        derive_support=args.derive_support,
        derive_undermine=args.derive_undermine,
        af_include_undermine=args.af_include_undermine,
        check_entailment=args.check_entailment,
        explain=args.explain,
        lean_verify=args.lean_verify,
        export_apx=args.export_apx,
        export_argdown=args.export_argdown,
        dot_out=args.dot_out,
    )

    out_json = _json(ir, pretty=not args.no_pretty)
    if args.out:
        with open(args.out,"w",encoding="utf-8") as f: f.write(out_json)
    else:
        print(out_json)

if __name__ == "__main__":
    main()
