# certify_strict.py
# -*- coding: utf-8 -*-
"""
Strict-step certification: try E prover on each inference with rule='strict' and a FOL payload.
Returns a list of CertReport objects printed by the CLI like:

=== Strict-step Certification (E2E) ===
i1: eprover → OK
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List
import os, shutil, subprocess, tempfile, pathlib

from arg_ir import ArgumentIR
from tptp_emit import make_tptp_problem

@dataclass
class CertReport:
    inference_id: str
    tool: str
    ok: bool
    info: str = ""

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def _prove_with_e(premises: List[str], conclusion: str, name: str) -> CertReport:
    if not _have("eprover"):
        return CertReport(name, "eprover", False, "eprover not found in PATH")
    tptp = make_tptp_problem(premises, conclusion, name_prefix=name)
    # Optionally save the TPTP file for inspection if CERT_OUTDIR is set
    save_dir = os.environ.get("CERT_OUTDIR")
    if save_dir:
        pathlib.Path(save_dir).mkdir(parents=True, exist_ok=True)
        with open(os.path.join(save_dir, f"{name}.p"), "w", encoding="utf-8") as f:
            f.write(tptp)
    with tempfile.NamedTemporaryFile("w", suffix=".p", delete=False, encoding="utf-8") as tmp:
        tmp.write(tptp); tmp_path = tmp.name
    try:
        # Ask E to solve; accept either stdout or stderr containing SZS status
        proc = subprocess.run(
            ["eprover", "--auto", "--cpu-limit=5", tmp_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        ok = ("SZS status Theorem" in out) or ("SZS status Unsatisfiable" in out)
        return CertReport(name, "eprover", ok, "OK" if ok else out.strip()[:500])
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

def certify_strict_steps(ir: ArgumentIR) -> List[CertReport]:
    reports: List[CertReport] = []
    # Iterate all inferences; certify those that look strict with a FOL payload
    for inf in getattr(ir, "inferences", []):
        if getattr(inf, "rule", None) != "strict":
            continue
        fol = getattr(inf, "fol", None)
        if not fol or not getattr(fol, "conclusion", None):
            continue
        # Expect fol.premises is a list[str]
        premises = list(getattr(fol, "premises", []))
        conclusion = getattr(fol, "conclusion", "")
        rep = _prove_with_e(premises, conclusion, name=inf.id)
        reports.append(rep)

        # If proof OK, mark the inference as certified so AF obligations can be relaxed
        if rep.ok:
            # Set a conventional flag many compilers use; harmless if unused
            try:
                # attach marker
                setattr(inf, "certified", True)
                if getattr(inf, "meta", None) is not None and isinstance(inf.meta, dict):
                    inf.meta["certified"] = True
            except Exception:
                pass
    return reports
