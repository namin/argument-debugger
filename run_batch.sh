#!/usr/bin/env bash
set -e
echo "Running batch"
for f in arguments_nl/*.txt; do
  echo "---- $f ----"
  python -B strengthener_cli.py --file "$f" --e2e
  echo
done
echo "Done."
