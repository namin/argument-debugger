from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import subprocess, tempfile, os, re, shutil

# =============================================================================
# E prover wrapper with compact / cleaned proofs and optional digest
# =============================================================================

@dataclass
class EProverResult:
    status: str                 # e.g., 'Theorem', 'Unsatisfiable', 'Satisfiable', 'CounterSatisfiable', 'Unknown', 'Timeout', 'Error'
    proof_tstp: Optional[str]   # compact/cleaned TSTP between 'SZS output start' and 'SZS output end', if any
    used_axioms: Optional[List[str]]  # heuristic extraction from proof, if present
    stdout: str                 # raw stdout from the final tool in the pipeline
    stderr: str                 # raw stderr from the final tool in the pipeline
    exit_code: int
    # New (optional) field with a human-readable summary when recognizable (e.g., UI+MP)
    proof_digest: Optional[str] = None

# ------------------------- Utilities: parsing & cleaning ----------------------

def _parse_szs(text: str) -> str:
    """Extract SZS status from E/epclextract output."""
    m = re.search(r"SZS status\s+([A-Za-z_]+)", text)
    return m.group(1) if m else 'Unknown'

def _extract_proof_block(text: str) -> Optional[str]:
    """
    Extract proof text between SZS markers. Handles '# SZS output end' and 'SZS output end'.
    """
    m = re.search(r"SZS output start[^\n]*\n(.*?)#?\s*SZS output end", text, flags=re.S)
    return m.group(1).strip() if m else None

def _extract_used_axioms_from_proof(proof: str) -> List[str]:
    """Heuristic extraction of input axiom names from a TSTP proof block."""
    names = set()
    # fof(name, axiom, ...).
    for m in re.finditer(r"\bfof\(([^,]+),\s*axiom", proof):
        names.add(m.group(1))
    # input_clause(name, ...)
    for m in re.finditer(r"\binput_clause\(([^,]+),", proof):
        names.add(m.group(1))
    return sorted(names)

def _clean_tstp(proof: str) -> str:
    """
    Make TSTP less noisy:
      - strip file(...) annotations
      - drop [status(...)] tags inside inference metadata
      - normalize whitespace a bit
    """
    s = proof
    # Remove trailing ", file('...')" occurrences inside fof/cnf lines
    s = re.sub(r",\s*file\([^)]*\)", "", s)
    # Remove [status(...)] occurrences
    s = re.sub(r"\[status\([^)]*\)\]", "[]", s)
    # Collapse multiple spaces
    s = re.sub(r"[ \t]+", " ", s)
    # Trim lines
    s = "\n".join(line.rstrip() for line in s.splitlines())
    return s.strip()

def _digest_refutation_ui_mp(proof_tstp: str) -> Optional[str]:
    """
    Try to summarize the classic UI+MP refutation:
      ∀x (L(x) -> R(x)), L(c); assume ~R(c); resolve to ⊥.
    Return a short textual digest if recognizable, else None.
    """
    # Collect CNF clauses: name -> (role, body)
    clause_re = re.compile(r"^cnf\(([^,]+),\s*([^,]+),\s*\((.*?)\)\s*,", re.M)
    clauses = {m.group(1): (m.group(2).strip(), m.group(3).strip())
               for m in clause_re.finditer(proof_tstp)}
    if not clauses:
        return None

    # Find: negated goal (~R(c)), universal clause (R(X) | ~L(X)) or (can_fly(X)|~bird(X)),
    # and instance L(c)
    neg = next((b for r, b in clauses.values()
                if r == "negated_conjecture" and b.replace(" ", "").startswith("~")), None)

    # A unit instance like bird(penguin)
    inst = next((b for r, b in clauses.values()
                 if r in {"plain", "axiom"} and re.fullmatch(r"[a-z]\w*\([a-z]\w*\)", b.replace(" ", ""))), None)

    # A disjunction like R(X1) | ~L(X1)
    impl = next((b for r, b in clauses.values()
                 if r in {"plain", "axiom"} and "|" in b and
                 re.fullmatch(r"[a-z]\w*\(X\d+\)\s*\|\s*~[a-z]\w*\(X\d+\)", b.replace(" ", ""))), None)

    if not (neg and inst and impl):
        return None

    # Parse out predicate and constant names
    m1 = re.match(r"~([a-z]\w*)\(([a-z]\w*)\)", neg.replace(" ", ""))
    m2 = re.match(r"([a-z]\w*)\(X\d+\)\s*\|\s*~([a-z]\w*)\(X\d+\)", impl.replace(" ", ""))
    m3 = re.match(r"([a-z]\w*)\(([a-z]\w*)\)", inst.replace(" ", ""))

    if not (m1 and m2 and m3):
        return None

    pred_R, c1 = m1.group(1), m1.group(2)
    pred_R_impl, pred_L_impl = m2.group(1), m2.group(2)
    pred_L_inst, c2 = m3.group(1), m3.group(2)

    if not (pred_R == pred_R_impl and pred_L_inst == pred_L_impl and c1 == c2):
        return None

    # Build digest
    return (
        "Proof digest (Universal Instantiation + Modus Ponens):\n"
        f"  1) From ∀x({pred_L_impl}(x) ⇒ {pred_R}(x)) → clausify to ({pred_R}(X) ∨ ¬{pred_L_impl}(X)).\n"
        f"  2) Premise: {pred_L_impl}({c1}).\n"
        f"  3) Negate goal: ¬{pred_R}({c1}).\n"
        f"  4) Resolve (3) with (1) to get ¬{pred_L_impl}({c1}); resolve with (2) to reach ⊥.\n"
        f"Therefore, {pred_R}({c1}) holds."
    )

