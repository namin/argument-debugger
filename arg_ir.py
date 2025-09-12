
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import json

@dataclass
class Proposition:
    id: str
    text: str
    kind: str = "fact"
    polarity: str = "+"
    modality: str = "asserted"
    sources: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

@dataclass
class Obligation:
    id: str
    kind: str
    name: str
    status: str = "unknown"

@dataclass
class FOLPayload:
    premises: List[str] = field(default_factory=list)
    conclusion: str = ""
    symbols: Dict[str, str] = field(default_factory=dict)

@dataclass
class Inference:
    id: str
    from_ids: List[str]
    to: str
    rule: str = "defeasible"
    type: str = "deductive"
    scheme: Optional[str] = None
    warrant_text: Optional[str] = None
    backing_text: Optional[str] = None
    qualifier: Optional[str] = None
    rebuttals: List[str] = field(default_factory=list)
    obligations: List[Obligation] = field(default_factory=list)
    fol: Optional[FOLPayload] = None
    certificates: Dict[str, str] = field(default_factory=dict)

@dataclass
class Relation:
    type: str
    frm: str
    to: str

@dataclass
class ArgumentIR:
    propositions: List[Proposition]
    inferences: List[Inference]
    relations: List[Relation]
    targets: List[str] = field(default_factory=list)

def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False)

def _expect_str(x: Any, default: str = "") -> str:
    return str(x) if isinstance(x, (str, int, float)) else default

def load_argument_ir(obj: dict) -> ArgumentIR:
    if not isinstance(obj, dict):
        raise ValueError("ARG-IR must be a dict")
    props=[]
    for p in obj.get("propositions", []):
        if not isinstance(p, dict) or "id" not in p or "text" not in p:
            continue
        props.append(Proposition(
            id=_expect_str(p.get("id")), text=_expect_str(p.get("text")),
            kind=_expect_str(p.get("kind","fact")), polarity=_expect_str(p.get("polarity","+")),
            modality=_expect_str(p.get("modality","asserted")),
            sources=[_expect_str(s) for s in p.get("sources", [])],
            tags=[_expect_str(t) for t in p.get("tags", [])],
        ))
    infs=[]
    for i in obj.get("inferences", []):
        if not isinstance(i, dict) or "id" not in i or "from" not in i or "to" not in i:
            continue
        obs=[]
        for ob in i.get("obligations", []):
            if not isinstance(ob, dict) or "id" not in ob or "kind" not in ob or "name" not in ob:
                continue
            obs.append(Obligation(id=_expect_str(ob.get("id")), kind=_expect_str(ob.get("kind")), name=_expect_str(ob.get("name")), status=_expect_str(ob.get("status","unknown"))))
        fol_obj=i.get("fol")
        fol=None
        if isinstance(fol_obj, dict):
            fol=FOLPayload(
                premises=[_expect_str(s) for s in fol_obj.get("premises", [])],
                conclusion=_expect_str(fol_obj.get("conclusion","")),
                symbols={_expect_str(k): _expect_str(v) for k,v in fol_obj.get("symbols",{}).items()}
            )
        certs={}
        if isinstance(i.get("certificates"), dict):
            for k,v in i["certificates"].items():
                certs[_expect_str(k)]=_expect_str(v)
        infs.append(Inference(
            id=_expect_str(i.get("id")), from_ids=[_expect_str(x) for x in i.get("from", [])], to=_expect_str(i.get("to")),
            rule=_expect_str(i.get("rule","defeasible")), type=_expect_str(i.get("type","deductive")),
            scheme=(None if i.get("scheme") is None else _expect_str(i.get("scheme"))),
            warrant_text=(None if i.get("warrant_text") is None else _expect_str(i.get("warrant_text"))),
            backing_text=(None if i.get("backing_text") is None else _expect_str(i.get("backing_text"))),
            qualifier=(None if i.get("qualifier") is None else _expect_str(i.get("qualifier"))),
            rebuttals=[_expect_str(x) for x in i.get("rebuttals", [])],
            obligations=obs, fol=fol, certificates=certs
        ))
    rels=[]
    for r in obj.get("relations", []):
        if not isinstance(r, dict) or "type" not in r or "from" not in r or "to" not in r:
            continue
        t=_expect_str(r.get("type"))
        if t not in ("supports","rebuts","undermines","undercuts","attacks"):
            t="attacks"
        rels.append(Relation(type=t, frm=_expect_str(r.get("from")), to=_expect_str(r.get("to"))))
    targets=[_expect_str(x) for x in obj.get("targets", [])]
    if not props: raise ValueError("No propositions")
    return ArgumentIR(propositions=props, inferences=infs, relations=rels, targets=targets)
