#!/usr/bin/env python3
# server.py — thin wrapper around unified_core.generate_unified_report
from __future__ import annotations

import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from unified_core import generate_unified_report, HAVE_AD
from llm import set_request_api_key

app = FastAPI(title="Argument Debugger — unified", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UnifiedRequest(BaseModel):
    text: str
    relation: str = "auto"
    use_llm: bool = False
    llm_mode: str = "augment"
    llm_threshold: float = 0.55
    jaccard: float = 0.45
    min_overlap: int = 3
    target: Optional[str] = None
    winners: str = "stable"
    repair: bool = False
    api_key: Optional[str] = None  # Add API key to request body

@app.get("/api/health")
def health():
    return {"ok": True, "ad_available": HAVE_AD}

@app.post("/api/unified")
def api_unified(req: UnifiedRequest, x_api_key: Optional[str] = Header(None)):
    # Set the request-scoped API key (prefer header, fallback to body)
    api_key = x_api_key or req.api_key
    if api_key:
        set_request_api_key(api_key)
    
    try:
        result = generate_unified_report(
            text=req.text,
            relation=req.relation,
            use_llm=req.use_llm,
            llm_mode=req.llm_mode,
            llm_threshold=req.llm_threshold,
            jaccard=req.jaccard,
            min_overlap=req.min_overlap,
            target=req.target,
            winners_semantics=req.winners,
            repair_stance=req.repair,
            filename="session",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unified analysis failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
