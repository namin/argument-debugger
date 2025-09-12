#!/usr/bin/env bash
set -euo pipefail
OUT="out"
mkdir -p "$OUT"
echo "Running NL → IR → FOL → Cert → AF → Optimal (fallback greedy)"
for f in arguments_nl/*.txt; do
  echo "---- $f ----"
  CERT_OUTDIR="$OUT/certs" \
  python -B strengthener_cli.py --file "$f" --e2e --synth-fol --dump-ir "$OUT"/
done
