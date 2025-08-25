#!/usr/bin/env python3
"""
nl2apx.py — Natural language → APX (Dung AF) translator

Reads a text file where each argument is a block separated by a blank line.
Optionally uses 'ID:' and 'ATTACKS:' directives per block; otherwise uses a simple
contradiction heuristic. You can also enable LLM-based edge inference (Gemini).

APX output format (ICCMA):
  arg(a1).
  arg(a2).
  att(a1,a2).   % a1 attacks a2

Usage examples:
  python nl2apx.py arguments.txt > graph.apx
  python nl2apx.py arguments.txt --relation explicit --out graph.apx
  python nl2apx.py arguments.txt --use-llm --llm-threshold 0.6 --out graph.apx
  python nl2apx.py arguments_no_explicit.txt --relation auto --out graph.apx --provenance

Input directives (optional, per block):
  ID: A1
  ATTACKS: A2, A3    or   ATTACKS: #2 #3

Environment for LLM (same as ad.py):
  GEMINI_API_KEY   or   GOOGLE_CLOUD_PROJECT (+ GOOGLE_CLOUD_LOCATION)
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Dict, List, Set, Tuple, Optional

# ---------------------------
# Optional Gemini client (mirrors ad.py setup)
# ---------------------------
_HAVE_LLM = False
_HAVE_PYDANTIC = False
try:
    from google import genai
    from google.genai import types
    _HAVE_LLM = True
except Exception:
    _HAVE_LLM = False

try:
    from pydantic import BaseModel, Field
    _HAVE_PYDANTIC = True
except Exception:
    _HAVE_PYDANTIC = False
    class BaseModel:  # minimal shim for type hints
        pass
    def Field(*args, **kwargs):
        return None

LLM_MODEL = "gemini-2.5-flash"

def init_llm_client():
    import os
    if not _HAVE_LLM:
        raise RuntimeError("google.genai not available; install or omit --use-llm.")
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    google_cloud_project = os.getenv('GOOGLE_CLOUD_PROJECT')
    google_cloud_location = os.getenv('GOOGLE_CLOUD_LOCATION', "us-central1")
    if gemini_api_key:
        return genai.Client(api_key=gemini_api_key)
    elif google_cloud_project:
        return genai.Client(vertexai=True, project=google_cloud_project, location=google_cloud_location)
    else:
        raise ValueError("Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT to use --use-llm.")

# ---------------------------
# Parsing utilities
# ---------------------------

STOPWORDS = {
    "the","a","an","and","or","to","of","in","on","for","with","by","as",
    "that","this","it","is","are","was","were","be","being","been",
    "at","from","but","if","then","than","so","because","since","while",
    "we","you","they","he","she","i","me","my","our","your","their",
    "do","does","did","done","have","has","had","will","would","can","could","may","might","must","should",
    "not"
}
NEG_MARKERS = {"not","no","never","cannot","can't","cant","n't"}
TOKEN_RE = re.compile(r"[a-z]+")

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).strip()

def tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())

def content_tokens(text: str) -> Set[str]:
    return {w for w in tokens(text) if w not in STOPWORDS}

def has_negation(text: str) -> bool:
    low = text.lower()
    if "n't" in low:
        return True
    for m in NEG_MARKERS:
        if re.search(rf"\b{re.escape(m)}\b", low):
            return True
    return False

def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return 0.0 if union == 0 else inter / union

def parse_blocks_text(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    return parse_blocks_text(raw)

def parse_blocks_text(raw: str) -> List[str]:
    # Normalize line endings and split on blank lines (incl. spaces)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = re.split(r"(?:\n\s*\n)+", raw)
    # Trim each block but KEEP internal newlines so ^ATTACKS: still matches
    return [b.strip() for b in blocks if b.strip()]


def parse_id_from_block(block: str) -> Optional[str]:
    m = re.search(r"(?im)^\s*id\s*:\s*([A-Za-z0-9_\-#]+)\s*$", block)
    return m.group(1).strip() if m else None

def parse_attacks_from_block(block: str) -> List[str]:
    toks = []
    for line in block.splitlines():
        m = re.match(r"(?im)^\s*attacks\s*:\s*(.+?)\s*$", line)
        if m:
            tail = m.group(1)
            toks += [p.strip() for p in re.split(r"[\s,;]+", tail) if p.strip()]
    return toks

def strip_directives(block: str) -> str:
    lines = []
    for line in block.splitlines():
        if re.match(r"(?im)^\s*(id|attacks)\s*:", line):
            continue
        lines.append(line)
    return normalize("\n".join(lines))

def assign_ids(n: int) -> List[str]:
    return [f"A{i+1}" for i in range(n)]

def sanitize_atom(s: str) -> str:
    """APX atoms should be safe identifiers; make lowercase, alnum/_; start with letter."""
    s2 = re.sub(r"[^A-Za-z0-9_]", "_", s).lower()
    if not s2 or not s2[0].isalpha():
        s2 = "a" + s2
    return s2

def make_unique(ids: List[str]) -> List[str]:
    seen = {}
    out = []
    for x in ids:
        base = sanitize_atom(x)
        if base not in seen:
            seen[base] = 0
            out.append(base)
        else:
            seen[base] += 1
            out.append(f"{base}_{seen[base]}")
    return out

# ---------------------------
# LLM edge extraction
# ---------------------------

if _HAVE_PYDANTIC:
    class EdgeModel(BaseModel):
        src: str = Field(description="Source index like '#1'")
        dst: str = Field(description="Target index like '#2'")
        confidence: float = Field(ge=0.0, le=1.0, description="Confidence in [0,1]")

    class AFEdges(BaseModel):
        edges: List[EdgeModel] = Field(default_factory=list)

class LLMAttackExtractor:
    def __init__(self, threshold: float = 0.55):
        self.threshold = threshold
        self.client = None
        try:
            self.client = init_llm_client()
        except Exception as e:
            self.client = None
            print(f"% [WARN] LLM disabled: {e}")

    def infer_edges(self, blocks: List[str]) -> Set[Tuple[int, int]]:
        if self.client is None:
            return set()
        listing = "\n".join([f"#{i+1}: {blocks[i]}" for i in range(len(blocks))])
        prompt = f"""
