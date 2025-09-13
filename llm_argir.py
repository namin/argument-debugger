# llm_argir.py
# -*- coding: utf-8 -*-
"""
LLM-first NL → ARG-IR with automatic "ensure inference to target" fallback.
- No heuristics; no pseudo tokens; LLM decides rule/type/scheme (and optional FOL for strict).
- If the first pass returns no inferences into any target, run up to two additional strict LLM passes
  that REUSE the same propositions (ids + verbatim text) and require at least one defeasible inference
  concluding into each target.

Matches your llm.py usage:
  - init_llm_client()
  - generate_content(client, contents=prompt, config=types.GenerateContentConfig(...))
with response_schema enforcing JSON.
"""

from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from google.genai import types
import os, json

from llm import init_llm_client, generate_content
from arg_ir import load_argument_ir, ArgumentIR

# ---------- small debug helper ----------
def _dbg(msg: str):
    if os.environ.get("ARGIR_LLM_DEBUG"):
        print(f"[llm-argir] {msg}")

# ---------- Pydantic schema the model fills ----------

class PropositionModel(BaseModel):
    id: str = Field(description='Proposition id ("p1","p2",...).')
    text: str = Field(description="Verbatim text from the input (no paraphrase, no pseudo tokens).")

class FOLPayloadModel(BaseModel):
    premises: List[str] = Field(default_factory=list)
    conclusion: str

RuleLiteral = Literal["strict", "defeasible"]
TypeLiteral = Literal["deductive","practical","causal","inductive","analogical","expert","statistical","other"]

class InferenceModel(BaseModel):
    id: str
    from_ids: List[str]
    to: str
    rule: RuleLiteral
    type: TypeLiteral
    scheme: str
    fol: Optional[FOLPayloadModel] = None

class ARGIRModel(BaseModel):
    propositions: List[PropositionModel]
    inferences: List[InferenceModel] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)

# ---------- First-pass prompt ----------

_PROMPT = r"""
You convert an argument written in natural language (NL) into a JSON Argument IR (ARG-IR).

REQUIREMENTS
- Do NOT paraphrase. Use the user's words verbatim for each proposition "text".
- Do NOT invent pseudo tokens (e.g., it_is_raining). Keep plain NL strings.
- Use ids "p1","p2",... for propositions; "i1","i2",... for inferences.
- Return ONE JSON object with this schema:

{
  "propositions": [{"id":"p1","text":"<verbatim>"}, ...],
  "inferences": [
    {
      "id":"i1",
      "from_ids":["p?","p?"],
      "to":"p?",
      "rule":"strict"|"defeasible",
      "type":"deductive"|"practical"|"causal"|"inductive"|"analogical"|"expert"|"statistical"|"other",
      "scheme":"Syllogism"|"ChainedSyllogism"|"ModusPonens"|"ModusTollens"|"PracticalReasoning"|"Causal"|"Analogical"|"StatisticalGeneralization"|"ExpertOpinion"|"Other",
      "fol":{"premises":[...],"conclusion":"..."}   // OPTIONAL; only if truly strict and machine-provable
    }
  ],
  "targets":["p?"]
}

GUIDANCE
- If a target conclusion is normative/policy (contains "should/ought/must/recommend/ban/allow"),
  use rule="defeasible", type="practical", scheme="PracticalReasoning".
- Use rule="strict" ONLY for clear deductive patterns (e.g., Syllogism, ModusPonens).
- Include "fol" ONLY if you are confident the strict step is machine-provable.
- IMPORTANT: Unless the input is a single unsupported claim, include at least ONE inference concluding into each target.

Return ONLY JSON (no commentary, no code fences).

TEXT:
<<<
{TEXT}
>>>
"""

# ---------- Second-pass prompt (engaged only if needed) ----------

_REPAIR_PROMPT = r"""
You are given the extracted propositions and targets from an argument.
Keep propositions EXACTLY as provided (same ids and verbatim text). Do NOT add, delete, or reword them.

TASK: return a COMPLETE ARG-IR JSON that **adds at least one inference concluding into each target**.
If a target is normative/policy ("should/ought/must/recommend/ban/allow"), use:
  rule="defeasible", type="practical", scheme="PracticalReasoning".

Schema to return:
{
  "propositions": [... exactly as provided ...],
  "inferences": [ ... include at least one inference into each target ... ],
  "targets": [ ... exactly as provided ... ]
}

PROPOSITIONS (id → verbatim text):
{PROP_TABLE}

TARGETS:
{TARGET_LIST}

Rules:
- Use ONLY the proposition ids above inside "from_ids" and "to".
- Do NOT paraphrase any proposition text.
- If uncertain, create ONE defeasible practical inference that collects the most relevant premises into the target.

Return ONLY JSON (no commentary, no code fences).
"""

