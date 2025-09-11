#!/usr/bin/env python3
"""
ad_multilevel.py — End-to-end, multi-level semantic parsing for argument-debugger,
with optional FOL-derived rebuttal edges, lightweight entailment checks, and explanations.

Keeps everything in *one file* and delegates heavy lifting to existing modules:
- Blocks/AF edge heuristics (+ optional LLM): nl2apx.{parse_blocks_text, build_edges}
- AF semantics (Dung): af_clingo.{grounded,preferred,stable,complete,stage,semi_stable,export_dot}
- Argument parsing (claims/inferences): ad.ArgumentParser
- Schemes/CQs (optional): scheme_layer.SchemeAssigner
- NL→FOL per-claim: logical_form.LogicalAnalyzer

New features in this file:
- FOL-derived *rebuttal* attacks from contradictory conclusions (flies(tweety) vs ¬flies(tweety))
  via --derive-contradictions {none,mutual,orient}. 'orient' tries to prefer more specific arguments.
- Lightweight entailment checking to populate "valid_inferences" (recognizes simple Modus Ponens).
- Grounded labeling and natural-language explanations of why nodes are in/out/undec.

Examples:
  python ad_multilevel.py examples/ml_arguments.txt --sem grounded --sem preferred
  python ad_multilevel.py examples/ml_arguments.txt --derive-contradictions mutual --check-entailment --explain
  python ad_multilevel.py examples/ml_arguments.txt --derive-contradictions orient --check-entailment --explain
"""

from __future__ import annotations
import argparse
import json
import re
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Tuple, Set

# --- Delegations to existing project modules (no new dependencies) ---
from nl2apx import parse_blocks_text, build_edges, sanitize_atom, make_unique
import af_clingo  # grounded(), preferred(), stable(), export_dot(), ...
from ad import ArgumentParser
try:
    from scheme_layer import SchemeAssigner  # optional
except Exception:
    SchemeAssigner = None  # type: ignore
from logical_form import LogicalAnalyzer

# -------------------------- Utilities -----------------------------------------

def _dataclass_to_dict(x):
    if is_dataclass(x):
        return {k: _dataclass_to_dict(v) for k, v in asdict(x).items()}
    if isinstance(x, (list, tuple)):
        return [_dataclass_to_dict(v) for v in x]
    if isinstance(x, dict):
        return {k: _dataclass_to_dict(v) for k, v in x.items()}
    return x

def _json(obj: Any, pretty: bool) -> str:
    return json.dumps(obj, indent=(2 if pretty else None), ensure_ascii=False)

def _scope_id(arg_id: str, inner_id: str) -> str:
    inner = (inner_id or "").strip()
    return f"{arg_id}.{inner}" if inner else arg_id

# Very light pretty->literal parser (strings only). Returns (polarity, atom) or None.
# Accepts literals like "flies(tweety)" or "¬flies(tweety)".
# Rejects complex forms containing quantifiers/connectives.
_CONNECTIVES = ("→", "↔", "∧", "∨")
_QUANTS = ("∀", "∃")

def _normalize_literal_str(s: str) -> Optional[Tuple[int, str]]:
    if not s:
        return None
    t = s.strip()
    # remove outer whitespace and paired parentheses if they enclose the whole string
    def _strip_parens(u: str) -> str:
        u = u.strip()
        if u.startswith("(") and u.endswith(")"):
            # strip repeatedly for nested
            while u.startswith("(") and u.endswith(")"):
                # ensure parentheses match; naive but safe here
                u = u[1:-1].strip()
        return u
    t = _strip_parens(t)
    # quick reject if obviously complex
    if any(sym in t for sym in _CONNECTIVES) or any(sym in t for sym in _QUANTS):
        return None
    # normalize negation markers
    u = t.replace("~", "¬").strip()
    if u.lower().startswith("not "):
        u = "¬" + u[4:].strip()
    if u.startswith("¬"):
        atom = _strip_parens(u[1:].strip())
        return (-1, atom)
    # must look like predicate(args)
    if "(" in u and u.endswith(")"):
        return (+1, u)
    return None

# Extract predicate name and single constant (very naive but fine for Tweety-like demos)
_PRED_CALL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([A-Za-z0-9_]+)\s*\)\s*$")

def _parse_fact_lit(s: str) -> Optional[Tuple[str, str, bool]]:
    """Return (pred, const, is_neg) for 'pred(const)' or '¬pred(const)'; else None."""
    lit = _normalize_literal_str(s)
    if lit is None:
        return None
    pol, atom = lit
    m = _PRED_CALL.match(atom)
    if not m:
        return None
    pred, const = m.group(1), m.group(2)
    return (pred, const, pol < 0)

