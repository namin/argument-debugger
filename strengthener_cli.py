
# -*- coding: utf-8 -*-
"""
One-parse Strengthener CLI.

Pipeline:
  NL text --(LLM/heuristic)--> ARG-IR --(compiler)--> AF
    → report status, attack surface, unmet obligations
    → try within-link strengthening (answers to obligations) and/or across-graph counters
    → show certificates: grounded extension before/after

Reuse llm.py if present. No external deps.
"""

from __future__ import annotations
import argparse
from typing import Optional, Set, Tuple
from nl_to_argir import nl_to_argir
from compile_to_af import compile_to_af, AFGraph, neg_id
from af_semantics import grounded_extension, status, attackers_of, unattacked
from enforcement_greedy import strengthen_within, strengthen_across

def _pick_target(ir, hint: Optional[str]) -> str:
    if hint:
        # exact id
        ids = {p.id for p in ir.propositions}
        if hint in ids:
            return hint
        # substring match
        for p in ir.propositions:
            if hint.lower() in p.text.lower():
                return p.id
    return (ir.targets[0] if ir.targets else ir.propositions[-1].id)

def _surface(g: AFGraph, target: str):
    print("\n=== Attack Surface ===")
    print(f"Target: {target}")
    atks = attackers_of(g.attacks, target)
    print("Attackers:", sorted(list(atks)) or "∅")
    print("Unattacked attackers:", sorted(list(unattacked(g.attacks, atks))) or "∅")
    neg_t = neg_id(target)
    defenders = {a for (a, b) in g.attacks if b == neg_t}
    print(f"Direct defenders of {target} (attack {neg_t}):", sorted(list(defenders)) or "∅")
    # obligations
    unmet = [n for n, lab in g.labels.items() if lab.startswith("CQ unmet:") or lab.startswith("Obligation unmet:")]
    if unmet:
        print("Unmet obligations:", sorted(unmet))

def main():
    ap = argparse.ArgumentParser(description="Argument Strengthener (one-parse) CLI")
    ap.add_argument("--text", type=str, help="Argument text")
    ap.add_argument("--file", type=str, help="Path to text file")
    ap.add_argument("--target", type=str, help="Target claim id or substring")
    ap.add_argument("--budget", type=int, default=3, help="Max edit steps")
    ap.add_argument("--within-first", action="store_true", help="Do within-link repairs before across-graph")
    args = ap.parse_args()

    if not args.text and not args.file:
        ap.error("Provide --text or --file")

    text = args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()

    ir = nl_to_argir(text)
    tgt = _pick_target(ir, args.target)
    g = compile_to_af(ir, include_default_doubt=True, include_obligation_attackers=True, support_as_defense=True)

    print("\n=== Initial (Grounded) ===")
    print("Target id:", tgt)
    print("Target text:", next((p.text for p in ir.propositions if p.id == tgt), tgt))
    print("Status:", status(g.nodes, g.attacks, tgt))
    print("Grounded extension size:", len(grounded_extension(g.nodes, g.attacks)))
    _surface(g, tgt)

    # Strengthening
    remaining = args.budget
    if args.within_first:
        plan_w = strengthen_within(ir, tgt, g, remaining)
        print("\n--- Within-link Plan ---")
        print("Before:", plan_w.before_status, "After:", plan_w.after_status)
        for e in plan_w.edits:
            if e.kind == "add_node":
                print("  add node", e.node_id, ":", e.node_label)
            if e.kind == "add_attack" and e.edge:
                print("  add attack", e.edge[0], "->", e.edge[1])
        for r in plan_w.rationale:
            print("  *", r)
        used = sum(1 for e in plan_w.edits if e.kind == "add_attack")
        remaining = max(0, remaining - used)
        # apply to graph for next step
        for e in plan_w.edits:
            if e.kind == "add_node" and e.node_id:
                g.nodes.add(e.node_id); g.labels[e.node_id] = e.node_label or e.node_id
            if e.kind == "add_attack" and e.edge:
                g.attacks.add(e.edge)

        if remaining > 0 and status(g.nodes, g.attacks, tgt) != "Accepted":
            plan_a = strengthen_across(ir, tgt, g, remaining)
            print("\n--- Across-graph Plan ---")
            print("Before:", plan_a.before_status, "After:", plan_a.after_status)
            for e in plan_a.edits:
                if e.kind == "add_node":
                    print("  add node", e.node_id, ":", e.node_label)
                if e.kind == "add_attack" and e.edge:
                    print("  add attack", e.edge[0], "->", e.edge[1])
            for r in plan_a.rationale:
                print("  *", r)
    else:
        plan_a = strengthen_across(ir, tgt, g, remaining)
        print("\n--- Across-graph Plan ---")
        print("Before:", plan_a.before_status, "After:", plan_a.after_status)
        for e in plan_a.edits:
            if e.kind == "add_node":
                print("  add node", e.node_id, ":", e.node_label)
            if e.kind == "add_attack" and e.edge:
                print("  add attack", e.edge[0], "->", e.edge[1])
        for r in plan_a.rationale:
            print("  *", r)
        used = sum(1 for e in plan_a.edits if e.kind == "add_attack")
        remaining = max(0, remaining - used)
        for e in plan_a.edits:
            if e.kind == "add_node" and e.node_id:
                g.nodes.add(e.node_id); g.labels[e.node_id] = e.node_label or e.node_id
            if e.kind == "add_attack" and e.edge:
                g.attacks.add(e.edge)
        if remaining > 0 and status(g.nodes, g.attacks, tgt) != "Accepted":
            plan_w = strengthen_within(ir, tgt, g, remaining)
            print("\n--- Within-link Plan ---")
            print("Before:", plan_w.before_status, "After:", plan_w.after_status)
            for e in plan_w.edits:
                if e.kind == "add_node":
                    print("  add node", e.node_id, ":", e.node_label)
                if e.kind == "add_attack" and e.edge:
                    print("  add attack", e.edge[0], "->", e.edge[1])
            for r in plan_w.rationale:
                print("  *", r)

if __name__ == "__main__":
    main()
