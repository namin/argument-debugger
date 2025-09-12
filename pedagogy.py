
# -*- coding: utf-8 -*-
"""
Pedagogical helpers:
- Suggest concrete, context-aware CQ answers
- Explain why acceptance changed
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Set
import re
from arg_ir import ArgumentIR

_percent_pat = re.compile(r'(?P<num>\d+(?:\.\d+)?)\s*%')

def first_percent(text: str) -> Optional[float]:
    m = _percent_pat.search(text or "")
    if not m: return None
    try:
        return float(m.group('num'))
    except Exception:
        return None

def find_goal_metrics(ir: ArgumentIR):
    rev = None; loss = None
    for p in ir.propositions:
        t = p.text.lower()
        if "goal" in t and ("revenue" in t or "ridership" in t):
            nums = [first_percent(p.text)]
            rest = p.text
            if nums[0] is not None:
                idx = p.text.find("%")
                rest = p.text[idx+1:] if idx >= 0 else p.text
            nums2 = first_percent(rest)
            vals = []
            if nums[0] is not None: vals.append(nums[0])
            if nums2 is not None: vals.append(nums2)
            if len(vals) == 2:
                rev, loss = vals[0], vals[1]
                break
    return rev, loss

def find_offpeak_effect(ir: ArgumentIR):
    dp = None; dq = None
    for p in ir.propositions:
        t = p.text.lower()
        if "off-peak" in t or "off peak" in t:
            nums = _percent_pat.findall(p.text)
            if len(nums) >= 2:
                try:
                    dp = float(nums[0]); dq = float(nums[1]); break
                except Exception:
                    continue
    return dp, dq

def contains_low_income(ir: ArgumentIR) -> bool:
    return any("low-income" in (p.text.lower()) or "low income" in (p.text.lower()) for p in ir.propositions)

def find_alt_policy_node(ir: ArgumentIR) -> Optional[str]:
    for p in ir.propositions:
        if "fare enforcement" in p.text.lower() or "enforcement" in p.text.lower():
            return p.id
    return None

def suggest_cq_answer(ir: ArgumentIR, cq_label: str, inference_label: str) -> str:
    cq_lower = cq_label.lower()
    if "means_lead_to_goal" in cq_lower:
        rev, loss = find_goal_metrics(ir)
        dp, dq = find_offpeak_effect(ir)
        if rev is not None and dp is not None and dq is not None:
            delta_r = dp - dq
            return (f"Quantitative link: Off-peak ΔR ≈ {dp:.1f}% − {dq:.1f}% = {delta_r:.1f}%, "
                    f"meeting the ≥{rev:.1f}% revenue target; ridership loss {dq:.1f}% stays within the cap.")
        return ("Provide a quantitative link from premises to the goal (e.g., price vs. ridership) "
                "showing the policy meets the revenue target while staying within the loss cap.")
    if "side_effects_acceptable" in cq_lower:
        if contains_low_income(ir):
            return ("Mitigation: exempt or discount low-income riders and confine the increase to off-peak; "
                    "project resulting loss and equity impact remain within stated thresholds.")
        return ("Mitigation plan: limit to off-peak periods and add discounts for sensitive groups.")
    if "better_alternative_absent" in cq_lower:
        alt = find_alt_policy_node(ir)
        if alt:
            return ("Show why fare enforcement alone is insufficient (near saturation, marginal cost), "
                    "or propose a combined plan where enforcement contributes and a modest off-peak increase closes the gap.")
        return ("Argue there is no strictly better feasible alternative, or propose a quantified combined plan.")
    if "mechanism" in cq_lower:
        return ("Specify operational steps linking enforcement to recovered revenue with baseline and expected uplift.")
    if "temporal_precedence" in cq_lower:
        return ("Cite before–after data showing revenue rises following enforcement changes.")
    if "robustness" in cq_lower:
        return ("Provide results across multiple routes/periods to show persistence.")
    if "premises_present" in cq_lower:
        return ("List all premises explicitly; avoid relying on implicit warrants or undefined terms.")
    if "rule_applicable" in cq_lower:
        return ("State the warrant precisely and show its conditions are satisfied.")
    if "term_consistency" in cq_lower:
        return ("Define key terms (e.g., 'ridership', 'revenue') consistently.")
    return ("Provide a targeted warrant/backing that directly answers this question; add a calculation or data point.")

def explain_acceptance_delta(before_E: Set[str], after_E: Set[str],
                             attacks: Set[tuple], labels: Dict[str,str], target: str) -> List[str]:
    lines: List[str] = []
    if target in before_E and target in after_E:
        lines.append("Target was already accepted; plan preserved acceptance."); return lines
    if target not in before_E and target in after_E:
        lines.append("Target became accepted because key attackers were defeated:")
    elif target not in after_E:
        lines.append("Target remains not accepted; some attackers still stand:")
    atk = {a for (a,b) in attacks if b == target}
    if not atk:
        lines.append("  (No direct attackers; acceptance follows from defended default doubt.)")
        return lines
    for a in sorted(list(atk)):
        a_lab = labels.get(a, a)
        defeaters = [x for (x,y) in attacks if y == a and x in after_E]
        if target in after_E:
            if defeaters:
                lines.append(f"  - {a} ('{a_lab}') is attacked by {defeaters}; those defenders are accepted.")
            else:
                lines.append(f"  - {a} ('{a_lab}') remains undefeated (but other defenses suffice).")
        else:
            if a in after_E:
                lines.append(f"  - {a} ('{a_lab}') is accepted and continues to block the target.")
            else:
                lines.append(f"  - {a} ('{a_lab}') is not accepted, but the target still lacks sufficient defense.")
    return lines