# Parse a universal rule ∀x(P(x) → RHS). Returns (ante_pred, [rhs_literals]),
# with rhs_literals entries like ('flies', neg=False) or ('flies', neg=True).
_RULE_ARROW = "→"

def _strip_outer_parens_balanced(s: str) -> str:
    """Strip one or more layers of outer parentheses when they enclose the whole string."""
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        ok = True
        for ch in s[1:-1]:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    ok = False
                    break
        if ok and depth == 0:
            s = s[1:-1].strip()
        else:
            break
    return s

def _parse_universal_rule(s: str) -> Optional[Tuple[str, List[Tuple[str, bool]]]]:
    """
    Accepts forms like:
      ∀x((P(x) → Q(x)))
      ∀x(P(x) → (Q(x) ∧ ¬R(x)))
      ∀x. (P(x) -> Q(x))        # ASCII arrow supported
    Returns: (antecedent_pred, [(rhs_pred, rhs_neg), ...])
    """
    if "∀" not in s:
        return None
    t = s.replace("->", "→")  # support ASCII arrow
    # Split off the quantifier and variable list: '∀x', '∀x.', '∀ x,y .', etc.
    m = re.match(r"^\s*∀\s*([A-Za-z](?:\s*,\s*[A-Za-z])*)\s*\.?\s*(.*)$", t)
    if not m:
        return None
    body = m.group(2).strip()
    body = _strip_outer_parens_balanced(body)  # handle ((...))
    if "→" not in body:
        return None
    left, right = body.split("→", 1)
    left = _strip_outer_parens_balanced(left.strip())
    right = _strip_outer_parens_balanced(right.strip())

    # Antecedent must look like Pred(x)
    mL = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*[A-Za-z]\s*\)\s*$", left)
    if not mL:
        return None
    ante_pred = mL.group(1)

    # RHS: split on ∧ or textual 'and'
    rhs_parts = re.split(r"\s*∧\s*|\s+\band\b\s+", right, flags=re.IGNORECASE)
    rhs_lits: List[Tuple[str, bool]] = []
    for p in rhs_parts:
        p = _strip_outer_parens_balanced(p.strip()).replace("~", "¬")
        neg = False
        if p.lower().startswith("not "):
            p = p[4:].strip()
            neg = True
        if p.startswith("¬"):
            p = p[1:].strip()
            neg = True
        mR = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*[A-Za-z]\s*\)\s*$", p)
        if not mR:
            # skip anything we can't parse as a simple literal
            continue
        rhs_lits.append((mR.group(1), neg))

    if not rhs_lits:
        return None
    return (ante_pred, rhs_lits)

def _is_more_specific(arg_fol_sentences: List[str]) -> float:
    """Heuristic specificity score: mention of subclass-like predicates (penguin) beats class (bird)."""
    sents = " ".join(arg_fol_sentences).lower()
    score = 0.0
    # domain-specific heuristic knobs; tune as needed
    if "penguin(" in sents:
        score += 2.0
    if "canary(" in sents:
        score += 1.5
    if "sparrow(" in sents:
        score += 1.5
    # universal rules about specific kinds
    if "∀" in sents and ("penguin(" in sents or "canary(" in sents):
        score += 0.5
    # broader classes reduce relative specificity
    if "bird(" in sents:
        score -= 0.4
    return score

def _grounded_labeling(grounded_ext: List[str], ids: List[str], edges_idx: List[Tuple[int,int]]) -> Dict[str, str]:
    """Compute simple in/out/undec labeling from grounded extension and attacks."""
    idx_by_id = {aid: i for i, aid in enumerate(ids)}
    in_set = set(grounded_ext)
    out_set: Set[str] = set()
    for (i, j) in edges_idx:
        a, b = ids[i], ids[j]
        if a in in_set:
            out_set.add(b)
    lab: Dict[str, str] = {}
    for aid in ids:
        if aid in in_set:
            lab[aid] = "in"
        elif aid in out_set:
            lab[aid] = "out"
        else:
            lab[aid] = "undec"
    return lab

