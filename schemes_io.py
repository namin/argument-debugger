
from __future__ import annotations
import json
from functools import lru_cache
from typing import Dict, Tuple, Any, Optional

DEFAULT_SCHEMES_PATH = "schemes.json"

@lru_cache(maxsize=1)
def load_schemes(path: str = DEFAULT_SCHEMES_PATH) -> Dict[str, Any]:
    """Load schemes.json once (cached). Returns a dict keyed by scheme_id, including _meta."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=1)
def load_cq_labels(path: str = DEFAULT_SCHEMES_PATH) -> Dict[str, Tuple[str, str]]:
    """Return a map {cq_id: (label, hint)} built from schemes.json.
    If a cq_id appears in multiple schemes with different labels/hints, the first occurrence wins.
    """
    data = load_schemes(path)
    labels: Dict[str, Tuple[str, str]] = {}
    for sid, scheme in data.items():
        if sid.startswith("_"):  # skip meta
            continue
        for cq in scheme.get("critical_questions", []):
            cid = cq["id"]
            if cid not in labels:
                labels[cid] = (cq.get("label", cid), cq.get("hint", ""))
    return labels

# Optional: centralize allowed schemes per rule_type (used by the classifier prompt)
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
    # 'definitional' can be mapped to definitions/rules depending on how your parser emits it
    "definitional": [
        "definition",
        "rules_to_case",
        "analogy",
    ],
}

def get_cq_label_hint(cq_id: str, path: str = DEFAULT_SCHEMES_PATH) -> Tuple[str, str]:
    """Convenience: fetch (label, hint) for a cq_id, falling back to (cq_id, '')."""
    labels = load_cq_labels(path)
    return labels.get(cq_id, (cq_id, ""))
