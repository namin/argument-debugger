
# -*- coding: utf-8 -*-
"""
Greedy strengthening ("enforcement") over AF compiled from ARG-IR.

Two move types:
  - WITHIN-LINK: answer unmet obligations (CQ/DeductiveCheck) by adding ans:* → cq/ob:*.
  - ACROSS-GRAPH: add counter:* → attacker_of_target.

This is a PoC; swap with clingo optimization for cost-optimal enforcement later.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple, Set, Dict

from arg_ir import ArgumentIR
from compile_to_af import AFGraph
from af_semantics import grounded_extension, status, attackers_of, unattacked
from pedagogy import suggest_cq_answer

# Optional LLM
_LLM = None
try:
    import llm as _LLM
except Exception:
    _LLM = None

def _llm_text(prompt: str) -> Optional[str]:
    if _LLM is None:
        return None
    for fn in ("ask", "complete", "text"):
        if hasattr(_LLM, fn):
            try:
                return getattr(_LLM, fn)(prompt)
            except Exception:
                pass
    return None

@dataclass
class Edit:
    kind: str                   # "add_node" | "add_attack"
    node_id: Optional[str] = None
    node_label: Optional[str] = None
    edge: Optional[Tuple[str, str]] = None

@dataclass
class Plan:
    edits: List[Edit]
    rationale: List[str]
    before_status: str
    after_status: str
    before_extension: Set[str]
    after_extension: Set[str]

def _short_text(t: str) -> str:
    t = (t or "").strip().split("\n")[0]
    return t[:400]

def propose_counter_for(attacker_label: str, context: str) -> str:
    prompt = f"""You are an argument coach.
