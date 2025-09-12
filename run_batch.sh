#!/usr/bin/env bash
set -e
echo "Running batch NL → IR → AF → greedy (within-first, budget=2)"
for f in arguments_nl/*.txt; do
  echo "---- $f ----"
  python -B strengthener_cli.py --file "$f" --within-first --budget 2
  echo
done
echo "Done."
