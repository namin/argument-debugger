
import re, json
from typing import Optional
from arg_ir import ArgumentIR, Proposition, Inference, Obligation, FOLPayload, Relation, load_argument_ir
from cq_catalog import cqs_for

try:
    import llm as _LLM
except Exception:
    _LLM = None

def tolerant_json_extract(s: str) -> Optional[dict]:
    if not s:
        return None
    try:
        import json
        return json.loads(s)
    except Exception:
        pass
    candidates=[]; opens=[]
    for i,ch in enumerate(s):
        if ch=='{': opens.append(i)
        elif ch=='}' and opens:
            start=opens.pop(); candidates.append(s[start:i+1])
    candidates.sort(key=len, reverse=True)
    for seg in candidates:
        try:
            return json.loads(seg)
        except Exception:
            continue
    try:
        a=s.find('{'); b=s.rfind('}')
        if 0<=a<b: return json.loads(s[a:b+1])
    except Exception:
        pass
    return None

_PROMPT = """You are converting an argument into ARG-IR v1.1 JSON.
Return a single JSON object with propositions, inferences, relations (ports allowed), and targets.
Always include supports iX->pY. Instantiate scheme-appropriate CQs as obligations with status "unmet" unless clearly satisfied.
Return ONLY JSON.
Argument:
"""

def _llm_json(prompt: str) -> Optional[dict]:
    if _LLM is None: return None
    for fn in ("ask_json","complete_json","json"):
        if hasattr(_LLM, fn):
            try: return getattr(_LLM, fn)(prompt)
            except Exception: pass
    for fn in ("ask","complete","text"):
        if hasattr(_LLM, fn):
            try: return tolerant_json_extract(getattr(_LLM, fn)(prompt))
            except Exception: pass
    return None

def _heuristic_parse(text: str) -> ArgumentIR:
    sents=[s.strip() for s in re.split(r'[.!?]\s+', text.strip()) if s.strip()]
    if not sents: sents=[text.strip() or "(empty)"]
    props=[Proposition(id=f"p{k+1}", text=s) for k,s in enumerate(sents)]
    tgt=props[-1].id
    premises=[p.id for p in props[:-1]] or [props[0].id]
    i1=Inference(id="i1", from_ids=premises, to=tgt, rule="defeasible", type="deductive", scheme="ModusPonens", obligations=[], fol=None)
    rels=[Relation(type="supports", frm="i1", to=tgt)]
    return ArgumentIR(propositions=props, inferences=[i1], relations=rels, targets=[tgt])

def _ensure_obligations(ir: ArgumentIR) -> ArgumentIR:
    for inf in ir.inferences:
        if not inf.obligations:
            scheme=inf.scheme if inf.scheme else None
            cq_list=cqs_for(scheme, inf.type if not scheme else "")
            obs=[]
            for k,_prompt in cq_list:
                obs.append(Obligation(id=f"{inf.id}.{k}", kind="CQ", name=k, status="unmet"))
            inf.obligations=obs
    return ir

def nl_to_argir(text: str) -> ArgumentIR:
    obj=_llm_json(_PROMPT + "\n" + text.strip()) if _LLM else None
    if obj is None:
        ir=_heuristic_parse(text); return _ensure_obligations(ir)
    try:
        ir=load_argument_ir(obj)
        have={(r.frm,r.to) for r in ir.relations if r.type=="supports"}
        for inf in ir.inferences:
            if (inf.id, inf.to) not in have:
                ir.relations.append(Relation(type="supports", frm=inf.id, to=inf.to))
        return _ensure_obligations(ir)
    except Exception:
        ir=_heuristic_parse(text); return _ensure_obligations(ir)
