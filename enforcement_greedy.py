
from dataclasses import dataclass
from typing import Optional, Tuple, List, Set
from arg_ir import ArgumentIR
from compile_to_af import AFGraph
from af_semantics import grounded_extension, attackers_of, unattacked

try:
    import llm as _LLM
except Exception:
    _LLM = None

def _llm_text(prompt: str) -> Optional[str]:
    if _LLM is None: return None
    for fn in ("ask","complete","text"):
        if hasattr(_LLM, fn):
            try: return getattr(_LLM, fn)(prompt)
            except Exception: pass
    return None

@dataclass
class Edit:
    kind: str
    node_id: Optional[str]=None
    node_label: Optional[str]=None
    edge: Optional[Tuple[str,str]]=None

@dataclass
class Plan:
    edits: List[Edit]
    rationale: List[str]
    before_status: str
    after_status: str
    before_extension: Set[str]
    after_extension: Set[str]

def _short(t: str) -> str:
    t=(t or "").strip().split("\n")[0]; return t[:400]

def propose_answer_for(cq_label: str, inf_label: str, context: str) -> str:
    prompt=f"You are an argument coach. Write a 1–2 sentence answer to satisfy: {cq_label} for {inf_label}. Context: {context}"
    ans=_llm_text(prompt); 
    return _short(ans) if ans else f"Add warrant/backing addressing: {cq_label}."

def propose_counter_for(attacker_label: str, context: str) -> str:
    prompt=f"You are an argument coach. Write a 1–2 sentence counter to: {attacker_label}. Context: {context}"
    ans=_llm_text(prompt); 
    return _short(ans) if ans else f"Challenge the key assumption: {attacker_label[:80]}..."

def strengthen_within(ir: ArgumentIR, tgt: str, g: AFGraph, budget: int) -> Plan:
    nodes=set(g.nodes); attacks=set(g.attacks); labels=dict(g.labels)
    from af_semantics import grounded_extension
    before_E=grounded_extension(nodes, attacks); before="Accepted" if tgt in before_E else "Not accepted"
    edits=[]; rationale=[]
    context=" ".join([p.text for p in ir.propositions][:5])
    unmet=[n for n,lab in labels.items() if lab.startswith("CQ unmet:") or lab.startswith("Obligation unmet:")]
    steps=0
    for n in unmet:
        if steps>=budget: break
        target_inf=None
        for (a,b) in attacks:
            if a==n:
                target_inf=b; break
        if not target_inf: continue
        cq_label=labels.get(n, n); inf_label=labels.get(target_inf, target_inf)
        ans_id=f"ans{len(nodes)+1}"; ans_text=propose_answer_for(cq_label, inf_label, context)
        nodes.add(ans_id); labels[ans_id]=f"answer:{ans_text}"; attacks.add((ans_id,n))
        edits.extend([Edit(kind="add_node", node_id=ans_id, node_label=labels[ans_id]),
                      Edit(kind="add_attack", edge=(ans_id,n))])
        rationale.append(f"Answer obligation '{n}' attacking '{target_inf}': '{ans_text}'")
        steps+=1
        E=grounded_extension(nodes, attacks)
        if tgt in E:
            return Plan(edits, rationale, before, "Accepted", before_E, E)
    E=grounded_extension(nodes, attacks)
    return Plan(edits, rationale, before, ("Accepted" if tgt in E else "Not accepted"), before_E, E)

def strengthen_across(ir: ArgumentIR, tgt: str, g: AFGraph, budget: int) -> Plan:
    nodes=set(g.nodes); attacks=set(g.attacks); labels=dict(g.labels)
    from af_semantics import grounded_extension
    before_E=grounded_extension(nodes, attacks); before="Accepted" if tgt in before_E else "Not accepted"
    edits=[]; rationale=[]; steps=0
    context=" ".join([p.text for p in ir.propositions][:5])
    while steps<budget:
        atks=attackers_of(attacks, tgt)
        if not atks: break
        UA=unattacked(attacks, atks); pool=UA or atks
        a=sorted(list(pool))[0]; attacker_label=labels.get(a,a)
        nid=f"c{len(nodes)+1}"; txt=propose_counter_for(attacker_label, context)
        nodes.add(nid); labels[nid]=f"counter:{txt}"; attacks.add((nid,a))
        edits.extend([Edit(kind="add_node", node_id=nid, node_label=labels[nid]),
                      Edit(kind="add_attack", edge=(nid,a))])
        rationale.append(f"Add counter to attacker '{a}': '{txt}'")
        steps+=1
        E=grounded_extension(nodes, attacks)
        if tgt in E:
            return Plan(edits, rationale, before, "Accepted", before_E, E)
    E=grounded_extension(nodes, attacks)
    return Plan(edits, rationale, before, ("Accepted" if tgt in E else "Not accepted"), before_E, E)
