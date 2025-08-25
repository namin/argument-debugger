#!/usr/bin/env python3
"""
nl2apx_adapter.py — Convert nl2apx edges (argument-level) into a BAF.
- Each block ID becomes an 'argument' node with its text.
- Each attack (i -> j) becomes a BAF attack edge (kind='rebut' by default).
- Provenance tags: 'exp' for explicit, 'heu' for heuristic, 'llm' for LLM.
"""
from __future__ import annotations

from typing import List, Dict, Tuple, Set, Optional
import importlib

from baf import BAF

# nl2apx.py must be available
NL = importlib.import_module("nl2apx")

def baf_from_nl2apx_edges(ids: List[str],
                          id2text: Dict[str, str],
                          idx_edges: Set[Tuple[int, int]],
                          meta: Dict) -> BAF:
    """
    Build a BAF where nodes are the argument blocks (IDs) and attacks are
    those discovered by nl2apx (explicit/heuristic/LLM).
    """
    baf = BAF()

    # 1) Nodes (argument-level)
    for _id in ids:
        baf.add_node(_id, text=id2text.get(_id, "").strip(), type="argument", source="nl2apx")

    # 2) Edge provenance lookup
    prov_idx = {}
    def add(lst, tag):
        for e in lst or []:
            prov_idx.setdefault(tuple(e), []).append(tag)
    add(meta.get("explicit_edges"), "exp")
    add(meta.get("heuristic_edges"), "heu")
    add(meta.get("llm_edges"), "llm")

    # 3) Attacks
    ids_list = list(ids)
    for (i, j) in idx_edges:
        src = ids_list[i]; dst = ids_list[j]
        tags = prov_idx.get((i, j), [])
        baf.add_attack(src, dst, kind="rebut", tags=tags)

    # keep meta (optional, attach at graph-level in one place if desired)
    return baf

def baf_from_text_file(path: str,
                       relation_mode: str = "auto",
                       jaccard: float = 0.45,
                       min_overlap: int = 3,
                       use_llm: bool = False,
                       llm_threshold: float = 0.55,
                       llm_mode: str = "augment") -> BAF:
    """
    Parse a .txt file with blocks using nl2apx and return a BAF with arguments as nodes.
    """
    blocks = NL.parse_blocks(path)
    ids, id2text, idx_edges, meta = NL.build_edges(
        blocks,
        relation_mode=relation_mode,
        jac_threshold=jaccard,
        min_overlap=min_overlap,
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        llm_mode=llm_mode,
    )
    return baf_from_nl2apx_edges(ids, id2text, idx_edges, meta)
