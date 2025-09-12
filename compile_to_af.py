
from dataclasses import dataclass
from typing import Set, Tuple, Dict, List
from arg_ir import ArgumentIR

def neg_id(pid: str) -> str:
    return f"neg:{pid}"

def port_target_to_node(target: str) -> str:
    return target.split('#',1)[0] if '#' in target else target

@dataclass
class AFGraph:
    nodes: Set[str]
    attacks: Set[Tuple[str,str]]
    labels: Dict[str,str]
    meta: Dict[str,List[Tuple[str,str]]]

def compile_to_af(ir: ArgumentIR, include_default_doubt=True, include_obligation_attackers=True, support_as_defense=True) -> AFGraph:
    nodes=set(); attacks=set(); labels={}; supports=[]
    for p in ir.propositions:
        nodes.add(p.id); labels[p.id]=p.text
        if include_default_doubt:
            nid=neg_id(p.id); nodes.add(nid); labels[nid]=f"default doubt of {p.id}"; attacks.add((nid,p.id))
    for i in ir.inferences:
        nodes.add(i.id)
        srcs=", ".join(i.from_ids) if i.from_ids else "∅"
        labels[i.id]=f"{i.type}:{i.scheme or ''} [{srcs} ⇒ {i.to}]".strip()
    for r in ir.relations:
        if r.type=="supports":
            supports.append((r.frm,r.to))
        elif r.type in ("rebuts","undermines","undercuts","attacks"):
            attacks.add((r.frm, port_target_to_node(r.to)))
    if support_as_defense:
        for (i,p) in supports:
            attacks.add((i, neg_id(p)))
    if include_obligation_attackers:
        for i in ir.inferences:
            for ob in i.obligations:
                if ob.status!="met":
                    nid=f"{'cq' if ob.kind=='CQ' else 'ob'}:{i.id}:{ob.name}"
                    nodes.add(nid); labels[nid]=f"{ob.kind} unmet: {ob.name} (for {i.id})"; attacks.add((nid,i.id))
    return AFGraph(nodes=nodes, attacks=attacks, labels=labels, meta={"supports": supports})
