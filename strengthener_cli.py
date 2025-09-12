# -*- coding: utf-8 -*-
"""
One-parse Strengthener CLI (with optimal enforcement and strict-step certification).

Pipeline:
  NL text or ARG-IR JSON
    → parse (LLM/heuristic) to ARG-IR
    → (optional) certify strict steps with E/Lean
    → compile to AF (with default-doubt & obligation undercutters)
    → report status and attack surface
    → (optional) optimal enforcement via clingo OR greedy strengthening
    → explain acceptance change

Usage examples:
  python strengthener_cli.py --text "A. B. Therefore C." --within-first --budget 3
  python strengthener_cli.py --argir examples/bus_fares_argir.json --optimal
  python strengthener_cli.py --file draft.txt --certify --optimal
  python strengthener_cli.py --file arguments_nl/01_syllogism_socrates.txt --e2e
"""

from __future__ import annotations
import argparse, json
from typing import Optional

from nl_to_argir import nl_to_argir
from compile_to_af import compile_to_af, AFGraph, neg_id
from af_semantics import grounded_extension, status, attackers_of, unattacked
from enforcement_greedy import strengthen_within, strengthen_across
from enforcement_optimal import optimal_enforce
from pedagogy import explain_acceptance_delta
from arg_ir import load_argument_ir
from certify_strict import certify_strict_steps

def _pick_target(ir, hint: Optional[str]) -> str:
    if hint:
        ids = {p.id for p in ir.propositions}
        if hint in ids:
            return hint
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
    unmet = [n for n, lab in g.labels.items() if lab.startswith("CQ unmet:") or lab.startswith("Obligation unmet:")]
    if unmet:
        print("Unmet obligations:", sorted(unmet))

def main():
    ap = argparse.ArgumentParser(description="Argument Strengthener (one-parse) CLI")
    ap.add_argument("--text", type=str, help="Argument text")
    ap.add_argument("--file", type=str, help="Path to text file")
    ap.add_argument("--argir", type=str, help="Path to ARG-IR JSON file")
    ap.add_argument("--target", type=str, help="Target claim id or substring")
    ap.add_argument("--budget", type=int, default=3, help="Max edit steps (for greedy)")
    ap.add_argument("--within-first", action="store_true", help="Do within-link repairs before across-graph (greedy)")
    ap.add_argument("--optimal", action="store_true", help="Use clingo optimal enforcement")
    ap.add_argument("--certify", action="store_true", help="Attempt E/Lean certificates for strict steps (updates obligations)")
    # NEW: end-to-end convenience flag
    ap.add_argument("--e2e", action="store_true",
                    help="End-to-end: certify strict steps, then optimal enforcement (fallback to greedy).")
    args = ap.parse_args()

    if not args.text and not args.file and not args.argir:
        ap.error("Provide --text or --file or --argir")

    # Load ARG-IR
    if args.argir:
        with open(args.argir, "r", encoding="utf-8") as f:
            data = json.load(f)
        ir = load_argument_ir(data)
    else:
        text = args.text
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        ir = nl_to_argir(text)

    # Certificates for strict steps (optional)
    if args.certify:
        res = certify_strict_steps(ir)
        if res:
            print("\n=== Strict-step Certification ===")
            for r in res:
                status_txt = "OK" if r.ok else "FAIL"
                print(f"{r.inference_id}: {r.tool} → {status_txt}")

    tgt = _pick_target(ir, args.target)
    g = compile_to_af(ir, include_default_doubt=True, include_obligation_attackers=True, support_as_defense=True)

    print("\n=== Initial (Grounded) ===")
    print("Target id:", tgt)
    print("Target text:", next((p.text for p in ir.propositions if p.id == tgt), tgt))
    print("Status:", status(g.nodes, g.attacks, tgt))
    E0 = grounded_extension(g.nodes, g.attacks)
    print("Grounded extension size:", len(E0))
    _surface(g, tgt)

    # NEW: E2E path (certify + optimal; fallback to greedy)
    if args.e2e:
        # If user didn't already ask for --certify, do it here so AF reflects proof results.
        if not args.certify:
            res = certify_strict_steps(ir)
            if res:
                print("\n=== Strict-step Certification (E2E) ===")
                for r in res:
                    print(f"{r.inference_id}: {r.tool} → {'OK' if r.ok else 'FAIL'}")
        # Recompile AF to reflect any obligation-status changes from certification
        g = compile_to_af(ir, include_default_doubt=True, include_obligation_attackers=True, support_as_defense=True)
        try:
            plan = optimal_enforce(ir, g, tgt)
            print("\n--- Optimal Plan (E2E) ---")
            print("Cost:", plan.cost, "Before:", plan.before_status, "After:", plan.after_status)
            for e in plan.edits:
                if e.kind == "add_node":
                    print("  add node", e.node_id, ":", e.node_label)
                if e.kind == "add_attack" and e.edge:
                    print("  add attack", e.edge[0], "->", e.edge[1])
            for r in plan.rationale:
                print("  *", r)
            # Apply edits so the explanation uses the updated graph
            for e in plan.edits:
                if e.kind == "add_node" and e.node_id:
                    g.nodes.add(e.node_id); g.labels[e.node_id] = e.node_label or e.node_id
                if e.kind == "add_attack" and e.edge:
                    g.attacks.add(e.edge)
            for line in explain_acceptance_delta(plan.before_extension, plan.after_extension, g.attacks, g.labels, tgt):
                print("   ", line)
            return
        except Exception as e:
            print("\n[warn] Optimal enforcement failed (likely clingo missing):", e)
            print("[warn] Falling back to greedy within-first (budget=max(3, --budget))")
            remaining = max(3, args.budget)
            plan_w = strengthen_within(ir, tgt, g, remaining)
            print("\n--- Within-link Plan (fallback) ---")
            print("Before:", plan_w.before_status, "After:", plan_w.after_status)
            for e in plan_w.edits:
                if e.kind == "add_node":
                    print("  add node", e.node_id, ":", e.node_label)
                if e.kind == "add_attack" and e.edge:
                    print("  add attack", e.edge[0], "->", e.edge[1])
            for r in plan_w.rationale:
                print("  *", r)
            for line in explain_acceptance_delta(plan_w.before_extension, plan_w.after_extension, g.attacks, g.labels, tgt):
                print("   ", line)
            return

    if args.optimal:
        plan = optimal_enforce(ir, g, tgt)
        print("\n--- Optimal Plan (clingo) ---")
        print("Cost:", plan.cost, "Before:", plan.before_status, "After:", plan.after_status)
        for e in plan.edits:
            if e.kind == "add_node":
                print("  add node", e.node_id, ":", e.node_label)
            if e.kind == "add_attack" and e.edge:
                print("  add attack", e.edge[0], "->", e.edge[1])
        for r in plan.rationale:
            print("  *", r)
        for line in explain_acceptance_delta(plan.before_extension, plan.after_extension, g.attacks, g.labels, tgt):
            print("   ", line)
        return

    # Greedy path
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
        for line in explain_acceptance_delta(plan_w.before_extension, plan_w.after_extension, g.attacks, g.labels, tgt):
            print("   ", line)
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
            for line in explain_acceptance_delta(plan_a.before_extension, plan_a.after_extension, g.attacks, g.labels, tgt):
                print("   ", line)
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
        for line in explain_acceptance_delta(plan_a.before_extension, plan_a.after_extension, g.attacks, g.labels, tgt):
            print("   ", line)
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
            for line in explain_acceptance_delta(plan_w.before_extension, plan_w.after_extension, g.attacks, g.labels, tgt):
                print("   ", line)

if __name__ == "__main__":
    main()
