
# -*- coding: utf-8 -*-
"""
Strict-step certification:
- For inferences with rule="strict" and a FOL payload, attempt E prover.
- If successful, mark deductive obligations as met and attach a certificate.
- Lean hook is included but disabled by default (environment-dependent).

This module is robust: if E or Lean aren't available, it degrades gracefully.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import shutil, subprocess, tempfile, os

from arg_ir import ArgumentIR, Inference, Obligation, FOLPayload
from tptp_utils import make_tptp_problem

@dataclass
class CertResult:
    inference_id: str
    tool: str                 # "eprover" | "lean" | "none"
    ok: bool
    details: str

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def _try_eprover(fol: FOLPayload, name: str = "prob") -> CertResult:
    if not _have("eprover"):
        return CertResult(name, "eprover", False, "eprover not found in PATH")
    tptp = make_tptp_problem(fol, name_prefix=name)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, f"{name}.p")
        with open(path, "w", encoding="utf-8") as f:
            f.write(tptp)
        try:
            # --auto selects strategy; --cpu-limit short to return quickly
            proc = subprocess.run(
                ["eprover", "--auto", "--cpu-limit=5", path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
            )
            out = proc.stdout + "\n" + proc.stderr
            ok = "SZS status Theorem" in out or "SZS status Unsatisfiable" in out
            return CertResult(name, "eprover", ok, out if ok else out[-4000:])
        except Exception as e:
            return CertResult(name, "eprover", False, f"eprover error: {e}")

def _try_lean_stub(fol: FOLPayload, name: str = "prob") -> CertResult:
    # Placeholder; real Lean integration depends on project setup.
    return CertResult(name, "lean", False, "Lean integration not configured")

def _mark_deductive_met(inf: Inference) -> None:
    for ob in inf.obligations:
        if ob.kind.lower().startswith("ded") or ob.name in ("premises_present","rule_applicable","term_consistency"):
            ob.status = "met"

def certify_strict_steps(ir: ArgumentIR, prefer: str = "eprover") -> List[CertResult]:
    results: List[CertResult] = []
    for inf in ir.inferences:
        if inf.rule != "strict" or inf.fol is None or not inf.fol.conclusion:
            continue
        # attempt E first
        res = _try_eprover(inf.fol, name=inf.id) if prefer == "eprover" else _try_lean_stub(inf.fol, name=inf.id)
        results.append(res)
        if res.ok:
            # record certificate payload
            inf.certificates[res.tool] = f"OK: {res.tool} proof available (see details)"
            _mark_deductive_met(inf)
        else:
            inf.certificates[res.tool] = f"FAILED: {res.details[:500]}"
    return results
