# strengthener_cli.py
# -*- coding: utf-8 -*-
"""
One-parse Strengthener CLI (with optimal enforcement, strict-step certification, and context view).

New in this version:
  --context    Print a self-contained snapshot BEFORE planning:
               - Claims (id → text)
               - Inferences (from → to, rule/type/scheme, certified, FOL if any)
               - Obligations per inference (with plain-English legend)
               - Why no strict FOL was recognized (if applicable)
               - Attackers with human-readable labels

End-to-end flow:
  NL/Text/ARG-IR  → nl_to_argir  → (synth FOL) → (certify strict) → compile AF (+ waiver) → semantics → plan
"""

from __future__ import annotations
import argparse, json, os, pathlib, re
from typing import Optional, Iterable, Tuple, Dict, List
from dataclasses import asdict, is_dataclass

from nl_to_argir import nl_to_argir
from compile_to_af import compile_to_af, AFGraph, neg_id
from af_semantics import grounded_extension, status, attackers_of, unattacked
from enforcement_greedy import strengthen_within, strengthen_across
from enforcement_optimal import optimal_enforce
from pedagogy import explain_acceptance_delta
from arg_ir import load_argument_ir, ArgumentIR
from certify_strict import certify_strict_steps

# Prefer fol_synth.synth_fol; fallback to fol_from_nl.seed_fol_for_strict
_synth = None
_synth_name = "none"
try:
    from fol_synth import synth_fol as _synth
    _synth_name = "fol_synth.synth_fol"
except Exception:
    try:
        from fol_from_nl import seed_fol_for_strict as _synth
        _synth_name = "fol_from_nl.seed_fol_for_strict"
    except Exception:
        _synth = None

# ----------------- small helpers -----------------

def _pick_target(ir: ArgumentIR, hint: Optional[str]) -> str:
    if hint:
        ids = {p.id for p in ir.propositions}
        if hint in ids:
            return hint
        for p in ir.propositions:
            if hint.lower() in p.text.lower():
                return p.id
    return (ir.targets[0] if ir.targets else ir.propositions[-1].id)

def _obligation_legend() -> Dict[str, str]:
    return {
        # generic deductive/structural checks
        "premises_present": "List all premises explicitly (avoid hidden assumptions).",
        "rule_applicable": "State the warrant/rule and show its preconditions are satisfied.",
        "term_consistency": "Use key terms consistently or define them to remove ambiguity.",
        # practical/causal (appear in other examples)
        "means_lead_to_goal": "Explain how the proposed means actually achieves the stated goal (mechanism/evidence).",
        "side_effects_acceptable": "Address harms/downsides and justify that they are acceptable.",
        "better_alternative_absent": "Argue that there isn’t a clearly better alternative.",
        "mechanism": "Describe how the cause produces the effect (linking story).",
        "robustness": "Explain why the link holds across plausible variations.",
        "temporal_precedence": "Establish that the cause precedes the effect."
    }

def _explain_obligation_key(k: str) -> str:
    key = k.split(":")[-1] if ":" in k else k
    return _obligation_legend().get(key, "(no legend available)")

def _to_jsonable(obj):
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj

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
    with open(out, "w", encoding="utf-8") as f:
        json.dump(_to_jsonable(ir), f, ensure_ascii=False, indent=2)
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

def _iter_inputs(args) -> Iterable[Tuple[str, str]]:
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

# ----------------- AF helpers & context printing -----------------

def _surface(g: AFGraph, target: str, show_labels: bool = False):
    print("\n=== Attack Surface ===")
    print(f"Target: {target}")
    atks = sorted(list(attackers_of(g.attacks, target)))
    if atks:
        if show_labels:
            labeled = [f"{a} ({g.labels.get(a, a)})" for a in atks]
            print("Attackers:", labeled)
        else:
            print("Attackers:", atks)
    else:
        print("Attackers: ∅")
    ua = sorted(list(unattacked(g.attacks, set(atks))))
    print("Unattacked attackers:", ua or "∅")
    neg_t = neg_id(target)
    defenders = {a for (a, b) in g.attacks if b == neg_t}
    if show_labels:
        labeled_def = [f"{a} ({g.labels.get(a, a)})" for a in sorted(defenders)]
        print(f"Direct defenders of {target} (attack {neg_t}):", labeled_def or "∅")
    else:
        print(f"Direct defenders of {target} (attack {neg_t}):", sorted(defenders) or "∅")
    unmet = [n for n, lab in g.labels.items()
             if lab.startswith("CQ unmet:") or lab.startswith("Obligation unmet:")]
    if unmet:
        print("Unmet obligations:", sorted(unmet))

