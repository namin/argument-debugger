
from __future__ import annotations
import json
from functools import lru_cache
from typing import Dict, Tuple, Any, Optional

DEFAULT_SCHEMES_PATH = "schemes.json"

@lru_cache(maxsize=1)
def load_schemes(path: str = DEFAULT_SCHEMES_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=1)
def load_cq_labels(path: str = DEFAULT_SCHEMES_PATH) -> Dict[str, Tuple[str, str]]:
    data = load_schemes(path)
    labels: Dict[str, Tuple[str, str]] = {}
    for sid, scheme in data.items():
        if sid.startswith("_"):
            continue
        for cq in scheme.get("critical_questions", []):
            cid = cq["id"]
            title = cq.get("title") or cid
            short = cq.get("short") or ""
            if cid not in labels:
                labels[cid] = (title, short)
    return labels

@lru_cache(maxsize=1)
def load_cq_meta(path: str = DEFAULT_SCHEMES_PATH):
    data = load_schemes(path)
    meta: Dict[str, Dict[str, Any]] = {}
    for sid, scheme in data.items():
        if sid.startswith("_"):
            continue
        for cq in scheme.get("critical_questions", []):
            meta[cq["id"]] = cq
    return meta

def format_cq_one_liner(cq_id: str, path: str = DEFAULT_SCHEMES_PATH) -> str:
    meta = load_cq_meta(path).get(cq_id, {"title": cq_id, "short": ""})
    title = meta.get("title", cq_id)
    short = meta.get("short", "").rstrip(".")
    return f"{title} — {short}." if short else title

def format_cq_extended(cq_id: str, path: str = DEFAULT_SCHEMES_PATH) -> str:
    meta = load_cq_meta(path).get(cq_id, {"title": cq_id})
    parts = [meta.get("title", cq_id)]
    q = meta.get("question")
    if q:
        parts.append(q)
    hint = meta.get("short")
    if hint:
        parts.append(hint)
    why = meta.get("why_it_matters")
    if why:
        parts.append(f"Why it matters: {why}")
    return " — ".join(parts)

ALLOWED_BY_RULE_TYPE = {
    "deductive": [
        "rules_to_case",
        "definition",
        "analogy",
    ],
    "inductive": [
        "example",
        "analogy",
        "sign",
        "correlation_to_causation",
        "cause_to_effect",
        "expert_opinion",
        "position_to_know",
    ],
    "causal": [
        "cause_to_effect",
        "correlation_to_causation",
        "sign",
        "practical_reasoning",
        "argument_from_consequences",
    ],
    "definitional": [
        "definition",
        "rules_to_case",
        "analogy",
    ],
}
