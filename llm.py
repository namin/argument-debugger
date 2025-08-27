#!/usr/bin/env python3
"""
llm.py — Centralized LLM client initialization for Gemini/Vertex AI

This module provides a unified interface for creating LLM clients across the codebase.
Supports both direct Gemini API access and Vertex AI access.

API Key Resolution (starting with top priority):
  1. Explicit parameter (for standalone/CLI usage)
  2. Request-scoped API key (when used in server context via contextvars)
  3. Environment variables: GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT

If any Gemini API key is provided, it takes precedence over any Google Cloud project set.

Usage:
  from llm import init_llm_client, get_llm_client_or_none, set_request_api_key, generate_content
  
  # Server context - set request-scoped key
  set_request_api_key("user-provided-key")
  client = init_llm_client()  # Uses request-scoped key
  
  # Standalone/CLI context - uses environment variables
  client = init_llm_client()  # Uses env vars
  
  # Explicit override (works in any context)
  client = init_llm_client(api_key="explicit-key")

  # API calls (cached if CACHE_LLM is set)
  response = generate_content(client, model="gemini-2.5-flash", contents=prompt, config=config)
"""
import os
import hashlib
import json
from typing import Optional, Union, Any
from contextvars import ContextVar

# Add caching imports
CACHE_LLM = os.getenv("CACHE_LLM") is not None
if CACHE_LLM:
    try:
        from joblib import Memory
        _HAVE_JOBLIB = True
    except ImportError:
        _HAVE_JOBLIB = False
        Memory = None
else:
    _HAVE_JOBLIB = False
    Memory = None

# Custom exceptions
class LLMConfigurationError(Exception):
    """Raised when LLM client cannot be initialized due to missing configuration."""
    pass

# Try to import Gemini dependencies
_HAVE_GENAI = False
try:
    from google import genai
    from google.genai import types
    _HAVE_GENAI = True
except ImportError:
    _HAVE_GENAI = False
    # Provide minimal stubs for type hints
    genai = None
    types = None

# Default model to use across the codebase
LLM_MODEL = "gemini-2.5-flash"

# Request-scoped API key storage (for server context)
_request_api_key: ContextVar[Optional[str]] = ContextVar('request_api_key', default=None)

# Cache configuration
_CACHE_DIR = os.path.expanduser(os.getenv("LLM_CACHE_DIR", ".cache/llm"))

# Initialize cache if available
_memory = None
if _HAVE_JOBLIB and CACHE_LLM:
    _memory = Memory(_CACHE_DIR, verbose=0)


def set_request_api_key(api_key: Optional[str]) -> None:
    """Set API key for current request context (server use)."""
    _request_api_key.set(api_key)


def get_request_api_key() -> Optional[str]:
    """Get API key from current request context (server use)."""
    try:
        return _request_api_key.get()
    except LookupError:
        # Not in a context where request API key was set (e.g., standalone usage)
        return None


def init_llm_client(api_key: Optional[str] = None, 
                    project: Optional[str] = None,
                    location: Optional[str] = None,
                    required: bool = True):
    """
    Initialize LLM client with fallback to environment variables.
    
    Args:
        api_key: Optional API key (overrides GEMINI_API_KEY env var)
        project: Optional GCP project (overrides GOOGLE_CLOUD_PROJECT env var)
        location: Optional GCP location (overrides GOOGLE_CLOUD_LOCATION env var)
        required: If True, raises exception when LLM unavailable; if False, returns None
        
    Returns:
        genai.Client instance or None (if required=False and unavailable)
        
    Raises:
        RuntimeError: If google.genai not available and required=True
        ValueError: If no valid configuration found and required=True
    """
    if not _HAVE_GENAI:
        if required:
            raise RuntimeError("google.genai not available; install google-genai package or set required=False.")
        return None
    
    # API key resolution priority:
    # 1. Explicit parameter (highest priority)
    # 2. Request-scoped key (server context)
    # 3. Environment variables (fallback)
    gemini_api_key = api_key or get_request_api_key() or os.getenv('GEMINI_API_KEY')
    google_cloud_project = project or os.getenv('GOOGLE_CLOUD_PROJECT')
    google_cloud_location = location or os.getenv('GOOGLE_CLOUD_LOCATION', "us-central1")
    
    try:
        if gemini_api_key:
            return genai.Client(api_key=gemini_api_key)
        elif google_cloud_project:
            return genai.Client(vertexai=True, project=google_cloud_project, location=google_cloud_location)
    except Exception as e:
        if required:
            raise ValueError(f"Failed to initialize LLM client: {e}")
        return None
    
    if required:
        raise LLMConfigurationError("Gemini configuration required, e.g. set GEMINI_API_KEY. Get free key at https://aistudio.google.com/app/apikey.")
    return None


def get_llm_client_or_none(api_key: Optional[str] = None,
                          project: Optional[str] = None,
                          location: Optional[str] = None):
    """
    Convenience function to get LLM client without raising exceptions.
    
    Returns None if LLM is unavailable or configuration is invalid.
    This is equivalent to init_llm_client(..., required=False).
    """
    return init_llm_client(api_key=api_key, project=project, location=location, required=False)


def generate_content(client, contents: Union[str, list], config=None, model: str = LLM_MODEL):
    """
    Cached wrapper for client.models.generate_content calls.
    By design, the cache is over the contents and config only, not the model.
    
    Args:
        client: The genai.Client instance
        contents: Prompt text or list of content parts
        config: Optional GenerateContentConfig
        model: Model name (e.g., "gemini-2.5-flash")
        
    Returns:
        Response object with .text attribute
    """
    if _memory is None:
        # No caching - direct call
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )
    
    @_memory.cache
    def _cached_call(contents: str, config: str):
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )
        return response.text
    
    cached_text = _cached_call(contents, config)
    
    # Return response-like object
    class Response:
        def __init__(self, text):
            self.text = text
    
    return Response(cached_text)