_NORMATIVE = re.compile(r'\b(should|ought|recommend|prohibit|allow|ban|mandate)\b', re.IGNORECASE)
_PROBABILISTIC = re.compile(r'\b(likely|probably|might|may|tends?|on average|most)\b', re.IGNORECASE)

def _why_no_strict_reason(conclusion_text: str) -> Optional[str]:
    txt = conclusion_text.strip()
    if _NORMATIVE.search(txt):
        return "Conclusion is normative/policy (contains 'should/ought' etc.), treated as defeasible."
    if _PROBABILISTIC.search(txt):
        return "Conclusion is probabilistic/inductive, outside the strict deductive catalog."
    return None

def _print_context(ir: ArgumentIR, g: AFGraph, target: str, show_legend: bool = True):
    print("\n=== Context (NL → ARG‑IR Snapshot) ===")
    # Claims
    print("\nClaims:")
    for p in ir.propositions:
        flag_tgt = "  [TARGET]" if p.id == target else ""
        print(f"  {p.id}: {p.text}{flag_tgt}")

    # Inferences
    print("\nInferences:")
    by_id = {p.id: p.text for p in ir.propositions}
    strict_count = 0
    for inf in ir.inferences:
        from_list = [f"{pid}: {by_id.get(pid, pid)}" for pid in inf.from_ids]
        to_txt = by_id.get(inf.to, inf.to)
        rule = getattr(inf, "rule", "defeasible")
        itype = getattr(inf, "type", None) or "-"
        scheme = getattr(inf, "scheme", None) or "-"
        certified = bool(getattr(inf, "certified", False) or
                         (getattr(inf, "meta", None) and isinstance(inf.meta, dict) and inf.meta.get("certified")))
        print(f"  {inf.id}:")
        print(f"    from: {', '.join(from_list) or '(none)'}")
        print(f"    to:   {inf.to}: {to_txt}")
        print(f"    rule/type/scheme: {rule} / {itype} / {scheme}   certified={certified}")
        fol = getattr(inf, "fol", None)
        if rule == "strict" and fol and getattr(fol, "conclusion", None):
            strict_count += 1
            try:
                print(f"    FOL premises: {list(fol.premises)}")
                print(f"    FOL conclusion: {fol.conclusion}")
            except Exception:
                pass
        # Obligations present in AF for this inference
        ob_nodes = sorted(n for n in g.nodes if n.startswith(f"cq:{inf.id}:") or n.startswith(f"ob:{inf.id}:"))
        if ob_nodes:
            print("    Obligations present:")
            for n in ob_nodes:
                key = n.split(":")[-1]
                print(f"      - {n} : { _explain_obligation_key(key) }")

    # If no strict for target's defender, say why (heuristic)
    ttxt = next((p.text for p in ir.propositions if p.id == target), "")
    reason = _why_no_strict_reason(ttxt)
    if reason:
        print("\nWhy no strict FOL was recognized (heuristic):")
        print(f"  - {reason}")
        print("  - Strict catalog currently covers: Syllogism, Chained Syllogism, Modus Ponens, Modus Tollens.")

    if show_legend:
        print("\nObligation legend (what the cq:* labels mean):")
        for k, v in _obligation_legend().items():
            print(f"  {k:>24} — {v}")

# ----------------- waiver for certified strict steps -----------------

def _waive_certified_obligations_in_graph(ir: ArgumentIR, g: AFGraph) -> AFGraph:
    """
    Remove CQ/obligation undercutters that target strict inferences proven (certified=True).
    """
    cert_ids = set()
    for inf in getattr(ir, "inferences", []):
        if getattr(inf, "rule", None) == "strict" and (
            getattr(inf, "certified", False) or
            (getattr(inf, "meta", None) and isinstance(inf.meta, dict) and inf.meta.get("certified"))
        ):
            cert_ids.add(inf.id)
    if not cert_ids:
        return g

    to_drop = set()
    for nid in list(g.nodes):
        for iid in cert_ids:
            if nid.startswith(f"cq:{iid}:") or nid.startswith(f"ob:{iid}:"):
                to_drop.add(nid)
                break

    if not to_drop:
        return g

    print("\n[debug] Waiving obligations for certified strict steps:")
    for n in sorted(to_drop):
        print("  -", n)

    g.nodes -= to_drop
    g.attacks = {(a, b) for (a, b) in g.attacks if a not in to_drop and b not in to_drop}
    for nid in to_drop:
        g.labels.pop(nid, None)
    return g

# ----------------- main run path -----------------

