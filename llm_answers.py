# llm_answers.py
from google.genai import types
from llm import init_llm_client, generate_content

def generate_cq_answer(arg_text: str, cq_key: str, premise_summaries: list[str], conclusion_text: str) -> str:
    client = init_llm_client()
    cfg = types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_budget=0))
    prompt = f"""
You will write ONE sentence that directly answers a policy Critical Question in order to strengthen the argument.

Argument (verbatim):
---
{arg_text}
---

Target conclusion:
---
{conclusion_text}
---

Relevant premises (short list):
- {"\n- ".join(premise_summaries)}

Critical Question: {cq_key}

Rules:
- Write ONE compact sentence that would plausibly satisfy this CQ in context.
- It should look like a warrant/evidence line, not meta-commentary.
- Keep it neutral and minimal. No over-claims; no new topics.

Output: ONE sentence only.
"""
    resp = generate_content(client, contents=prompt, config=cfg)
    return resp.text.strip()