# --------------------------- Main entry: prover call --------------------------

def prove_with_e(
    tptp_text: str, *,
    e_path: str = "eprover",
    cpu_limit: int = 5,
    extra_args: Optional[list] = None,
    want_proof: bool = True,
    # New tuning knobs:
    compact: bool = True,        # prefer compact proof via epclextract if available
    output_level: int = 2,       # 2 is usually enough; 3 is chattier
    want_digest: bool = True     # attempt a short human-readable summary when possible
) -> EProverResult:
    """
    Run E prover on a TPTP string and return a compact/clean proof if requested.

    Pipeline:
      A) If compact=True and 'epclextract' is available:
         eprover --auto --cpu-limit --proof-object -l 3  (PCL protocol)
         | epclextract --tstp-out --competition-framing --silent  (clean TSTP)
      B) else:
         eprover --auto --cpu-limit --tstp-format --proof-object -l <output_level>
      If no proof found and 'eproof' exists, try:
         eproof --auto --cpu-limit -l 3 --tstp-out
    """
    # Check availability
    if shutil.which(e_path) is None:
        return EProverResult(
            status="Error",
            proof_tstp=None,
            used_axioms=None,
            stdout="",
            stderr=(
                f"E prover not found at '{e_path}'. "
                "Install with: brew install eprover (macOS) or apt-get install eprover (Linux)"
            ),
            exit_code=127,
            proof_digest=None
        )

    # Write problem to a temporary file
    with tempfile.NamedTemporaryFile("w", suffix=".p", delete=False) as f:
        f.write(tptp_text)
        tmp_path = f.name

    try:
        # Helper to run a command; keep text I/O
        def _run(cmd, *, input_str=None):
            return subprocess.run(cmd, input=input_str, capture_output=True, text=True)

        proof_tstp: Optional[str] = None
        stdout_final = ""
        stderr_final = ""
        status = "Unknown"
        exit_code = 0

        # -------- Attempt A: Compact pipeline with epclextract --------
        if want_proof and compact and shutil.which("epclextract") is not None:
            # Produce a full PCL protocol (no --tstp-format); level 3 is safer for extraction
            cmd_pcl = [e_path, "--auto", f"--cpu-limit={cpu_limit}", "--proof-object", "-l", "3", tmp_path]
            if extra_args:
                cmd_pcl[1:1] = list(extra_args)  # after e_path so --auto stays first
            proc_pcl = _run(cmd_pcl)
            pcl_out = proc_pcl.stdout
            pcl_err = proc_pcl.stderr
            # Convert to compact TSTP with framing markers
            cmd_extract = ["epclextract", "--tstp-out", "--competition-framing", "--silent"]
            proc_ext = _run(cmd_extract, input_str=pcl_out)
            stdout_final = proc_ext.stdout or pcl_out
            stderr_final = proc_ext.stderr or pcl_err
            exit_code = proc_pcl.returncode if proc_ext.returncode == 0 else proc_ext.returncode

            status = _parse_szs(stdout_final) or _parse_szs(stderr_final)
            proof = _extract_proof_block(stdout_final) or _extract_proof_block(stderr_final)
            if proof:
                proof_tstp = _clean_tstp(proof)

        # -------- Attempt B: Direct TSTP from eprover --------
        if want_proof and proof_tstp is None:
            cmd = [e_path, "--auto", f"--cpu-limit={cpu_limit}", "--tstp-format", "--proof-object", "-l", str(output_level)]
            if extra_args:
                cmd[1:1] = list(extra_args)
            cmd.append(tmp_path)
            proc = _run(cmd)
            stdout_final = proc.stdout
            stderr_final = proc.stderr
            exit_code = proc.returncode

            status = _parse_szs(stdout_final) or _parse_szs(stderr_final)
            proof = _extract_proof_block(stdout_final) or _extract_proof_block(stderr_final)
            if proof:
                proof_tstp = _clean_tstp(proof)

        # -------- Attempt C: eproof fallback (does eprover + epclextract) --------
        if want_proof and proof_tstp is None and shutil.which("eproof") is not None:
            cmd_eproof = ["eproof", "--auto", f"--cpu-limit={cpu_limit}", "-l", "3", "--tstp-out", tmp_path]
            proc_ep = _run(cmd_eproof)
            stdout_final = proc_ep.stdout
            stderr_final = proc_ep.stderr
            exit_code = proc_ep.returncode

            status = _parse_szs(stdout_final) or _parse_szs(stderr_final) or status
            proof = _extract_proof_block(stdout_final) or _extract_proof_block(stderr_final)
            if proof:
                proof_tstp = _clean_tstp(proof)

        # If proof disabled or still not found, leave proof_tstp as None
        used_axioms = _extract_used_axioms_from_proof(proof_tstp) if proof_tstp else None

        # Optional digest for common patterns
        digest = _digest_refutation_ui_mp(proof_tstp) if (want_digest and proof_tstp) else None

        return EProverResult(
            status=status,
            proof_tstp=proof_tstp,
            used_axioms=used_axioms,
            stdout=stdout_final,
            stderr=stderr_final,
            exit_code=exit_code,
            proof_digest=digest
        )

    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
