#!/usr/bin/env python3
"""
llm.py — Centralized LLM client initialization for Gemini/Vertex AI

This module provides a unified interface for creating LLM clients across the codebase.
Supports both direct Gemini API access and Vertex AI access.

Environment variables:
  GEMINI_API_KEY        - Direct Gemini API access
  GOOGLE_CLOUD_PROJECT  - Vertex AI project ID
  GOOGLE_CLOUD_LOCATION - Vertex AI location (default: us-central1)

Usage:
  from llm import init_llm_client, get_llm_client_or_none
  
  # For required LLM access (raises exception if unavailable)
  client = init_llm_client()
  
  # For optional LLM access (returns None if unavailable)
  client = get_llm_client_or_none()
"""
import os
from typing import Optional

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
    
    # Use provided parameters or fall back to environment variables
    gemini_api_key = api_key or os.getenv('GEMINI_API_KEY')
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
        raise ValueError("Gemini configuration required. Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT environment variables.")
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


def is_llm_available() -> bool:
    """Check if LLM dependencies are available."""
    return _HAVE_GENAI


def get_llm_model() -> str:
    """Get the default LLM model name."""
    return LLM_MODEL
