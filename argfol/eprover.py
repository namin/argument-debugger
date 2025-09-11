from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import subprocess, tempfile, os, re, shutil

@dataclass
class EProverResult:
    status: str                 # e.g., 'Theorem', 'Unsatisfiable', 'Satisfiable', 'CounterSatisfiable', 'Unknown', 'Timeout', 'Error'
    proof_tstp: Optional[str]   # text between 'SZS output start' and 'SZS output end', if any
    used_axioms: Optional[List[str]]  # heuristic extraction from proof, if present
    stdout: str                 # raw stdout from eprover
    stderr: str                 # raw stderr from eprover
    exit_code: int

def _parse_szs(stdout: str) -> str:
    """Extract SZS status from E prover output"""
    m = re.search(r"SZS status\s+([A-Za-z_]+)", stdout)
    return m.group(1) if m else 'Unknown'

def _extract_proof(stdout: str) -> Optional[str]:
    """Extract proof between SZS output markers"""
    # Handle both "# SZS output end" and "SZS output end" formats
    m = re.search(r"SZS output start[^\n]*\n(.*?)#?\s*SZS output end", stdout, flags=re.S)
    return m.group(1).strip() if m else None

def _extract_used_axioms_from_proof(proof: str) -> List[str]:
    """Extract axiom names from proof text"""
    names = set()
    # fof(name, axiom, ...).
    for m in re.finditer(r"\bfof\(([^,]+),\s*axiom", proof):
        names.add(m.group(1))
    # input_clause(name, ...)
    for m in re.finditer(r"\binput_clause\(([^,]+),", proof):
        names.add(m.group(1))
    return sorted(names)

def prove_with_e(
    tptp_text: str, *,
    e_path: str = "eprover",
    cpu_limit: int = 5,
    extra_args: Optional[list] = None,
    want_proof: bool = True
) -> EProverResult:
    """
    Run E prover on a TPTP string and parse its result.
    
    Args:
        tptp_text: TPTP problem in FOF format
        e_path: Path to eprover executable
        cpu_limit: CPU time limit in seconds
        extra_args: Additional command line arguments
        want_proof: Whether to request proof output
    
    Returns:
        EProverResult with status, proof, and diagnostic information
    """
    # Check if E prover is available
    if shutil.which(e_path) is None:
        return EProverResult(
            status="Error", 
            proof_tstp=None, 
            used_axioms=None, 
            stdout="",
            stderr=f"E prover not found at '{e_path}'. Install with: brew install eprover (macOS) or apt-get install eprover (Linux)",
            exit_code=127
        )

    # Write TPTP problem to temporary file
    with tempfile.NamedTemporaryFile("w", suffix=".p", delete=False) as f:
        f.write(tptp_text)
        tmp_path = f.name

    try:
        # Build command with appropriate flags
        cmd = [e_path, "--auto", f"--cpu-limit={cpu_limit}"]
        
        if want_proof:
            # Add proof generation flags AFTER --auto to override defaults
            cmd += ["--tstp-format", "--proof-object", "-l", "3"]
        
        if extra_args:
            cmd += list(extra_args)
        
        cmd.append(tmp_path)
        
        # Run E prover
        proc = subprocess.run(cmd, capture_output=True, text=True)
        stdout, stderr = proc.stdout, proc.stderr
        
        # Parse results
        status = _parse_szs(stdout) or _parse_szs(stderr)
        proof = _extract_proof(stdout) if want_proof else None
        
        # If no proof found but eproof is available, try it as fallback
        if want_proof and not proof and shutil.which("eproof"):
            cmd_eproof = ["eproof", "--auto", f"--cpu-limit={cpu_limit}", 
                          "-l", "3", "--tstp-out", tmp_path]
            proc_eproof = subprocess.run(cmd_eproof, capture_output=True, text=True)
            proof = _extract_proof(proc_eproof.stdout)
            if proof:
                stdout = proc_eproof.stdout
                stderr = proc_eproof.stderr
                status = _parse_szs(stdout) or status
        
        # Extract axioms if proof was found
        used_axioms = _extract_used_axioms_from_proof(proof) if proof else None
        
        return EProverResult(
            status=status, 
            proof_tstp=proof, 
            used_axioms=used_axioms,
            stdout=stdout, 
            stderr=stderr, 
            exit_code=proc.returncode
        )
        
    finally:
        # Clean up temporary file
        try:
            os.remove(tmp_path)
        except OSError:
            pass