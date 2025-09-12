
# -*- coding: utf-8 -*-
"""
cq_templates.py — compatibility shim

Provides:
  - seed_obligations_for(inf, text_context=None) -> List[Obligation]
  - seed_all_obligations(ir, text_context=None) -> ArgumentIR  (fills any missing)

This mirrors the role you referenced ("from cq_templates import seed_obligations_for")
and builds obligations from `cq_catalog.cqs_for` using the scheme or (fallback) type
of each inference. By default, obligations are marked "unmet".

Drop this file next to your other modules so the import works.
"""

from __future__ import annotations
from typing import List, Optional
from arg_ir import Inference, Obligation, ArgumentIR
from cq_catalog import cqs_for

def seed_obligations_for(inf: Inference, text_context: Optional[str] = None) -> List[Obligation]:
    """
    Create a list of Obligation objects for the given inference based on its scheme/type.
    Marks everything 'unmet' by default, with a couple of light heuristics to 'met'/'unknown'.
    """
    scheme = (inf.scheme or "").strip()
    cqs = cqs_for(scheme, inf.type if not scheme else "")
    obligations: List[Obligation] = []
    for name, _prompt in cqs:
        status = "unmet"
        # Light heuristics (safe defaults):
        if name == "premises_present" and inf.fol and inf.fol.premises and inf.fol.conclusion:
            status = "met"
        elif name == "rule_applicable" and (inf.warrant_text or inf.backing_text):
            status = "unknown"
        obligations.append(Obligation(id=f"{inf.id}.{name}", kind="CQ", name=name, status=status))
    return obligations

def seed_all_obligations(ir: ArgumentIR, text_context: Optional[str] = None) -> ArgumentIR:
    """
    For each inference with no obligations, attach seeded obligations in-place.
    Returns the same `ir` for convenience.
    """
    for inf in ir.inferences:
        if not inf.obligations:
            inf.obligations = seed_obligations_for(inf, text_context=text_context)
    return ir
