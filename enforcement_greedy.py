
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

def propose_answer_for(cq_label: str, inf_label: str, context: str) -> str:
    prompt = f"""You are an argument coach.
Given a Critical Question (or deductive obligation) that undercuts an inference, write a brief (1–2 sentence) answer that would satisfy it.
Obligation: {cq_label}
Inference: {inf_label}
Context: {context}
Return ONLY the answer text, no preface."""
    ans = _llm_text(prompt)
    return _short_text(ans) if ans else f"Provide warrant/backing addressing: {cq_label[:80]}."

def propose_counter_for(attacker_label: str, context: str) -> str:
    prompt = f"""You are an argument coach.
Write a single, concise counterargument (1–2 sentences) that undercuts or rebuts the attacker below.
Attacker: {attacker_label}
Context: {context}
Return ONLY the counterargument text, no preface."""
    ans = _llm_text(prompt)
    return _short_text(ans) if ans else f"A plausible challenge undermines a key assumption: {attacker_label[:80]}..."

def strengthen_within(ir: ArgumentIR, tgt: str, g: AFGraph, budget: int) -> Plan:
    nodes, attacks, labels = set(g.nodes), set(g.attacks), dict(g.labels)
    before_E = grounded_extension(nodes, attacks)
    before_status = "Accepted" if tgt in before_E else "Not accepted"
    edits: List[Edit] = []
    rationale: List[str] = []
    context = "\n".join([p.text for p in ir.propositions][:5])

    # identify unmet obligations nodes: labels starting with "CQ unmet:" or "Obligation unmet:"
    unmet_nodes = [n for n, lab in labels.items() if lab.startswith("CQ unmet:") or lab.startswith("Obligation unmet:")]
    # prefer those that undercut direct defenders (those attacking neg:tgt)
    neg_t = f"neg:{tgt}"
    defenders = {a for (a, b) in attacks if b == neg_t}
    prio = []
    for n in unmet_nodes:
        # if n attacks a defender, prioritize it
        if (n, next(iter(defenders)) if defenders else "") in attacks:
            prio.append(n)
        else:
            prio.append(n)
    # Greedy add answers
    steps = 0
    for n in prio:
        if steps >= budget: break
        infs = [b for (a, b) in attacks if a == n and b in defenders or True]
        # find the inference this CQ attacks
        target_inf = None
        for (a, b) in attacks:
            if a == n:
                target_inf = b; break
        if not target_inf:
            continue
        cq_label = labels.get(n, n)
        inf_label = labels.get(target_inf, target_inf)
        ans_id = f"ans{len(nodes)+1}"
        ans_text = propose_answer_for(cq_label, inf_label, context)
        nodes.add(ans_id); labels[ans_id] = f"answer:{ans_text}"
        attacks.add((ans_id, n))
        edits.append(Edit(kind="add_node", node_id=ans_id, node_label=labels[ans_id]))
        edits.append(Edit(kind="add_attack", edge=(ans_id, n)))
        rationale.append(f"Answer obligation '{n}' attacking '{target_inf}': '{ans_text}'")
        steps += 1
        E = grounded_extension(nodes, attacks)
        if tgt in E:
            return Plan(edits, rationale, before_status, "Accepted", before_E, E)

    E = grounded_extension(nodes, attacks)
    after_status = "Accepted" if tgt in E else "Not accepted"
    return Plan(edits, rationale, before_status, after_status, before_E, E)

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
