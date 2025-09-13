# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Set, Tuple, Dict, List
from arg_ir import ArgumentIR

def neg_id(pid: str) -> str:
    return f"neg:{pid}"

def port_target_to_node(target: str) -> str:
    # Preserve your anchor-drop behavior (e.g., "p3#foo" -> "p3")
    return target.split("#", 1)[0] if "#" in target else target

@dataclass
class AFGraph:
    nodes: Set[str]
    attacks: Set[Tuple[str, str]]
    labels: Dict[str, str]
    meta: Dict[str, List[Tuple[str, str]]]

# -----------------------------
# Helpers for obligations/CQs
# -----------------------------

def _seed_from_ir_obligations(inf) -> List[Tuple[str, str]]:
    """
    If the IR already carries obligations for this inference, collect any that are unmet.
    Returns a list of (kind, name) where kind is 'cq' or 'ob'.
    """
    out: List[Tuple[str, str]] = []
    obs = getattr(inf, "obligations", None)
    if not obs:
        return out
    for ob in obs:
        # Be tolerant to slight field name differences
        status = (getattr(ob, "status", None) or getattr(ob, "state", None) or "").lower()
        if status == "met":
            continue
        kind_raw = (getattr(ob, "kind", "") or "").lower()
        kind = "cq" if kind_raw in ("cq", "criticalquestion", "critical_question") else "ob"
        name = getattr(ob, "name", None) or getattr(ob, "id", None) or "unspecified"
        out.append((kind, name))
    return out

def _seed_from_scheme_type(inf) -> List[Tuple[str, str]]:
    """
    Fallback: derive unmet obligations/CQs from scheme/type/rule when the IR didn't provide any.
    Returns a list of (kind, name). We mark these as 'cq' by default, and 'ob' for strict checks.
    """
    sch = (getattr(inf, "scheme", "") or "").lower()
    typ = (getattr(inf, "type", "") or "").lower()
    rule = (getattr(inf, "rule", "") or "").lower()

    # Practical reasoning (normative conclusions)
    if "practicalreasoning" in sch or typ == "practical":
        names = ["means_lead_to_goal", "side_effects_acceptable", "better_alternative_absent"]
        return [("cq", n) for n in names]

    # Causal links
    if "causal" in sch or typ == "causal":
        names = ["mechanism", "robustness", "temporal_precedence"]
        return [("cq", n) for n in names]

    # Strict/deductive checks
    if rule == "strict":
        names = ["premises_present", "rule_applicable", "term_consistency"]
        return [("ob", n) for n in names]

    # Generic trio if nothing else matches
    names = ["premises_present", "rule_applicable", "term_consistency"]
    return [("cq", n) for n in names]

def _obligations_for(inf) -> List[Tuple[str, str]]:
    """
    Prefer obligations already present in the IR; otherwise fall back to scheme/type mapping.
    Each item is (kind, name) where kind ∈ {'cq','ob'}.
    """
    from_ir = _seed_from_ir_obligations(inf)
    if from_ir:
        return from_ir
    return _seed_from_scheme_type(inf)

def _label_inference(inf) -> str:
    srcs = ", ".join(getattr(inf, "from_ids", []) or [])
    to = getattr(inf, "to", "")
    # Keep your original shape: "<type>:<scheme> [srcs ⇒ to]"
    typ = getattr(inf, "type", "") or ""
    sch = getattr(inf, "scheme", "") or ""
    head = f"{typ}:{sch}".strip(":")
    return f"{head} [{srcs} ⇒ {to}]".strip()

# -----------------------------
# Main compiler
# -----------------------------

def compile_to_af(
    ir: ArgumentIR,
    include_default_doubt: bool = True,
    include_obligation_attackers: bool = True,
    support_as_defense: bool = True,
) -> AFGraph:
    """
    Compile the Argument IR to an abstract argumentation framework (AF).

    - Propositions become nodes; each gets a default-doubt attacker neg:p
    - Inferences become nodes
    - Explicit relations:
        * supports(frm, to) recorded in meta["supports"]
        * attacks/rebuts/undermines/undercuts(frm, to) add attacks (frm -> to) (with #anchor stripped)
    - support_as_defense: add (i -> neg:to) so inference nodes directly defend their conclusions
      AND convert explicit supports edges to (frm -> neg:to)
    - include_obligation_attackers: add CQ/obligation undercutters against inference nodes
      using IR-provided obligations when present, else scheme/type-derived defaults
    """
    nodes: Set[str] = set()
    attacks: Set[Tuple[str, str]] = set()
    labels: Dict[str, str] = {}
    supports: List[Tuple[str, str]] = []

    # 1) Propositions and default doubt
    for p in ir.propositions:
        nodes.add(p.id)
        labels[p.id] = p.text
        if include_default_doubt:
            nid = neg_id(p.id)
            nodes.add(nid)
            labels[nid] = f"default doubt of {p.id}"
            attacks.add((nid, p.id))

    # 2) Inferences as first-class nodes (+ direct defense to their conclusions)
    for i in ir.inferences:
        nodes.add(i.id)
        labels[i.id] = _label_inference(i)
        # Ensure an inference defends its conclusion against default doubt
        if support_as_defense and getattr(i, "to", None):
            attacks.add((i.id, neg_id(i.to)))

    # 3) Explicit relations: supports / attacks
    for r in getattr(ir, "relations", []) or []:
        rtype = (getattr(r, "type", "") or "").lower()
        frm = getattr(r, "frm", None)
        to = getattr(r, "to", None)
        if not frm or not to:
            continue
        if rtype == "supports":
            supports.append((frm, to))
        elif rtype in ("rebuts", "undermines", "undercuts", "attacks"):
            attacks.add((frm, port_target_to_node(to)))

    # 4) Convert supports into defense edges (optional)
    if support_as_defense:
        for (frm, to) in supports:
            # A support edge (frm -> to) becomes a defense of 'to' against its negation
            attacks.add((frm, neg_id(to)))

    # 5) Obligation/CQ undercutters (IR-provided first, fallback to scheme/type)
    if include_obligation_attackers:
        for i in ir.inferences:
            for (kind, name) in _obligations_for(i):
                nid = f"{kind}:{i.id}:{name}"
                nodes.add(nid)
                if kind == "cq":
                    labels[nid] = f"CQ unmet: {name}"
                else:
                    labels[nid] = f"Obligation unmet: {name}"
                attacks.add((nid, i.id))

    return AFGraph(nodes=nodes, attacks=attacks, labels=labels, meta={"supports": supports})
