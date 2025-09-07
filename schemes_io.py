
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
            if cid not in labels:
                labels[cid] = (cq.get("label", cid), cq.get("hint", ""))
    return labels

@lru_cache(maxsize=1)
def load_cq_meta(path: str = DEFAULT_SCHEMES_PATH) -> Dict[str, Dict[str, Any]]:
    """Return a map {cq_id: full_metadata_dict} from schemes.json."""
    data = load_schemes(path)
    meta: Dict[str, Dict[str, Any]] = {}
    for sid, scheme in data.items():
        if sid.startswith("_"):
            continue
        for cq in scheme.get("critical_questions", []):
            cid = cq["id"]
            if cid not in meta:
                meta[cid] = cq
    return meta

def get_cq_label_hint(cq_id: str, path: str = DEFAULT_SCHEMES_PATH) -> Tuple[str, str]:
    labels = load_cq_labels(path)
    return labels.get(cq_id, (cq_id, ""))

def get_cq_meta(cq_id: str, path: str = DEFAULT_SCHEMES_PATH) -> Dict[str, Any]:
    meta = load_cq_meta(path)
    return meta.get(cq_id, {"id": cq_id, "label": cq_id, "hint": ""})

ALLOWED_BY_RULE_TYPE = {
    "deductive": [
        "practical_reasoning",
        "argument_from_consequences",
        "rules_to_case",
        "definition",
        "analogy",
        "cause_to_effect",
        "expert_opinion",
        "position_to_know",
    ],
    "inductive": [
        "example",
        "analogy",
        "sign",
        "correlation_to_causation",
        "cause_to_effect",
    ],
    "causal": [
        "cause_to_effect",
        "correlation_to_causation",
        "sign",
    ],
    "definitional": [
        "definition",
        "rules_to_case",
        "analogy",
    ],
}