def _maybe_synthesize_fol(ir: ArgumentIR, enable: bool):
    if not enable:
        return
    if _synth is None:
        print("[warn] FOL synthesis not available (no fol_synth / fol_from_nl).")
        return
    print(f"[debug] FOL synthesis provider: {_synth_name}")
    _synth(ir)
    # Show strict steps with FOL so you can see what cert will use:
    found = 0
    for inf in ir.inferences:
        if inf.rule == "strict" and getattr(inf, "fol", None) and getattr(inf.fol, "conclusion", None):
            found += 1
            print("\n[debug] strict", inf.id, "scheme=", getattr(inf, "scheme", None))
            try:
                print("  premises:", list(inf.fol.premises))
                print("  conclusion:", inf.fol.conclusion)
            except Exception:
                pass
    if found == 0:
        print("[debug] No strict steps with FOL recognized after synthesis.")

def _run_one(ir: ArgumentIR, args, label: Optional[str] = None):
    # 1) FOL synth (explicit or auto under --e2e)
    _maybe_synthesize_fol(ir, enable=(args.synth_fol or args.e2e))

    # 2) Certification (explicit or auto under --e2e)
    if args.certify or args.e2e:
        res = certify_strict_steps(ir)
        if res:
            hdr = "=== Strict-step Certification (E2E) ===" if args.e2e else "=== Strict-step Certification ==="
            print("\n" + hdr)
            for r in res:
                print(f"{r.inference_id}: {r.tool} → {'OK' if r.ok else 'FAIL'}")

    # 3) Compile AF & initial status + waiver for certified strict
    tgt = _pick_target(ir, args.target)
    g = compile_to_af(ir, include_default_doubt=True, include_obligation_attackers=True, support_as_defense=True)
    g = _waive_certified_obligations_in_graph(ir, g)

    # 3b) Context (before planning), if requested
    if args.context:
        _print_context(ir, g, tgt, show_legend=True)

    # 4) Initial status
    print("\n=== Initial (Grounded) ===")
    print("Target id:", tgt)
    print("Target text:", next((p.text for p in ir.propositions if p.id == tgt), tgt))
    print("Status:", status(g.nodes, g.attacks, tgt))
    E0 = grounded_extension(g.nodes, g.attacks)
    print("Grounded extension size:", len(E0))
    _surface(g, tgt, show_labels=True)

    # 5) E2E prefers optimal; fallback to greedy
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
            for rline in plan.rationale:
                print("  *", rline)
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

    # 6) Greedy path (if not e2e or after fallback)
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

def main():
    ap = argparse.ArgumentParser(description="Argument Strengthener (one-parse) CLI")
    ap.add_argument("--text", type=str, help="Argument text")
    ap.add_argument("--file", type=str, help="Path to text file")
    ap.add_argument("--argir", type=str, help="Path to ARG-IR JSON file")
    ap.add_argument("--dir", type=str, help="Directory of inputs (.txt/.md for NL, .json for ARG-IR)")
    ap.add_argument("--auto", action="store_true", help="Placeholder flag (compatibility)")

    # New: context flag
    ap.add_argument("--context", action="store_true",
                    help="Print claims, inferences, obligations (with legend), "
                         "and a brief reason if no strict FOL was recognized.")

    # End-to-end flow switches
    ap.add_argument("--e2e", action="store_true",
                    help="End-to-end: synth-fol + certify strict steps + optimal enforcement (fallback to greedy).")
    ap.add_argument("--synth-fol", action="store_true",
                    help="Synthesize FOL for strict steps from NL (marks rule='strict' on success).")
    ap.add_argument("--certify", action="store_true",
                    help="Attempt E/Lean certificates for strict steps (updates obligations).")
    ap.add_argument("--optimal", action="store_true", help="Use clingo optimal enforcement.")

    # Greedy options
    ap.add_argument("--within-first", action="store_true",
                    help="Do within-link repairs before across-graph (greedy).")
    ap.add_argument("--budget", type=int, default=3, help="Max edit steps (for greedy).")

    ap.add_argument("--target", type=str, help="Target claim id or substring.")
    ap.add_argument("--dump-ir", type=str, help="Path to write ARG-IR JSON (file or directory).")
    args = ap.parse_args()

    if not (args.text or args.file or args.argir or args.dir):
        ap.error("Provide one of: --text  |  --file  |  --argir  |  --dir")

    for kind, payload in _iter_inputs(args):
        if kind == "argir":
            ir, label = _load_ir_from_argir(payload)
        elif kind == "nlfile":
            ir, label = _load_ir_from_text_or_file(None, payload)
        else:
            ir, label = _load_ir_from_text_or_file(payload, None)
        if args.dump_ir:
            _dump_ir(ir, args.dump_ir, src_path=label)
        _run_one(ir, args, label=label)

if __name__ == "__main__":
    main()
