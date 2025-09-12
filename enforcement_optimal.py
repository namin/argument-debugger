
# -*- coding: utf-8 -*-
"""
Optimal (cost-minimal) enforcement using clingo.

We generate a set of candidate edits:
  - within-link answers for unmet obligations (CQ/DeductiveCheck) that attack an inference `d`
    which directly defends the target (i.e., d -> neg:target).
  - across-graph counters to attack each attacker of the target.

We let clingo choose a minimal-cost subset; we then validate acceptance in Python
(grounded semantics). If none of the optimal subsets succeed, we increase the cost bound.

Requires `clingo` on PATH. Falls back is not provided here (use greedy module if needed).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Set
import json, shutil, subprocess, tempfile, os, re

from arg_ir import ArgumentIR
from compile_to_af import AFGraph, neg_id
from af_semantics import grounded_extension, status, attackers_of, unattacked

@dataclass
class EditSpec:
    kind: str     # "answer" | "counter"
    key: str      # e.g., "cq:i1:means_lead_to_goal" or "neg:p6" attacker id
    desc: str     # human label
    id: str       # ASP-safe id token

@dataclass
class Edit:
    kind: str
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
    cost: int

def _safe(sym: str) -> str:
    # Make an ASP-safe identifier
    s = re.sub(r'[^a-zA-Z0-9_]', '_', sym)
    if not re.match(r'[a-zA-Z_]', s):
        s = "x_" + s
    return s

def _collect_candidates(g: AFGraph, target: str) -> Tuple[List[EditSpec], Dict[str,str]]:
    specs: List[EditSpec] = []
    labels = g.labels
    # Within: obligations attacking defenders of target
    neg_t = neg_id(target)
    defenders = {a for (a,b) in g.attacks if b == neg_t}
    for (a,b) in g.attacks:
        if a.startswith("cq:") or a.startswith("ob:"):
            if b in defenders:
                specs.append(EditSpec(kind="answer", key=a, desc=labels.get(a,a), id=_safe("ans__"+a)))
    # Across: attackers of target
    for a in attackers_of(g.attacks, target):
        specs.append(EditSpec(kind="counter", key=a, desc=labels.get(a,a), id=_safe("cnt__"+a)))
    return specs, labels

_ASP_ENCODING = r"""
% Candidates
cand(answer,ID) :- cand_id(ID), cand_type(ID,answer).
cand(counter,ID) :- cand_id(ID), cand_type(ID,counter).

% Choice of edits
{ choose(ID) : cand_id(ID) }.

% Cost: each chosen edit costs 1 (customize if needed)
cost(1,ID) :- choose(ID).

#minimize { 1,ID : choose(ID) }.

