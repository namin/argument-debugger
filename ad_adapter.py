#!/usr/bin/env python3
"""
ad_adapter.py — Convert a single-block analysis from ad.py into a BAF.
- Each claim from ad.py becomes a node "<BLOCK_ID>.<claim_id>"
- Inferences become support edges between those nodes.
- Optionally, connect the block-level node "<BLOCK_ID>" to its goal claim via a support edge.
- Issues (unsupported_premise, missing_link, circular, false_dichotomy, slippery_slope) are recorded as node meta.
"""
from __future__ import annotations

from typing import Optional, List, Dict
from dataclasses import dataclass
import importlib

from baf import BAF

# ad.py must be available
AD = importlib.import_module("ad")

def baf_from_ad_block(text: str, block_id: str, connect_goal_to_block: bool = True):
    """
    Run ad.py's parser on a single argument block and convert to a BAF.
    Node IDs are namespaced as "<block_id>.<claim_id>" to remain unique
    when you later merge multiple blocks.
    """
    parser = AD.ArgumentParser()
    A = parser.parse_argument(text)

    baf = BAF()
    # Add the block-level node (type=argument)
    baf.add_node(block_id, text=text.strip(), type="argument", source="ad")

    # Add claim nodes
    for c in A.claims:
        nid = f"{block_id}.{c.id}"
        baf.add_node(nid, text=c.content, type=c.type, source="ad", block=block_id)

    # Add support edges for inferences
    for inf in A.inferences:
        to_id = f"{block_id}.{inf.to_claim}"
        for frm in inf.from_claims:
            from_id = f"{block_id}.{frm}"
            baf.add_support(from_id, to_id, tags=["struct"])

    # Equivalences
    if getattr(A, "equivalences", None):
        for group in A.equivalences:
            baf.equiv.append(set(f"{block_id}.{g}" for g in group))

    # Issues → node meta (lightweight; you can build specialized UIs from this)
    # We'll use parser + ASPAnalyzer to surface issues; store per-claim flags.
    issues = AD.ASPDebugger(debug=False).analyze(A)
    per_claim = {}
    for iss in issues:
        for cid in iss.involved_claims:
            # Keep only claim-like IDs (ad.py sometimes returns "premises" token)
            if isinstance(cid, str) and cid.startswith("c"):
                per_claim.setdefault(cid, []).append(iss.type)
    for cid, tags in per_claim.items():
        nid = f"{block_id}.{cid}"
        if nid in baf.nodes:
            baf.nodes[nid].meta.setdefault("issues", [])
            for t in tags:
                if t not in baf.nodes[nid].meta["issues"]:
                    baf.nodes[nid].meta["issues"].append(t)

    # Connect the goal claim to the block node (support)
    if connect_goal_to_block and getattr(A, "goal_claim", None):
        goal = f"{block_id}.{A.goal_claim}"
        baf.add_support(goal, block_id, tags=["struct", "goal"])

    return baf, A  # return both for callers that need ad.py structure too
