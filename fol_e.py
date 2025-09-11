from dataclasses import dataclass
from typing import Dict, Optional, List, Literal
from argfol.tptp import to_tptp_problem
from argfol.eprover import prove_with_e, EProverResult

@dataclass
class ECheck:
    status: Literal["Theorem","Unsatisfiable","Satisfiable","CounterSatisfiable","Unknown","Timeout","Error"]
    used_axioms: Optional[List[str]]
    proof_tstp: Optional[str]
    tptp: str

def check_entailment_fof(axioms_fof: Dict[str, str], conjecture_fof: Optional[str],
                         *, cpu_limit: int = 5, e_path: str = "eprover") -> ECheck:
    # Build a TPTP problem from FOF strings (names must be unique & stable)
    lines = [f"fof({k}, axiom, {v})." for k, v in axioms_fof.items()]
    if conjecture_fof is not None:
        lines.append(f"fof(conj, conjecture, {conjecture_fof}).")
    tptp = "% AD/E bridge\n" + "\n".join(lines) + "\n"

    res: EProverResult = prove_with_e(
        tptp, e_path=e_path, cpu_limit=cpu_limit,
        # These ensure a TSTP proof gets printed (you fixed your eprover.py already)
        extra_args=["--tstp-format", "--proof-object", "-l", "3"]
    )
    # Normalize status for UI
    status = res.status or "Unknown"
    return ECheck(status=status, used_axioms=res.used_axioms, proof_tstp=res.proof_tstp, tptp=tptp)

