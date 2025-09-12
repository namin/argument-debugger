
# -*- coding: utf-8 -*-
"""
Minimal Critical Questions (CQs) catalog.

Maps scheme/type → list of canonical CQ names (snake_case) + human prompts.
"""

from typing import Dict, List, Tuple

# canonical name → human-readable prompt
_SCHEMES: Dict[str, List[Tuple[str, str]]] = {
    "ExpertOpinion": [
        ("expert_credible", "Is the cited expert credible in this domain?"),
        ("within_field", "Is the statement within the expert's field?"),
        ("consensus", "Do other qualified experts broadly agree?"),
        ("independence", "Is the expert unbiased/independent?")
    ],
    "CauseToEffect": [
        ("mechanism", "Is there a plausible mechanism from cause to effect?"),
        ("temporal_precedence", "Does the cause precede the effect?"),
        ("confounders", "Are key confounders controlled for?"),
        ("robustness", "Is the effect robust across contexts?")
    ],
    "PracticalReasoning": [
        ("goal_stated", "Is the goal clearly stated and agreed?"),
        ("means_lead_to_goal", "Will the proposed action achieve the stated goal?"),
        ("side_effects_acceptable", "Are negative side effects acceptable or mitigated?"),
        ("better_alternative_absent", "Is there no better alternative that achieves the goal?")
    ],
    "deductive": [
        ("premises_present", "Are all required premises present?"),
        ("rule_applicable", "Is the rule/warrant explicit and applicable?"),
        ("term_consistency", "Are terms used consistently (no equivocation)?")
    ]
}

def cqs_for(scheme: str, fallback_type: str = "") -> List[Tuple[str, str]]:
    if scheme in _SCHEMES:
        return _SCHEMES[scheme]
    if fallback_type in _SCHEMES:
        return _SCHEMES[fallback_type]
    return []

def all_schemes() -> Dict[str, List[Tuple[str, str]]]:
    return dict(_SCHEMES)
