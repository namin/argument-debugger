
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import List, Dict, Tuple
from pydantic import BaseModel, Field
from google.genai import types
from llm import init_llm_client, generate_content

# -----------------------------
# Pydantic schemas for LLM I/O
# -----------------------------

class SchemeItem(BaseModel):
    from_claims: List[str] = Field(description="IDs of premises used in this inference")
    to_claim: str = Field(description="ID of the conclusion this inference aims to support")
    scheme_id: str = Field(description="One of the allowed scheme ids from schemes.json")
    required_cqs: List[str] = Field(default_factory=list, description="Critical Questions (ids) that must be answered for this inference to stand")
    answered_cqs: List[str] = Field(default_factory=list, description="Subset of required_cqs that are answered explicitly in the argument text")

class SchemeAnalysis(BaseModel):
    items: List[SchemeItem] = Field(default_factory=list)

# -----------------------------
# Runtime container for results
# -----------------------------

@dataclass
class SchemeFacts:
    # Facts to emit into ASP
    requires: List[Tuple[str, str]]  # (to_claim, cq_id)
    answered: List[Tuple[str, str]]  # (to_claim, cq_id)
    # For UI/debugging
    items: List[SchemeItem]

# -----------------------------
# Main classifier
# -----------------------------

class SchemeAssigner:
    """
    LLM-driven scheme classifier that:
      - assigns a scheme to each inference,
      - selects applicable critical questions (CQs) from schemes.json,
      - marks which CQs are answered in the text (explicit 'CQ: id — ...' or implicit).
    It uses the *same* generate_content() library calls as the rest of ad.py.
    """

    def __init__(self, schemes_path: str = "schemes.json", temperature: float = 0.0):
        with open(schemes_path, "r", encoding="utf-8") as f:
            self.schemes = json.load(f)
        self.client = init_llm_client()
        self.config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=SchemeAnalysis,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )

    def analyze(self, argument, original_text: str) -> SchemeFacts:
        """
        argument: the parsed Argument object from ArgumentParser.parse_argument()
        original_text: the original NL block (used to detect explicit CQ: answers)
        Returns SchemeFacts with requires/answered facts to add to ASP.
        """
        # Prepare a compact description of allowed schemes and CQ ids for the LLM.
        allowed = {k: [cq["id"] for cq in v.get("critical_questions", [])]
                   for k, v in self.schemes.items()}

        # Build a JSON-friendly snapshot of claims and inferences
        claims_json = [{"id": c.id, "content": c.content, "type": c.type} for c in argument.claims]
        infs_json = [{"from_claims": i.from_claims, "to_claim": i.to_claim, "rule_type": i.rule_type}
                     for i in argument.inferences]

        prompt = f"""
You are classifying *inferences* in an argument into standard argumentation schemes and listing Critical Questions (CQs).
Use only scheme_ids from this set (keys): {list(allowed.keys())}.
For each chosen scheme, the only allowed CQ ids are: {allowed}.

INPUT (claims and inferences):
CLAIMS_JSON:
{json.dumps(claims_json, ensure_ascii=False)}
INFERENCES_JSON:
{json.dumps(infs_json, ensure_ascii=False)}

ORIGINAL ARGUMENT TEXT (may include explicit CQ answers like "CQ: alternatives — ..."):
{original_text}

TASK:
For each inference (each element of INFERENCES_JSON), output a SchemeItem with:
  - scheme_id: one of the allowed keys
  - required_cqs: the subset of the scheme's CQ ids that are actually relevant here
  - answered_cqs: the subset of required_cqs explicitly answered by the text above
    (If the text contains a line like "CQ: <id> — ..." treat that CQ as answered.)

CONSTRAINTS:
- required_cqs must be a subset of the scheme's allowed CQ ids.
- answered_cqs must be a subset of required_cqs.
- Return strictly valid JSON for the provided schema.
"""

        resp = generate_content(self.client, contents=prompt, config=self.config)
        analysis = SchemeAnalysis.model_validate_json(resp.text)

        requires: List[Tuple[str, str]] = []
        answered: List[Tuple[str, str]] = []
        for item in analysis.items:
            for cq in item.required_cqs:
                requires.append((item.to_claim, cq))
            for cq in item.answered_cqs:
                answered.append((item.to_claim, cq))

        return SchemeFacts(requires=requires, answered=answered, items=list(analysis.items))

    @staticmethod
    def emit_asp_facts(facts: SchemeFacts, q):
        """
        Turn SchemeFacts into ASP facts using the q() escaping function from ad.py.
        We purposely use (to_claim, cq_id) pairs to avoid introducing inference IDs.
        """
        lines = []
        for (to_claim, cq) in facts.requires:
            lines.append(f"requires_cq({q(to_claim)},{q(cq)}).")
        for (to_claim, cq) in facts.answered:
            lines.append(f"answered_cq({q(to_claim)},{q(cq)}).")
        return "\n".join(lines) + ("\n" if lines else "")

# Optional: minimal ASP rules you can splice into your program builder.
SCHEMES_LP = r"""
% === Scheme CQ enforcement ===
% Facts expected:
%   requires_cq(To, CqId).
%   answered_cq(To, CqId).

% If any CQ required for To is unanswered, disable all inferences into To.
disabled_inference(F, To) :- inference(F, To), requires_cq(To, Q), not answered_cq(To, Q).

% Report as an issue
missing_cq(To, Q) :- requires_cq(To, Q), not answered_cq(To, Q).
#show missing_cq/2.
"""