You are extracting a Dung Abstract Argumentation Framework (AF) from a list of short argument items.

TASK:
- For each ordered pair (#i, #j), add an ATTACK edge if accepting #i undermines or contradicts #j.
- Do *not* invent items; use only the provided list.
- Return JSON: {{"edges":[{{"src":"#i","dst":"#j","confidence":0..1}}, ...]}}.
- Include only attacks (no supports).

ITEMS:
{listing}
"""
        try:
            if _HAVE_PYDANTIC:
                cfg = types.GenerateContentConfig(
                    temperature=0.1,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    response_mime_type="application/json",
                    response_schema=AFEdges
                )
            else:
                cfg = types.GenerateContentConfig(
                    temperature=0.1,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    response_mime_type="application/json"
                )
            resp = self.client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config=cfg
            )
            text = resp.text
            if _HAVE_PYDANTIC:
                data = AFEdges.model_validate_json(text)
                raw = [dict(src=e.src, dst=e.dst, confidence=e.confidence) for e in data.edges]
            else:
                data = json.loads(text)
                raw = data.get("edges", [])
            edges: Set[Tuple[int,int]] = set()
            for e in raw:
                try:
                    i = int(str(e["src"]).lstrip("#")) - 1
                    j = int(str(e["dst"]).lstrip("#")) - 1
                    conf = float(e.get("confidence", 1.0))
                except Exception:
                    continue
                if conf >= self.threshold:
                    edges.add((i, j))
            return edges
        except Exception as e:
            print(f"% [WARN] LLM inference failed: {e}")
            return set()

# ---------------------------
# AF construction (explicit / heuristic / LLM)
# ---------------------------

def build_edges(blocks: List[str],
                relation_mode: str = "auto",
                jac_threshold: float = 0.45,
                min_overlap: int = 3,
                use_llm: bool = False,
                llm_threshold: float = 0.55,
                llm_mode: str = "augment") -> Tuple[List[str], Dict[str,str], Set[Tuple[int,int]], Dict]:
    """Returns (ids, id_to_text, edges(indexed), meta)."""
    # IDs (prefer explicit; else A1..An)
    provided_ids = [parse_id_from_block(b) for b in blocks]
    auto_ids = assign_ids(len(blocks)) if any(pid is None for pid in provided_ids) else []
    ids = [pid if pid is not None else auto_ids[i] for i, pid in enumerate(provided_ids)]
    # Strip directives for text
    id_to_text = {ids[i]: strip_directives(blocks[i]) for i in range(len(blocks))}

    # Explicit edges (index-based)
    explicit_edges: Set[Tuple[int,int]] = set()
    index_of = {ids[i]: i for i in range(len(ids))}
    for i, b in enumerate(blocks):
        for t in parse_attacks_from_block(b):
            dst = None
            if t.startswith("#"):
                try:
                    k = int(t[1:]) - 1
                    if 0 <= k < len(ids):
                        dst = k
                except ValueError:
                    pass
            else:
                if t in index_of:
                    dst = index_of[t]
            if dst is not None and dst != i:
                explicit_edges.add((i, dst))

    # Heuristic edges (only if no explicit and mode allows)
    heuristic_edges: Set[Tuple[int,int]] = set()
    use_heur = (relation_mode == "auto" and not explicit_edges)
    if relation_mode == "explicit":
        use_heur = False
    if relation_mode == "none":
        use_heur = False
    if use_heur:
        ctoks = {i: content_tokens(id_to_text[ids[i]]) for i in range(len(ids))}
        negf = {i: has_negation(id_to_text[ids[i]]) for i in range(len(ids))}
        for i in range(len(ids)):
            for j in range(i+1, len(ids)):
                A = ctoks[i]; B = ctoks[j]
                if len(A & B) < min_overlap: 
                    continue
                if jaccard(A, B) < jac_threshold:
                    continue
                if negf[i] ^ negf[j]:
                    heuristic_edges.add((i, j))
                    heuristic_edges.add((j, i))

    # LLM edges
    llm_edges: Set[Tuple[int,int]] = set()
    if use_llm:
        ext = LLMAttackExtractor(threshold=llm_threshold)
        llm_edges = ext.infer_edges(blocks)

    # Combine
    if use_llm and llm_mode == "override":
        edges = set(llm_edges)
    else:
        edges = set(explicit_edges) | set(heuristic_edges) | set(llm_edges)

    meta = {
        "explicit_edges": sorted(list(explicit_edges)),
        "heuristic_edges": sorted(list(heuristic_edges)),
        "llm_edges": sorted(list(llm_edges)),
        "final_edges": sorted(list(edges)),
    }
    return ids, id_to_text, edges, meta

# ---------------------------
# APX emission
# ---------------------------

def emit_apx(ids: List[str],
             id_to_text: Dict[str,str],
             edges: Set[Tuple[int,int]],
             provenance: Optional[Dict] = None) -> str:
    # Sanitize & deduplicate atom names
    apx_atoms = make_unique([sanitize_atom(i) for i in ids])
    # Map index -> atom
    id_atom = {i: apx_atoms[i] for i in range(len(ids))}

    lines: List[str] = []
    # Header as comments
    lines.append("% APX generated by nl2apx.py")
    lines.append("% Arguments and mapping:")
    for i, id_ in enumerate(ids):
        text = id_to_text[id_].replace("\n"," ").strip()
        lines.append(f"%   {id_atom[i]} == {id_} :: {text[:80]}")

    # arg/1
    for i in range(len(ids)):
        lines.append(f"arg({id_atom[i]}).")

    # att/2
    lines.append("% Attacks")
    for (i, j) in sorted(edges):
        lines.append(f"att({id_atom[i]},{id_atom[j]}).")

    # Optional provenance
    if provenance:
        lines.append("% --- provenance (indices; 0-based) ---")
        for k, v in provenance.items():
            if k in ("explicit_edges","heuristic_edges","llm_edges","final_edges"):
                lines.append(f"% {k}: {v}")
    return "\n".join(lines) + "\n"

# ---------------------------
# CLI
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="Natural language → APX translator (Dung AF).")
    ap.add_argument("path", help="Path to text file. Each argument block separated by a blank line.")
    ap.add_argument("--out", "-o", help="Output .apx file (default: stdout).", default=None)
    ap.add_argument("--relation", default="auto", choices=["auto","explicit","none"],
                    help="How to derive attacks: 'auto' uses ATTACKS if present else heuristics; 'explicit' uses only ATTACKS; 'none' disables heuristics (ATTACKS still honored).")
    ap.add_argument("--jaccard", type=float, default=0.45, help="Heuristic Jaccard threshold (auto mode).")
    ap.add_argument("--min-overlap", type=int, default=3, help="Minimum shared content tokens for heuristic (auto mode).")
    ap.add_argument("--use-llm", action="store_true", help="Use Gemini to infer attacks.")
    ap.add_argument("--llm-threshold", type=float, default=0.55, help="Confidence cutoff for LLM edges.")
    ap.add_argument("--llm-mode", default="augment", choices=["augment","override"],
                    help="Combine with other edges (augment) or use only LLM edges (override).")
    ap.add_argument("--provenance", action="store_true", help="Include provenance comments.")
    args = ap.parse_args()

    blocks = parse_blocks(args.path)
    ids, id_to_text, edges, meta = build_edges(
        blocks,
        relation_mode=args.relation,
        jac_threshold=args.jaccard,
        min_overlap=args.min_overlap,
        use_llm=args.use_llm,
        llm_threshold=args.llm_threshold,
        llm_mode=args.llm_mode,
    )
    apx = emit_apx(ids, id_to_text, edges, provenance=(meta if args.provenance else None))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(apx)
    else:
        print(apx, end="")

if __name__ == "__main__":
    main()
