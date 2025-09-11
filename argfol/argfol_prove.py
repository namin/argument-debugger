#!/usr/bin/env python3
"""CLI: Read a JSON problem (axioms + conjecture) and invoke E prover.

JSON schema:
{
  "axioms": {
    "name1": "fof formula string",
    "name2": "..."
  },
  "conjecture": "fof formula string or null"
}

The FOF strings use TPTP connectives (FOF). This CLI is handy when your LLM
already emits FOF; if you need AST construction, use the Python API instead.
"""
import sys
import json
import argparse
from typing import Dict, Optional, List
from .eprover import prove_with_e

def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Prove FOL theorems using E prover from JSON input"
    )
    parser.add_argument('input_json', 
                       help='Path to JSON file with axioms/conjecture in FOF strings')
    parser.add_argument('--e-path', 
                       default='eprover',
                       help='Path to E prover executable (default: eprover)')
    parser.add_argument('--cpu-limit', 
                       type=int, 
                       default=5,
                       help='CPU time limit in seconds (default: 5)')
    
    args = parser.parse_args()
    
    # Load JSON input
    try:
        with open(args.input_json, 'r') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading JSON file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract axioms and conjecture
    axioms: Dict[str, str] = data.get('axioms', {})
    conjecture: Optional[str] = data.get('conjecture')
    
    # Build TPTP problem from FOF strings
    lines: List[str] = [f"fof({k}, axiom, {v})." for k, v in axioms.items()]
    if conjecture is not None:
        lines.append(f"fof(conj, conjecture, {conjecture}).")
    
    tptp = '% From JSON input\n' + '\n'.join(lines) + '\n'
    
    # Run E prover
    res = prove_with_e(tptp, e_path=args.e_path, cpu_limit=args.cpu_limit)
    
    # Output results
    print(f"Status: {res.status}")
    
    if res.used_axioms:
        print(f"Used axioms: {res.used_axioms}")
    
    if res.proof_tstp:
        print('--- PROOF (TSTP) ---')
        print(res.proof_tstp)
        print('--- END PROOF ---')
    
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    
    sys.exit(0 if res.exit_code == 0 else 1)

if __name__ == '__main__':
    main()