def _explain_grounded(ids: List[str], id_to_text: Dict[str,str], edges_idx: List[Tuple[int,int]], grounded_ext: List[str]) -> Dict[str, str]:
    """Human-readable one-liners per node explaining grounded status."""
    idx_by_id = {aid: i for i, aid in enumerate(ids)}
    attackers: Dict[str, List[str]] = {aid: [] for aid in ids}
    for (i, j) in edges_idx:
        attackers[ids[j]].append(ids[i])
    expl: Dict[str, str] = {}
    in_set = set(grounded_ext)
    for aid in ids:
        if aid in in_set:
            if attackers[aid]:
                expl[aid] = f"{aid} is IN because all of its attackers ({', '.join(attackers[aid])}) are OUT."
            else:
                expl[aid] = f"{aid} is IN because it has no attackers."
        else:
            if not attackers[aid]:
                expl[aid] = f"{aid} is UNDEC (no defense selected and no attackers accepted)."
            else:
                expl[aid] = f"{aid} is OUT because it is attacked by {', '.join(attackers[aid])} and has no accepted defenders."
    return expl

# --------------------------- Core pipeline ------------------------------------

def analyze_multilevel(
    raw_text: str,
    relation_mode: str = "auto",
    use_llm_edges: bool = False,
    llm_threshold: float = 0.55,
    llm_mode: str = "augment",
    semantics: List[str] = ("grounded", "preferred", "stable"),
    cq: bool = False,
    cq_topk: int = 2,
    dot_out: Optional[str] = None,
    # NEW knobs:
    derive_contradictions: str = "none",  # "none" | "mutual" | "orient"
    check_entailment: bool = False,
    explain: bool = False,
) -> Dict[str, Any]:
    """
    Build the three-layer IR with optional FOL-derived rebuttal edges, entailment checks, and explanations.
    """
    # 0) Split into blocks (each becomes an AF node)
    blocks: List[str] = parse_blocks_text(raw_text)

    # 1) Baseline AF edges from NL (heuristics/explicit/LLM)
    ids, id_to_text, edges_idx, meta = build_edges(
        blocks,
        relation_mode=relation_mode,
        use_llm=use_llm_edges,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    idx_by_id = {aid: i for i, aid in enumerate(ids)}

    # 2) Argument layer + FOL per claim
    arg_parser = ArgumentParser()
    cq_assigner = SchemeAssigner(topk=cq_topk, temperature=0.0) if (cq and SchemeAssigner is not None) else None
    logical = LogicalAnalyzer(debug=False)

    arguments_out: Dict[str, Any] = {}
    fol_cache_by_claim: Dict[Tuple[str,str], List[str]] = {}  # (arg_id, claim_id) -> [pretty FOL]
    conclusion_literal_by_arg: Dict[str, Tuple[int,str,str]] = {}  # aid -> (polarity, atom, pretty_str)
    all_fol_strings_by_arg: Dict[str, List[str]] = {}

    for aid in ids:
        text_block = id_to_text[aid]
        # Parse argument structure
        try:
            parsed = arg_parser.parse_argument(text_block)
        except Exception as e:
            arguments_out[aid] = {"text": text_block, "parse_error": str(e)}
            continue

        # Schemes/CQs
        if cq_assigner is not None:
            try:
                sfacts = cq_assigner.analyze(parsed, text_block, topk=cq_topk)
                parsed.scheme_requires = sfacts.requires
                parsed.scheme_answered = sfacts.answered
            except Exception as e:
                parsed.scheme_requires = []
                parsed.scheme_answered = []
                parsed.scheme_error = str(e)

        arg_dict = _dataclass_to_dict(parsed)

        # Per-claim FOL
        fol_sentences: List[Dict[str, Any]] = []
        all_fol_strings: List[str] = []
        for c in parsed.claims:
            scoped = _scope_id(aid, c.id)
            try:
                fol_arg = logical.extract_logical_form(c.content)
                idx = 0
                for stmt in fol_arg.statements:
                    idx += 1
                    pretty = stmt.formula.to_string()
                    fol_sentences.append({
                        "id": f"{scoped}.s{idx}",
                        "claim_id": c.id,
                        "pretty": pretty
                    })
                    all_fol_strings.append(pretty)
                fol_cache_by_claim[(aid, c.id)] = [s["pretty"] for s in fol_sentences if s["claim_id"] == c.id]
            except Exception as e:
                fol_sentences.append({
                    "id": f"{scoped}",
                    "claim_id": c.id,
                    "error": f"FOL parse failed: {e}",
                })
                fol_cache_by_claim[(aid, c.id)] = []

        all_fol_strings_by_arg[aid] = list(all_fol_strings)

        # Whole-argument FOL analysis (best-effort)
        fol_analysis: Optional[Dict[str, Any]] = None
        try:
            result = logical.analyze(logical.extract_logical_form(text_block))
            fol_analysis = {
                "issues": result.get("issues", []),
                "valid_inferences": result.get("valid_inferences", []),
            }
        except Exception:
            fol_analysis = None

        # Identify conclusion literal (for rebuttal detection)
        goal_id = arg_dict.get("goal_claim")
        concl_lit: Optional[Tuple[int,str,str]] = None
        if goal_id:
            for s in fol_sentences:
                if s.get("claim_id") == goal_id and "pretty" in s:
                    lit = _normalize_literal_str(s["pretty"])
                    if lit is not None:
                        pol, atom = lit
                        concl_lit = (pol, atom, s["pretty"])
                        break
        if concl_lit:
            conclusion_literal_by_arg[aid] = concl_lit

        arguments_out[aid] = {
            "text": text_block,
            "argument": arg_dict,
            "fol": {
                "sentences": fol_sentences,
                "analysis": fol_analysis
            }
        }

    # 3) (NEW) FOL-derived rebuttal edges from contradictory conclusions
    derived_edges_idx: Set[Tuple[int,int]] = set()
    edge_witness: Dict[Tuple[int,int], str] = {}
    if derive_contradictions in ("mutual", "orient") and len(conclusion_literal_by_arg) >= 2:
        # Index by atom: who asserts +atom and who asserts -atom?
        pos: Dict[str, List[Tuple[str,str]]] = {}  # atom -> [(aid, pretty)]
        neg: Dict[str, List[Tuple[str,str]]] = {}
        for aid, (pol, atom, pretty) in conclusion_literal_by_arg.items():
            if pol > 0:
                pos.setdefault(atom, []).append((aid, pretty))
            else:
                neg.setdefault(atom, []).append((aid, pretty))
        for atom in set(pos.keys()).intersection(neg.keys()):
            for (aid_pos, pretty_pos) in pos[atom]:
                for (aid_neg, pretty_neg) in neg[atom]:
                    if derive_contradictions == "mutual":
                        i, j = idx_by_id[aid_pos], idx_by_id[aid_neg]
                        k, l = idx_by_id[aid_neg], idx_by_id[aid_pos]
                        derived_edges_idx.add((i, j))
                        derived_edges_idx.add((k, l))
                        edge_witness[(i, j)] = f"rebut: {pretty_pos} vs {pretty_neg}"
                        edge_witness[(k, l)] = f"rebut: {pretty_neg} vs {pretty_pos}"
                    else:  # orient by specificity
                        a_score = _is_more_specific(all_fol_strings_by_arg.get(aid_pos, []))
                        b_score = _is_more_specific(all_fol_strings_by_arg.get(aid_neg, []))
                        if a_score > b_score:
                            i, j = idx_by_id[aid_pos], idx_by_id[aid_neg]
                        elif b_score > a_score:
                            i, j = idx_by_id[aid_neg], idx_by_id[aid_pos]
                        else:
                            # tie → mutual
                            i, j = idx_by_id[aid_pos], idx_by_id[aid_neg]
                            derived_edges_idx.add((idx_by_id[aid_neg], idx_by_id[aid_pos]))
                            edge_witness[(idx_by_id[aid_neg], idx_by_id[aid_pos])] = f"rebut: {pretty_neg} vs {pretty_pos}"
                        derived_edges_idx.add((i, j))
                        # assign witness in chosen direction
                        if (i, j) not in edge_witness:
                            # i attacks j, so take i's pretty against j's pretty
                            if ids[i] == aid_pos:
                                edge_witness[(i, j)] = f"rebut: {pretty_pos} vs {pretty_neg}"
                            else:
                                edge_witness[(i, j)] = f"rebut: {pretty_neg} vs {pretty_pos}"

    # Merge edges: baseline + derived (dedupe)
    base_edges = set(tuple(e) for e in edges_idx)
    final_edges = list(sorted(base_edges.union(derived_edges_idx)))
    # 4) Dung semantics on final edges
    # prepare clingo atoms mapping
    safe_atoms = make_unique([sanitize_atom(i) for i in ids])
    atom_of: Dict[str, str] = {ids[i]: safe_atoms[i] for i in range(len(ids))}
    atoms_list = [atom_of[i] for i in ids]
    attacks_atoms: List[Tuple[str, str]] = []
    for (i, j) in final_edges:
        attacks_atoms.append((atom_of[ids[i]], atom_of[ids[j]]))

    # compute semantics
    af_sem: Dict[str, Any] = {}
    def _atoms2ids_setset(families):
        if isinstance(families, (set, frozenset)):
            return sorted([aid for aid, atom in atom_of.items() if atom in families])
        out: List[List[str]] = []
        for fam in families:
            out.append(sorted([aid for aid, atom in atom_of.items() if atom in fam]))
        return out

    for sem in semantics:
        s = sem.lower()
        if s == "grounded":
            ext = af_clingo.grounded(atoms_list, attacks_atoms)
            af_sem["grounded"] = _atoms2ids_setset(ext)
        elif s == "preferred":
            fam = af_clingo.preferred(atoms_list, attacks_atoms)
            af_sem["preferred"] = _atoms2ids_setset(fam)
        elif s == "stable":
            fam = af_clingo.stable(atoms_list, attacks_atoms)
            af_sem["stable"] = _atoms2ids_setset(fam)
        elif s == "complete":
            fam = af_clingo.complete(atoms_list, attacks_atoms)
            af_sem["complete"] = _atoms2ids_setset(fam)
        elif s in ("semi-stable", "semistable"):
            fam = af_clingo.semi_stable(atoms_list, attacks_atoms)
            af_sem["semi-stable"] = _atoms2ids_setset(fam)
        elif s == "stage":
            fam = af_clingo.stage(atoms_list, attacks_atoms)
            af_sem["stage"] = _atoms2ids_setset(fam)

    # Optional DOT export
    if dot_out:
        try:
            af_clingo.export_dot(atoms_list, attacks_atoms, dot_out)
        except Exception:
            pass

    # 5) (NEW) Lightweight entailment checks per argument (Modus Ponens pattern)
    if check_entailment:
        for aid, bundle in arguments_out.items():
            arg = bundle.get("argument", {})
            goal_id = arg.get("goal_claim")
            if not goal_id:
                continue
            # collect premise FOL strings for this argument
            prem_fols: List[str] = []
            concl_fols: List[str] = []
            for s in bundle["fol"]["sentences"]:
                if s.get("claim_id") == goal_id and "pretty" in s:
                    concl_fols.append(s["pretty"])
                else:
                    # assume all non-goal claims are usable premises
                    if "pretty" in s:
                        prem_fols.append(s["pretty"])
            # parse rules and facts
            facts: List[Tuple[str, str, bool]] = []
            rules: List[Tuple[str, List[Tuple[str, bool]]]] = []
            for f in prem_fols:
                fact = _parse_fact_lit(f)
                if fact:
                    facts.append(fact)
                else:
                    rule = _parse_universal_rule(f)
                    if rule:
                        rules.append(rule)
            valid: List[Dict[str, Any]] = []
            for cf in concl_fols:
                c_fact = _parse_fact_lit(cf)
                if not c_fact:
                    continue
                c_pred, c_const, c_neg = c_fact
                # check any rule+fact combo deriving this literal
                found = False
                for (ante_pred, rhs_lits) in rules:
                    # ensure we have a matching fact P(c)
                    consts = [const for (pred, const, isneg) in facts if pred == ante_pred and not isneg]
                    for const in consts:
                        for (rhs_pred, rhs_neg) in rhs_lits:
                            if rhs_pred == c_pred and rhs_neg == c_neg and const == c_const:
                                valid.append({
                                    "rule": "modus_ponens",
                                    "via": f"∀x({ante_pred}(x) → ...{('¬' if rhs_neg else '')}{rhs_pred}(x)) + {ante_pred}({const}) ⊢ {('¬' if c_neg else '')}{c_pred}({const})"
                                })
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
            # attach results
            if "analysis" not in bundle["fol"] or bundle["fol"]["analysis"] is None:
                bundle["fol"]["analysis"] = {"issues": [], "valid_inferences": valid}
            else:
                bundle["fol"]["analysis"]["valid_inferences"] = bundle["fol"]["analysis"].get("valid_inferences", []) + valid

    # 6) Build AF JSON edges with provenance & witness
    # provenance from builder:
    prov = {
        "explicit_edges": meta.get("explicit_edges", []),
        "heuristic_edges": meta.get("heuristic_edges", []),
        "llm_edges": meta.get("llm_edges", []),
        "derived_edges": sorted(list(derived_edges_idx)),
        "final_edges": final_edges,
    }
    # create edge list in id-space with witness where available
    edges_json: List[Dict[str, Any]] = []
    base_edge_set = set(tuple(e) for e in edges_idx)
    for (i, j) in final_edges:
        e = {"from": ids[i], "to": ids[j], "type": "attack"}
        if (i, j) in edge_witness:
            e["witness"] = edge_witness[(i, j)]
            e["provenance"] = "derived:fol-contradiction"
        else:
            # try to tag baseline provenance
            if (i, j) in base_edge_set:
                # which bucket?
                tag = None
                if [i, j] in meta.get("explicit_edges", []):
                    tag = "explicit"
                elif [i, j] in meta.get("heuristic_edges", []):
                    tag = "heuristic"
                elif [i, j] in meta.get("llm_edges", []):
                    tag = "llm"
                e["provenance"] = tag or "baseline"
        edges_json.append(e)

    # 7) Optional grounded labeling + explanations
    labeling: Optional[Dict[str, str]] = None
    explanations: Optional[Dict[str, str]] = None
    if "grounded" in af_sem:
        g = af_sem["grounded"]
        if isinstance(g, list):  # it's a single extension
            labeling = _grounded_labeling(g, ids, final_edges)
            if explain:
                explanations = _explain_grounded(ids, id_to_text, final_edges, g)

    # Assemble final IR
    ir = {
        "doc_id": "doc:auto",
        "text": raw_text,
        "af": {
            "nodes": ids,
            "node_text": {aid: id_to_text[aid] for aid in ids},
            "edges": edges_json,
            "semantics": af_sem,
            "provenance": prov,
            "labeling_grounded": labeling,
            "explanations": explanations,
        },
        "arguments": arguments_out,
    }
    return ir

# ------------------------------ CLI -------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Multi-level analyzer (AF → arguments → FOL) with optional derived rebuttals and entailment checks.")
    ap.add_argument("file", nargs="?", default="examples/examples.txt",
                    help="Path to input file. Blocks separated by a blank line become AF nodes.")
    ap.add_argument("-o", "--out", default=None, help="Write JSON IR to this path (default: stdout).")
    ap.add_argument("--no-pretty", action="store_true", help="Disable pretty JSON.")
    # AF edge construction
    ap.add_argument("--relation", default="auto", choices=["auto", "explicit", "none"],
                    help="How to derive AF edges over blocks (default: auto).")
    ap.add_argument("--use-llm", action="store_true", help="Use LLM to infer AF attacks (see README env vars).")
    ap.add_argument("--llm-threshold", type=float, default=0.55, help="Confidence cutoff for LLM edges.")
    ap.add_argument("--llm-mode", default="augment", choices=["augment", "override"],
                    help="Combine with other edges (augment) or only LLM edges (override).")
    # Dung semantics
    ap.add_argument("--sem", action="append",
                    choices=["grounded","preferred","stable","complete","stage","semi-stable","semistable"],
                    help="Semantics to compute (repeatable). Default: grounded, preferred, stable.")
    ap.add_argument("--dot", dest="dot_out", default=None, help="Export AF as DOT to this path.")
    # Schemes / CQs
    ap.add_argument("--cq", default=False, action=argparse.BooleanOptionalAction, help="Enable scheme/CQ analysis.")
    ap.add_argument("--cq-topk", type=int, default=2, help="Top-k CQs per conclusion (default: 2).")
    # NEW knobs
    ap.add_argument("--derive-contradictions", default="none", choices=["none","mutual","orient"],
                    help="Derive rebuttal attacks from contradictory conclusions: none|mutual|orient (prefer specific).")
    ap.add_argument("--check-entailment", action="store_true",
                    help="Enable lightweight entailment checks (Modus Ponens detection) per argument.")
    ap.add_argument("--explain", action="store_true",
                    help="Add natural-language grounded explanations per node.")
    args = ap.parse_args()

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        print(f"Error: file '{args.file}' not found.")
        return

    sems = args.sem if args.sem else ["grounded", "preferred", "stable"]
    ir = analyze_multilevel(
        raw_text=raw,
        relation_mode=args.relation,
        use_llm_edges=args.use_llm,
        llm_threshold=args.llm_threshold,
        llm_mode=args.llm_mode,
        semantics=sems,
        cq=args.cq,
        cq_topk=args.cq_topk,
        dot_out=args.dot_out,
        derive_contradictions=args.derive_contradictions,
        check_entailment=args.check_entailment,
        explain=args.explain,
    )
    out_json = _json(ir, pretty=not args.no_pretty)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        print(out_json)

if __name__ == "__main__":
    main()
