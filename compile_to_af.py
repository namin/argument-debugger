
# -*- coding: utf-8 -*-
"""
Compilation from ARG-IR to AF/BAF-like structures.

AF mode (Dung AF):
  - Nodes: propositions + inferences (+ aux CQ/default-doubt nodes).
  - Attacks: rebuts/undermines/undercuts mapped to attacks.
  - "Support-as-defense" trick: for each proposition p add neg:p -> p; for each
    inference i that supports p, add i -> neg:p.

Optional seeding:
  - For each inference obligation with status != "met", add a cq/dc node attacking the inference.

BAF mode (skeleton):
  - Return support edges explicitly (not used by AF semantics here).

All in stdlib.
"""

from __future__ import annotations
from typing import Set, Tuple, Dict, List
from dataclasses import dataclass
from arg_ir import ArgumentIR, Proposition, Inference, Relation, Obligation

# ---- AF build -----------------------------------------------------------------

def neg_id(pid: str) -> str:
    return f"neg:{pid}"

def port_target_to_node(target: str) -> str:
    """
    Ports like "i1#warrant" → "i1"; "i1#premise:p2" → "i1".
    """
    return target.split('#', 1)[0] if '#' in target else target

@dataclass
class AFGraph:
    nodes: Set[str]
    attacks: Set[Tuple[str, str]]
    labels: Dict[str, str]                 # node id → human label
    meta: Dict[str, List[Tuple[str,str]]]  # e.g., "supports": [(i,p), ...]

def compile_to_af(
    ir: ArgumentIR,
    include_default_doubt: bool = True,
    include_obligation_attackers: bool = True,
    support_as_defense: bool = True
) -> AFGraph:
    nodes: Set[str] = set()
    attacks: Set[Tuple[str, str]] = set()
    labels: Dict[str, str] = {}
    supports: List[Tuple[str, str]] = []

    # Propositions and optional default-doubt
    for p in ir.propositions:
        nodes.add(p.id); labels[p.id] = p.text
        if include_default_doubt:
            nid = neg_id(p.id)
            nodes.add(nid); labels[nid] = f"default doubt of {p.id}"
            attacks.add((nid, p.id))

    # Inferences
    for i in ir.inferences:
        nodes.add(i.id)
        srcs = ", ".join(i.from_ids) if i.from_ids else "∅"
        labels[i.id] = f"{i.type}:{i.scheme or ''} [{srcs} ⇒ {i.to}]".strip()

    # Relations
    for r in ir.relations:
        if r.type == "supports":
            supports.append((r.frm, r.to))
        elif r.type in ("rebuts", "undermines", "undercuts", "attacks"):
            frm = r.frm
            to = port_target_to_node(r.to)
            attacks.add((frm, to))

    # Support-as-defense: i -> neg:p
    if support_as_defense:
        for (i, p) in supports:
            attacks.add((i, neg_id(p)))

    # Obligations seeding: for unmet ones, create cq:/dc: nodes attacking the inference
    if include_obligation_attackers:
        for i in ir.inferences:
            for ob in i.obligations:
                if ob.status != "met":
                    nid = f"{'cq' if ob.kind=='CQ' else 'ob'}:{i.id}:{ob.name}"
                    nodes.add(nid)
                    labels[nid] = f"{ob.kind} unmet: {ob.name} (for {i.id})"
                    attacks.add((nid, i.id))

    return AFGraph(nodes=nodes, attacks=attacks, labels=labels, meta={"supports": supports})
