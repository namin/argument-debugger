#!/usr/bin/env python3
# run_unified.py — CLI to produce the unified AF + ad.py report
from __future__ import annotations

import argparse, sys, json
from pathlib import Path

from unified_core import generate_unified_report

def main():
    ap = argparse.ArgumentParser(description="Unified AF + ad.py reporter")
    ap.add_argument("file", nargs="?", help="Input .txt (blocks separated by blank lines). If omitted, read stdin.")
    ap.add_argument("--relation", choices=["auto","explicit","none"], default="auto")
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--llm-mode", choices=["augment","override"], default="augment")
    ap.add_argument("--llm-threshold", type=float, default=0.55)
    ap.add_argument("--jaccard", type=float, default=0.45)
    ap.add_argument("--min-overlap", type=int, default=3)
    ap.add_argument("--target", default=None)
    ap.add_argument("--winners", choices=["preferred","stable","grounded","complete","stage","semi-stable"], default="stable")
    ap.add_argument("--repair", action="store_true", help="Ask ad.py to propose repair for each stance")
    ap.add_argument("--md-out", default=None, help="Write Markdown to file")
    ap.add_argument("--json-out", default=None, help="Write JSON summary to file")
    args = ap.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
        filename = Path(args.file).name
    else:
        text = sys.stdin.read()
        filename = "stdin"

    result = generate_unified_report(
        text=text,
        relation=args.relation,
        use_llm=args.use_llm,
        llm_mode=args.llm_mode,
        llm_threshold=args.llm_threshold,
        jaccard=args.jaccard,
        min_overlap=args.min_overlap,
        target=args.target,
        winners_semantics=args.winners,
        repair_stance=args.repair,
        filename=filename,
    )

    md = result["markdown"]
    if args.md_out:
        Path(args.md_out).write_text(md, encoding="utf-8")
    else:
        print(md)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