# ---------- Third-pass prompt (stricter; engaged only if still needed) ----------

_FORCE_PROMPT = r"""
You MUST output a COMPLETE ARG-IR JSON that contains:
- The SAME "propositions" and "targets" as provided (identical ids and verbatim text).
- An "inferences" array with AT LEAST ONE inference whose "to" equals each target id.

If the target is normative/policy ("should/ought/must/recommend/ban/allow"):
  set rule="defeasible", type="practical", scheme="PracticalReasoning".
Otherwise choose the appropriate type/scheme.

Here are the inputs you MUST reuse exactly:

"propositions": [
{PROP_JSON}
],
"targets": {TARGET_JSON}

Now RETURN ONLY ONE JSON object with fields "propositions", "inferences", "targets".
The "inferences" MUST be non-empty and must include at least one entry with {"to": <each target id>}.
Do NOT add or modify any proposition text. Do NOT include commentary or code fences.
"""

# ---------- helpers ----------

def _gen_prop_table(props: List[PropositionModel]) -> str:
    return "\n".join(f"- {p.id}: {p.text}" for p in props)

def _needs_inference_into_target(m: ARGIRModel) -> bool:
    if not m.targets:
        return False
    if not m.inferences:
        return True
    tset = set(m.targets)
    return not any(inf.to in tset for inf in m.inferences)

def _dump_model_obj(label: str, m: ARGIRModel):
    if os.environ.get("ARGIR_LLM_DEBUG"):
        print(f"[llm-argir] {label} JSON:")
        try:
            print(json.dumps(m.model_dump(), ensure_ascii=False, indent=2))
        except Exception:
            pass

# ---------- main ----------

def llm_to_argir(text: str) -> ArgumentIR:
    client = init_llm_client()
    cfg = types.GenerateContentConfig(
        temperature=0.0,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json",
        response_schema=ARGIRModel,
    )

    # Pass 1: full parse
    prompt = _PROMPT.replace("{TEXT}", text.strip())
    resp = generate_content(client, contents=prompt, config=cfg)
    model_obj = ARGIRModel.model_validate_json(resp.text)
    _dbg(f"pass1: inferences={len(model_obj.inferences)} targets={model_obj.targets}")
    _dump_model_obj("pass1", model_obj)

    # Pass 2: only if no inference reaches any target
    if _needs_inference_into_target(model_obj):
        prop_table = _gen_prop_table(model_obj.propositions)
        tgt_list = ", ".join(model_obj.targets) if model_obj.targets else "(none)"
        repair_prompt = _REPAIR_PROMPT.replace("{PROP_TABLE}", prop_table).replace("{TARGET_LIST}", tgt_list)
        resp2 = generate_content(client, contents=repair_prompt, config=cfg)
        model_obj = ARGIRModel.model_validate_json(resp2.text)
        _dbg(f"pass2: inferences={len(model_obj.inferences)} targets={model_obj.targets}")
        _dump_model_obj("pass2", model_obj)

    # Pass 3: stricter requirement if still missing
    if _needs_inference_into_target(model_obj):
        props_json = ",\n".join(
            json.dumps({"id": p.id, "text": p.text}, ensure_ascii=False) for p in model_obj.propositions
        )
        tgt_json = json.dumps(model_obj.targets, ensure_ascii=False)
        force_prompt = _FORCE_PROMPT.replace("{PROP_JSON}", props_json).replace("{TARGET_JSON}", tgt_json)
        resp3 = generate_content(client, contents=force_prompt, config=cfg)
        model_obj = ARGIRModel.model_validate_json(resp3.text)
        _dbg(f"pass3: inferences={len(model_obj.inferences)} targets={model_obj.targets}")
        _dump_model_obj("pass3", model_obj)

    # Final check
    if _needs_inference_into_target(model_obj):
        _dump_model_obj("final_fail", model_obj)
        raise SystemExit(
            "LLM produced ARG-IR with no inference into the target after 3 passes. "
            "Set ARGIR_LLM_DEBUG=1 to inspect the JSON and consider tweaking the input text."
        )

    data: Dict[str, Any] = model_obj.model_dump()
    # --- NORMALIZE KEYS FOR THE LOADER ---
    # Map "from_ids" -> "from" for each inference, since load_argument_ir likely expects "from"
    for inf in data.get("inferences", []):
        if "from" not in inf and "from_ids" in inf:
            inf["from"] = inf["from_ids"]  # do not remove from_ids, but adding "from" is enough
    # -------------------------------------
    return load_argument_ir(data)
