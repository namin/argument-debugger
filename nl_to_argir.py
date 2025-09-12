
# -*- coding: utf-8 -*-
"""
LLM → ARG-IR parser (single semantic parsing) with:
- tolerant JSON extraction
- auto-seeded obligations (CQs) when missing
- FOL seeding for strict steps via heuristics (fol_from_nl.seed_fol_for_strict)
- heuristic fallback if LLM unavailable

This module is stdlib-only.
"""

from __future__ import annotations
import re
import json
from typing import Optional
from arg_ir import ArgumentIR, Proposition, Inference, Obligation, FOLPayload, Relation, load_argument_ir
from cq_catalog import cqs_for
from fol_from_nl import seed_fol_for_strict

# Optional LLM adapter
_LLM = None
try:
    import llm as _LLM  # repo-local
except Exception:
    _LLM = None

# ---- Robust JSON extraction ---------------------------------------------------
def tolerant_json_extract(s: str) -> Optional[dict]:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    candidates = []
    opens = []
    for i, ch in enumerate(s):
        if ch == '{':
            opens.append(i)
        elif ch == '}' and opens:
            start = opens.pop()
            candidates.append(s[start:i+1])
    candidates.sort(key=len, reverse=True)
    for seg in candidates:
        try:
            obj = json.loads(seg)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    try:
        a = s.find('{'); b = s.rfind('}')
        if 0 <= a < b:
            return json.loads(s[a:b+1])
    except Exception:
        pass
    return None

# ---- Prompt -------------------------------------------------------------------
_PROMPT = """You are converting an argument into ARG-IR v1.1 JSON.

Return a single JSON object with:
- "propositions": [{id, text, kind?, polarity?, modality?, sources?, tags?}]
- "inferences": [{
    id, from: [prop_ids], to: prop_id,
    rule: "strict"|"defeasible",
    type: "deductive"|"statistical"|"causal"|"analogical"|"practical",
    scheme?, warrant_text?, backing_text?, qualifier?, rebuttals?,
    obligations?: [{id, kind, name, status}],
    fol?: {premises: [..], conclusion: "...", symbols: {...}}  // supply when the step is strict/deductive and the forms are clear
  }]
- "relations": [{type: "supports"|"rebuts"|"undermines"|"undercuts"|"attacks", from: id, to: id_or_port}]
  where ports are like "i1#warrant" or "i1#premise:p2"
- "targets": [prop_id]

Guidelines:
- Use proposition ids p1..pN and inference ids i1..iM.
- ALWAYS include "supports" from each inference to its conclusion (iX -> pY).
- If a premise is contested, use "undermines" from a proposition to "iX#premise:pY".
- If a warrant/backing/rule is contested, use "undercuts" to "iX#warrant" or "iX#rule".
- For strict deductive steps (e.g., syllogisms, 'if-then' + premise), include a minimal "fol" in standard math or TPTP-like form.
- Instantiate scheme-appropriate Critical Questions as "obligations" with status "unmet" unless clearly satisfied in the text.
Return ONLY JSON.
Argument:
"""

def _llm_json(prompt: str) -> Optional[dict]:
    if _LLM is None:
        return None
    for fn in ("ask_json", "complete_json", "json"):
        if hasattr(_LLM, fn):
            try:
                return getattr(_LLM, fn)(prompt)
            except Exception:
                pass
    for fn in ("ask", "complete", "text"):
        if hasattr(_LLM, fn):
            try:
                txt = getattr(_LLM, fn)(prompt)
                return tolerant_json_extract(txt)
            except Exception:
                pass
    return None

# ---- Fallback heuristic -------------------------------------------------------
def _heuristic_parse(text: str) -> ArgumentIR:
    # Very simple: sentences → p1..pN, last is target; i1 supports last from others
    sents = [s.strip() for s in re.split(r'[.!?]\s+', text.strip()) if s.strip()]
    if not sents:
        sents = [text.strip()] if text.strip() else ["(empty)"]
    props = [Proposition(id=f"p{k+1}", text=s) for k, s in enumerate(sents)]
    tgt = props[-1].id
    premises = [p.id for p in props[:-1]] or [props[0].id]
    # conservative default: deductive strict if we see quantifier/if-then; else defeasible
    txt_low = text.lower()
    rule = "strict" if ("all " in txt_low or "if " in txt_low or "only if" in txt_low) else "defeasible"
    itype = "deductive" if rule == "strict" else "deductive"
    i1 = Inference(id="i1", from_ids=premises, to=tgt, rule=rule, type=itype, scheme="ModusPonens" if "if " in txt_low else None,
                   obligations=[], fol=None)
    rels = [Relation(type="supports", frm="i1", to=tgt)]
    return ArgumentIR(propositions=props, inferences=[i1], relations=rels, targets=[tgt])

def _ensure_obligations(ir: ArgumentIR) -> ArgumentIR:
    """
    If any inference has no obligations, instantiate scheme/type-appropriate CQs as unmet.
    """
    for inf in ir.inferences:
        if not inf.obligations:
            scheme = inf.scheme if inf.scheme else None
            cq_list = cqs_for(scheme, inf.type if not scheme else "")
            new_obs = []
            for k, _prompt in cq_list:
                ob_id = f"{inf.id}.{k}"
                new_obs.append(Obligation(id=ob_id, kind="CQ", name=k, status="unmet"))
            inf.obligations = new_obs
    return ir

# ---- Public API ---------------------------------------------------------------
def nl_to_argir(text: str) -> ArgumentIR:
    obj = _llm_json(_PROMPT + "\n" + text.strip()) if _LLM else None
    if obj is None:
        ir = _heuristic_parse(text)
        ir = _ensure_obligations(ir)
        seed_fol_for_strict(ir)
        return ir
    try:
        ir = load_argument_ir(obj)
        # Ensure every inference has an explicit supports to its conclusion
        have = {(r.frm, r.to) for r in ir.relations if r.type == "supports"}
        for inf in ir.inferences:
            if (inf.id, inf.to) not in have:
                ir.relations.append(Relation(type="supports", frm=inf.id, to=inf.to))
        ir = _ensure_obligations(ir)
        seed_fol_for_strict(ir)
        return ir
    except Exception:
        ir = _heuristic_parse(text)
        ir = _ensure_obligations(ir)
        seed_fol_for_strict(ir)
        return ir
