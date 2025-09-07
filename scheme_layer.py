
from __future__ import annotations
import json, re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel, Field
from google.genai import types
from llm import init_llm_client, generate_content

# --------- Pydantic IO schema for the scheme call ---------

class SchemeItem(BaseModel):
    from_claims: List[str] = Field(description="Premise claim IDs used in this inference")
    to_claim: str = Field(description="Conclusion claim ID this inference supports")
    scheme_id: str = Field(description="Chosen scheme id (must be one of the allowed ids provided)")
    required_cqs: List[str] = Field(default_factory=list, description="At most k CQ IDs deemed necessary for this inference")

class SchemeAnalysis(BaseModel):
    items: List[SchemeItem] = Field(default_factory=list)

# --------- Facts returned to host pipeline ---------

@dataclass
class SchemeFacts:
    # After aggregation per conclusion:
    requires: List[Tuple[str, str]]  # (to_claim, cq_id)
    answered: List[Tuple[str, str]]  # (to_claim, cq_id)
    raw_items: List[SchemeItem]      # Original per-inference items (for debugging)

# --------- Main LLM-driven assigner ---------

class SchemeAssigner:
    """
    LLM-only scheme assignment + CQ selection.
    Features:
      - restrict schemes by parser's rule_type (deductive/inductive/causal),
      - cap to top-k CQs (per inference request and per-conclusion aggregation),
      - aggregate CQs per conclusion to avoid duplicates.
    """

    def __init__(self, schemes_path: str = "schemes.json", topk: int = 2, temperature: float = 0.0):
        with open(schemes_path, "r", encoding="utf-8") as f:
            self.schemes = json.load(f)
        self.topk = max(0, int(topk))
        self.client = init_llm_client()
        self.config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=SchemeAnalysis,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

    def analyze(self, argument, original_text: str, topk: Optional[int] = None) -> SchemeFacts:
        k = self.topk if topk is None else max(0, int(topk))

        # Prepare allowed schemes per rule_type
        allowed_map = {
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
        }

        claims_json = [{"id": c.id, "content": c.content, "type": c.type} for c in argument.claims]
        infs_json = [{"from_claims": i.from_claims, "to_claim": i.to_claim, "rule_type": i.rule_type}
                     for i in argument.inferences]

        # Build the instruction. We include an allowed set for each inference by rule_type.
        # We also ask the LLM to return at most k CQs per inference.
        # We *still* aggregate per conclusion afterward to ensure a hard cap of k per conclusion.
        prompt = f"""
You classify each inference in an argument into a standard argumentation scheme and list
the most relevant critical questions (CQs). Use ONLY the allowed schemes for each inference's rule_type.

SCHEMES (ids → CQs):
{json.dumps({sid: [cq["id"] for cq in s.get("critical_questions", [])] for sid, s in self.schemes.items()}, ensure_ascii=False)}

ALLOWED BY RULE TYPE:
{json.dumps(allowed_map, ensure_ascii=False)}

TOP-K CQs per inference: {k}

INPUT:
CLAIMS:
{json.dumps(claims_json, ensure_ascii=False)}
INFERENCES (each has rule_type):
{json.dumps(infs_json, ensure_ascii=False)}

ORIGINAL ARGUMENT TEXT (may include explicit answers like 'CQ: <id> — ...'):
{original_text}

TASK:
For each inference, output a JSON object:
  - scheme_id: choose ONE from allowed_map[rule_type]
  - required_cqs: list of up to TOP-K CQ ids *from that scheme* that are most relevant here
Do not include more than TOP-K CQs for any single inference.

Return JSON with schema: {{"items":[...]}} only.
"""

        resp = generate_content(self.client, contents=prompt, config=self.config)
        analysis = SchemeAnalysis.model_validate_json(resp.text)

        # Aggregate per conclusion id (to_claim): union required CQs across its incoming inferences.
        per_to_required: Dict[str, List[str]] = {}
        for item in analysis.items:
            cur = per_to_required.setdefault(item.to_claim, [])
            for cq in item.required_cqs:
                if cq not in cur:
                    cur.append(cq)

        # Parse explicit CQ answers present in the text, e.g., "CQ: alternatives — ..."
        explicit = set(m.lower() for m in re.findall(r"^\\s*CQ\\s*:\\s*([A-Za-z0-9_\\-]+)", original_text, flags=re.M))

        requires: List[Tuple[str, str]] = []
        answered: List[Tuple[str, str]] = []

        for to_claim, cqs in per_to_required.items():
            # Cap to top-k per conclusion
            capped = cqs[:k] if k > 0 else []
            for cq in capped:
                requires.append((to_claim, cq))
                if cq.lower() in explicit:
                    answered.append((to_claim, cq))

        return SchemeFacts(requires=requires, answered=answered, raw_items=list(analysis.items))