Write a single, concise counterargument (1–2 sentences) that undercuts or rebuts the attacker below.
Attacker: {attacker_label}
Context: {context}
Return ONLY the counterargument text, no preface."""
    ans = _llm_text(prompt)
    return _short_text(ans) if ans else f"A plausible challenge undermines a key assumption: {attacker_label[:80]}..."

def strengthen_within(ir: ArgumentIR, tgt: str, g: AFGraph, budget: int) -> Plan:
    # Local working copies
    nodes, attacks, labels = set(g.nodes), set(g.attacks), dict(g.labels)

    # Baseline status/extension for the plan object
    before_E = grounded_extension(nodes, attacks)
    before_status = "Accepted" if tgt in before_E else "Not accepted"

    edits: List[Edit] = []
    rationale: List[str] = []

    # 1) Collect unmet obligations (the only things we "answer" within-link).
    unmet_nodes = [
        n for n, lab in labels.items()
        if lab.startswith("CQ unmet:") or lab.startswith("Obligation unmet:")
    ]
    if not unmet_nodes or budget <= 0:
        after_E = grounded_extension(nodes, attacks)
        after_status = "Accepted" if tgt in after_E else "Not accepted"
        return Plan(edits, rationale, before_status, after_status, before_E, after_E)

    # Build fast incoming/outgoing maps once.
    incoming: Dict[str, Set[str]] = {}
    outgoing: Dict[str, Set[str]] = {}
    for a, b in attacks:
        incoming.setdefault(b, set()).add(a)
        outgoing.setdefault(a, set()).add(b)

    # Direct defenders of the target are the inference nodes with an edge to neg:target
    neg_t = f"neg:{tgt}"
    defenders: Set[str] = {a for (a, b) in attacks if b == neg_t}

    # Helper: skip obligations that already have any attacker (already answered/countered).
    def already_attacked(n: str) -> bool:
        return bool(incoming.get(n))

    # 2) Score obligations and choose the best target inference if an obligation hits multiple.
    #    Priority order:
    #      (a) obligations on direct defenders of the target (0 < 1)
    #      (b) obligations that are themselves unattacked (0 < 1)  → quick win
    #      (c) obligations whose target inference is NOT in the current grounded extension (0 < 1)
    #          (i.e., it's currently blocked, so answering may help)
    #      (d) stable tiebreak by node id to keep determinism
    candidates: List[Tuple[Tuple[int, int, int, str], str, str]] = []
    for n in unmet_nodes:
        if already_attacked(n):
            continue  # nothing to do; there is already an answer/counter to this obligation
        targets = outgoing.get(n, set())
        if not targets:
            continue  # malformed: an obligation node should attack at least one inference node

        # pick the best attacked inference for prioritization
        def best_key(tinf: str) -> Tuple[int, int, int, str]:
            is_direct_def = 0 if tinf in defenders else 1
            ob_unattacked = 0 if not incoming.get(n) else 1  # (redundant with already_attacked, but harmless)
            tinf_blocked = 0 if tinf not in before_E else 1
            return (is_direct_def, ob_unattacked, tinf_blocked, tinf)

        best_tinf = min(targets, key=best_key)
        candidates.append((best_key(best_tinf), n, best_tinf))

    # Nothing actionable
    if not candidates:
        after_E = grounded_extension(nodes, attacks)
        after_status = "Accepted" if tgt in after_E else "Not accepted"
        return Plan(edits, rationale, before_status, after_status, before_E, after_E)

    # Highest-leverage first
    candidates.sort()

    # 3) Greedily add answers within the budget, early-stop if target becomes accepted.
    steps = 0
    for _, ob_node, target_inf in candidates:
        if steps >= budget:
            break

        cq_label = labels.get(ob_node, ob_node)
        inf_label = labels.get(target_inf, target_inf)
        ans_text = suggest_cq_answer(ir, cq_label, inf_label)

        # Simple id scheme consistent with the rest of the file
        ans_id = f"ans{len(nodes) + 1}"
        nodes.add(ans_id)
        labels[ans_id] = f"answer:{ans_text}"
        attacks.add((ans_id, ob_node))

        edits.append(Edit(kind="add_node", node_id=ans_id, node_label=labels[ans_id]))
        edits.append(Edit(kind="add_attack", edge=(ans_id, ob_node)))
        rationale.append(f"Answer obligation '{ob_node}' attacking '{target_inf}': '{ans_text}'")

        # Update maps incrementally to keep scoring/early acceptance checks consistent
        incoming.setdefault(ob_node, set()).add(ans_id)

        steps += 1

        # Early stop if we've achieved acceptance
        E = grounded_extension(nodes, attacks)
        if tgt in E:
            return Plan(edits, rationale, before_status, "Accepted", before_E, E)

    # 4) Return final plan
    after_E = grounded_extension(nodes, attacks)
    after_status = "Accepted" if tgt in after_E else "Not accepted"
    return Plan(edits, rationale, before_status, after_status, before_E, after_E)

def strengthen_across(ir: ArgumentIR, tgt: str, g: AFGraph, budget: int) -> Plan:
    nodes, attacks, labels = set(g.nodes), set(g.attacks), dict(g.labels)
    before_E = grounded_extension(nodes, attacks)
    before_status = "Accepted" if tgt in before_E else "Not accepted"
    edits: List[Edit] = []
    rationale: List[str] = []
    context = "\n".join([p.text for p in ir.propositions][:5])

    steps = 0
    while steps < budget:
        atks = attackers_of(attacks, tgt)
        if not atks:
            break
        UA = unattacked(attacks, atks)
        pool = UA or atks
        a = sorted(list(pool))[0]
        attacker_label = labels.get(a, a)
        nid = f"c{len(nodes)+1}"
        txt = propose_counter_for(attacker_label, context)
        nodes.add(nid); labels[nid] = f"counter:{txt}"
        attacks.add((nid, a))
        edits.append(Edit(kind="add_node", node_id=nid, node_label=labels[nid]))
        edits.append(Edit(kind="add_attack", edge=(nid, a)))
        rationale.append(f"Add counter to attacker '{a}': '{txt}'")
        steps += 1
        E = grounded_extension(nodes, attacks)
        if tgt in E:
            return Plan(edits, rationale, before_status, "Accepted", before_E, E)

    E = grounded_extension(nodes, attacks)
    after_status = "Accepted" if tgt in E else "Not accepted"
    return Plan(edits, rationale, before_status, after_status, before_E, E)
