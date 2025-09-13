# llm_argir.py
# -*- coding: utf-8 -*-
"""
LLM-first NL → ARG-IR parser (no heuristics, no pseudo tokens).
- Delegates all labeling (rule/type/scheme) to your LLM.
- Uses your llm.py: init_llm_client(), generate_content(...)
- Returns a typed ArgumentIR via arg_ir.load_argument_ir
"""

from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from google.genai import types

from llm import init_llm_client, generate_content
from arg_ir import load_argument_ir, ArgumentIR

# ---------- Pydantic schema that the model will fill ----------

class PropositionModel(BaseModel):
    id: str = Field(description='Proposition id (e.g., "p1", "p2", ...).')
    text: str = Field(description="Verbatim text from the input (no paraphrase, no pseudo tokens).")

class FOLPayloadModel(BaseModel):
    premises: List[str] = Field(default_factory=list, description="Strict premises (mini-FOL), only if truly deductive.")
    conclusion: str = Field(description="Strict conclusion (mini-FOL).")

RuleLiteral = Literal["strict", "defeasible"]
TypeLiteral = Literal[
    "deductive", "practical", "causal", "inductive", "analogical", "expert", "statistical", "other"
]

class InferenceModel(BaseModel):
    id: str = Field(description='Inference id (e.g., "i1", "i2", ...).')
    from_ids: List[str] = Field(description="List of proposition ids that support this inference.")
    to: str = Field(description="The proposition id this inference concludes.")
    rule: RuleLiteral = Field(description='Use "strict" ONLY for valid deductive steps; otherwise "defeasible".')
    type: TypeLiteral = Field(description="Kind of reasoning; e.g., practical for normative should/ought conclusions.")
    scheme: str = Field(description="Name of the scheme, e.g., Syllogism, ModusPonens, PracticalReasoning, etc.")
    fol: Optional[FOLPayloadModel] = Field(
        default=None,
        description="Present ONLY if rule=strict and you are confident about a machine-checkable derivation."
    )

class ARGIRModel(BaseModel):
    propositions: List[PropositionModel]
    inferences: List[InferenceModel]
    targets: List[str] = Field(description="Ids of the main claim(s) being argued for.")

# ---------- Prompt ----------

_PROMPT = r"""
You convert an argument written in natural language (NL) into a JSON Argument IR (ARG-IR).

REQUIREMENTS
- Do NOT paraphrase. Use the user's words verbatim for each proposition "text".
- Do NOT invent pseudo tokens (e.g., it_is_raining). Keep plain NL strings.
- Use ids "p1", "p2", ... for propositions; "i1", "i2", ... for inferences.
- Provide exactly one JSON object matching this schema:

{
  "propositions": [{"id": "p1", "text": "<verbatim>"}, ...],
  "inferences": [
    {
      "id": "i1",
      "from_ids": ["p?", "p?"],
      "to": "p?",
      "rule": "strict" | "defeasible",
      "type": "deductive" | "practical" | "causal" | "inductive" | "analogical" | "expert" | "statistical" | "other",
      "scheme": "Syllogism" | "ChainedSyllogism" | "ModusPonens" | "ModusTollens" | "PracticalReasoning" | "Causal" | "Analogical" | "StatisticalGeneralization" | "ExpertOpinion" | "Other",
      "fol": { "premises": [...], "conclusion": "..." }  // OPTIONAL: include only for truly strict steps
    }
  ],
  "targets": ["p?"]
}

GUIDANCE
- If the conclusion is normative/policy (contains "should/ought/must/recommend/ban/allow"), use type="practical",
  scheme="PracticalReasoning", and rule="defeasible".
- Use rule="strict" ONLY for clear deductive patterns (e.g., Syllogism, ModusPonens).
- Include "fol" ONLY if you are confident the strict step is machine-provable.

Return ONLY JSON (no commentary, no code fences).

TEXT:
<<<
{TEXT}
>>>
"""

# ---------- Runner ----------

def llm_to_argir(text: str) -> ArgumentIR:
    client = init_llm_client()
    cfg = types.GenerateContentConfig(
        temperature=0.0,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json",
        response_schema=ARGIRModel,   # <- model-enforced JSON
    )
    prompt = _PROMPT.replace("{TEXT}", text.strip())
    resp = generate_content(client, contents=prompt, config=cfg)

    # The wrapper returns a .text JSON string when response_schema is set
    model_obj = ARGIRModel.model_validate_json(resp.text)
    data: Dict[str, Any] = model_obj.model_dump()

    # Let the existing loader build the typed IR used by the rest of the pipeline
    return load_argument_ir(data)
