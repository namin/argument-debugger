# -*- coding: utf-8 -*-
"""
One-parse Strengthener CLI (with optimal enforcement and strict-step certification).

Pipeline:
  NL text or ARG-IR JSON
    → parse (LLM/heuristic) to ARG-IR
    → (optional) synthesize FOL for strict steps from NL (--synth-fol or --e2e)
    → (optional) certify strict steps with E/Lean
    → compile to AF (with default-doubt & obligation undercutters)
    → report status and attack surface
    → (optional) optimal enforcement via clingo OR greedy strengthening
    → explain acceptance change

Examples:
  python -B strengthener_cli.py --text "A. B. Therefore C." --within-first --budget 3
  python -B strengthener_cli.py --argir examples/bus_fares_argir.json --optimal
  python -B strengthener_cli.py --file arguments_nl/01_syllogism_socrates.txt --e2e
  python -B strengthener_cli.py --dir arguments_nl --e2e --synth-fol --dump-ir out/
"""

from __future__ import annotations
import argparse, json, os, pathlib
from typing import Optional, Iterable, Tuple
from dataclasses import asdict, is_dataclass

from nl_to_argir import nl_to_argir
from compile_to_af import compile_to_af, AFGraph, neg_id
from af_semantics import grounded_extension, status, attackers_of, unattacked
from enforcement_greedy import strengthen_within, strengthen_across
from enforcement_optimal import optimal_enforce
from pedagogy import explain_acceptance_delta
from arg_ir import load_argument_ir, ArgumentIR
from certify_strict import certify_strict_steps

# Optional FOL synthesizer
_synth = None
try:
    # Prefer explicit synthesizer if available
    from fol_synth import synth_fol as _synth
except Exception:
    try:
        # Fallback to the simple seeder (may require rule='strict' already)
        from fol_from_nl import seed_fol_for_strict as _synth
    except Exception:
        _synth = None

def _pick_target(ir: ArgumentIR, hint: Optional[str]) -> str:
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

def _dump_ir(ir: ArgumentIR, dest: Optional[str], src_path: Optional[str] = None):
    if not dest:
        return
    path = pathlib.Path(dest)
    if path.suffix.lower() == ".json" and (not path.exists() or path.is_file()):
        out = path
    else:
        outdir = path
        outdir.mkdir(parents=True, exist_ok=True)
        base = "ir"
        if src_path:
            base = pathlib.Path(src_path).stem
        out = outdir / f"{base}.argir.json"
    # dataclasses → dict
    def to_jsonable(obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, (list, tuple)):
            return [to_jsonable(x) for x in obj]
        if isinstance(obj, dict):
            return {k: to_jsonable(v) for k, v in obj.items()}
        return obj
    with open(out, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(ir), f, ensure_ascii=False, indent=2)
    print(f"[saved] ARG-IR → {out}")

def _load_ir_from_text_or_file(text: Optional[str], file_path: Optional[str]) -> Tuple[ArgumentIR, Optional[str]]:
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        ir = nl_to_argir(text)
        return ir, file_path
    assert text is not None
    return nl_to_argir(text), None

def _load_ir_from_argir(argir_path: str) -> Tuple[ArgumentIR, Optional[str]]:
    with open(argir_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_argument_ir(data), argir_path

def _run_one(ir: ArgumentIR, args, label: Optional[str] = None):
    # Optionally synthesize FOL (also auto-run when --e2e is used)
    if args.synth_fol or args.e2e:
        if _synth is not None:
            _synth(ir)
        else:
            print("[warn] --synth-fol requested but no fol_synth/fol_from_nl available.")

    # Optionally certify strict steps
    if args.certify or args.e2e:
        res = certify_strict_steps(ir)
        if res:
            hdr = "=== Strict-step Certification (E2E) ===" if args.e2e else "=== Strict-step Certification ==="
            print("\n" + hdr)
            for r in res:
                print(f"{r.inference_id}: {r.tool} → {'OK' if r.ok else 'FAIL'}")

    # Compile AF & initial status
    tgt = _pick_target(ir, args.target)
    g = compile_to_af(ir, include_default_doubt=True, include_obligation_attackers=True, support_as_defense=True)

    print("\n=== Initial (Grounded) ===")
    print("Target id:", tgt)
    print("Target text:", next((p.text for p in ir.propositions if p.id == tgt), tgt))
    print("Status:", status(g.nodes, g.attacks, tgt))
    E0 = grounded_extension(g.nodes, g.attacks)
    print("Grounded extension size:", len(E0))
    _surface(g, tgt)

    # End-to-end path prefers optimal; fallback to greedy
    if args.e2e:
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
            # Apply edits so explanation uses updated graph
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
            args.within_first = True
            args.budget = max(3, args.budget)

    # If not e2e or after fallback: Greedy
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
        # apply to graph
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

def _iter_inputs(args) -> Iterable[Tuple[str,str]]:
    """Yield (kind, path_or_text) for each input to process."""
    if args.dir:
        d = pathlib.Path(args.dir)
        for p in sorted(d.glob("*")):
            if p.suffix.lower() == ".json":
                yield ("argir", str(p))
            elif p.suffix.lower() in (".txt", ".md"):
                yield ("nlfile", str(p))
        return
    if args.argir:
        yield ("argir", args.argir)
    elif args.file:
        yield ("nlfile", args.file)
    else:
        yield ("nltext", args.text)

def main():
    ap = argparse.ArgumentParser(description="Argument Strengthener (one-parse) CLI")
    # Inputs
    ap.add_argument("--text", type=str, help="Argument text")
    ap.add_argument("--file", type=str, help="Path to text file")
    ap.add_argument("--argir", type=str, help="Path to ARG-IR JSON file")
    ap.add_argument("--dir", type=str, help="Directory of inputs (.txt/.md for NL, .json for ARG-IR)")
    ap.add_argument("--auto", action="store_true", help="Placeholder flag (kept for compatibility)")
    # Flow control
    ap.add_argument("--e2e", action="store_true",
                    help="End-to-end: synth-fol (if available) + certify strict steps + optimal enforcement (fallback to greedy).")
    ap.add_argument("--synth-fol", action="store_true",
                    help="Try to synthesize FOL for strict steps from NL (and mark rule='strict' on success).")
    ap.add_argument("--certify", action="store_true",
                    help="Attempt E/Lean certificates for strict steps (updates obligations)")
    ap.add_argument("--optimal", action="store_true", help="Use clingo optimal enforcement")
    ap.add_argument("--within-first", action="store_true", help="Do within-link repairs before across-graph (greedy)")
    ap.add_argument("--budget", type=int, default=3, help="Max edit steps (for greedy)")
    ap.add_argument("--target", type=str, help="Target claim id or substring")
    ap.add_argument("--dump-ir", type=str, help="Path to write ARG-IR JSON (file or directory).")
    args = ap.parse_args()

    if not (args.text or args.file or args.argir or args.dir):
        ap.error("Provide one of: --text  |  --file  |  --argir  |  --dir")

    # Process possibly multiple inputs (dir or single)
    for kind, payload in _iter_inputs(args):
        label = None
        if kind == "argir":
            ir, label = _load_ir_from_argir(payload)
        elif kind == "nlfile":
            ir, label = _load_ir_from_text_or_file(None, payload)
        else:
            ir, label = _load_ir_from_text_or_file(payload, None)

        if args.dump_ir:
            _dump_ir(ir, args.dump_ir, src_path=label)

        # Fast path: if user explicitly asked for only optimal/greedy/certify flows
        _run_one(ir, args, label=label)

if __name__ == "__main__":
    main()