#show choose/1.
"""

def _write_facts(specs: List[EditSpec], dirpath: str) -> str:
    fpath = os.path.join(dirpath, "facts.lp")
    with open(fpath, "w", encoding="utf-8") as f:
        for s in specs:
            f.write(f"cand_id({s.id}). cand_type({s.id},{s.kind}).\n")
    return fpath

def _run_clingo(encoding: str, facts_file: str, optN: bool = True) -> List[List[str]]:
    if shutil.which("clingo") is None:
        raise RuntimeError("clingo not found on PATH")
    with tempfile.NamedTemporaryFile("w", suffix=".lp", delete=False) as enc:
        enc.write(encoding)
        enc_path = enc.name
    try:
        cmd = ["clingo", enc_path, facts_file, "-n", "0", "--outf=2"]
        if optN:
            cmd.append("--opt-mode=optN")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if proc.returncode not in (0,10,30):
            raise RuntimeError(f"clingo error: {proc.stderr}")
        data = json.loads(proc.stdout)
        models = []
        for call in data.get("Call", []):
            for w in call.get("Witnesses", []):
                atoms = w.get("Value", [])
                chosen = []
                for a in atoms:
                    if a.startswith("choose(") and a.endswith(")"):
                        inside = a[len("choose("):-1]
                        chosen.append(inside)
                models.append(chosen)
        return models
    finally:
        try:
            os.remove(enc_path)
        except Exception:
            pass

def optimal_enforce(ir: ArgumentIR, g: AFGraph, target: str, prefer_within_first: bool = True) -> Plan:
    specs, labels = _collect_candidates(g, target)
    before_E = grounded_extension(g.nodes, g.attacks)
    before_status = "Accepted" if target in before_E else "Not accepted"

    if not specs:
        return Plan([], ["No candidate edits found."], before_status, before_status, before_E, before_E, cost=0)

    with tempfile.TemporaryDirectory() as d:
        facts = _write_facts(specs, d)
        models = _run_clingo(_ASP_ENCODING, facts, optN=True)  # all optimal subsets
        # Evaluate each optimal model; pick the first that yields acceptance
        for chosen in models:
            # apply chosen edits
            nodes, attacks = set(g.nodes), set(g.attacks)
            edits: List[Edit] = []
            rationale: List[str] = []
            for cid in chosen:
                spec = next(s for s in specs if s.id == cid)
                if spec.kind == "answer":
                    nid = f"{cid}_node"
                    nodes.add(nid); 
                    lab = f"answer:{spec.desc}"
                    attacks.add((nid, spec.key))
                    edits.append(Edit(kind="add_node", node_id=nid, node_label=lab))
                    edits.append(Edit(kind="add_attack", edge=(nid, spec.key)))
                    rationale.append(f"Answer obligation '{spec.key}': '{spec.desc}'")
                elif spec.kind == "counter":
                    nid = f"{cid}_node"
                    nodes.add(nid);
                    lab = f"counter:{labels.get(spec.key,spec.key)}"
                    attacks.add((nid, spec.key))
                    edits.append(Edit(kind="add_node", node_id=nid, node_label=lab))
                    edits.append(Edit(kind="add_attack", edge=(nid, spec.key)))
                    rationale.append(f"Counter attacker '{spec.key}': '{labels.get(spec.key,spec.key)}'")
            E = grounded_extension(nodes, attacks)
            if target in E:
                return Plan(edits, rationale, before_status, "Accepted", before_E, E, cost=len(chosen))
        # If none of the optimal subsets validate, try next-cost subsets by relaxing minimize
        # Do iterative deepening by enforcing exactly k choices
        for k in range(1, len(specs)+1):
            enc = _ASP_ENCODING + f"\n:- #count{{ID: choose(ID)}} != {k}.\n"
            models = _run_clingo(enc, facts, optN=False)
            for chosen in models:
                nodes, attacks = set(g.nodes), set(g.attacks)
                edits: List[Edit] = []
                rationale: List[str] = []
                for cid in chosen:
                    spec = next(s for s in specs if s.id == cid)
                    if spec.kind == "answer":
                        nid = f"{cid}_node"; nodes.add(nid)
                        lab = f"answer:{spec.desc}"
                        attacks.add((nid, spec.key))
                        edits.append(Edit(kind="add_node", node_id=nid, node_label=lab))
                        edits.append(Edit(kind="add_attack", edge=(nid, spec.key)))
                        rationale.append(f"Answer obligation '{spec.key}': '{spec.desc}'")
                    else:
                        nid = f"{cid}_node"; nodes.add(nid)
                        lab = f"counter:{labels.get(spec.key,spec.key)}"
                        attacks.add((nid, spec.key))
                        edits.append(Edit(kind="add_node", node_id=nid, node_label=lab))
                        edits.append(Edit(kind="add_attack", edge=(nid, spec.key)))
                        rationale.append(f"Counter attacker '{spec.key}': '{labels.get(spec.key,spec.key)}'")
                E = grounded_extension(nodes, attacks)
                if target in E:
                    return Plan(edits, rationale, before_status, "Accepted", before_E, E, cost=len(chosen))
        # No plan found
        return Plan([], ["No edit subset achieved acceptance."], before_status, before_status, before_E, before_E, cost=0)
