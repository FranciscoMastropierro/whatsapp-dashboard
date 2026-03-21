"""HTTP client for the chatbot dashboard API (GET only)."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx


def resolve_base_url(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip().rstrip("/")
    try:
        import streamlit as st

        secrets_url = st.secrets.get("API_BASE_URL")
    except Exception:
        secrets_url = None
    raw = secrets_url or os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
    return raw.rstrip("/")


def get_json(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
) -> dict[str, Any]:
    """GET JSON from API. Drops None values and empty-string values from params."""
    base = resolve_base_url(base_url)
    url = urljoin(base + "/", path.lstrip("/"))
    clean: dict[str, Any] = {}
    if params:
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            clean[k] = v
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, params=clean or None)
        r.raise_for_status()
        return r.json()


def health_ok(base_url: str | None = None) -> bool:
    try:
        base = resolve_base_url(base_url)
        with httpx.Client(timeout=5.0) as client:
            r = client.get(urljoin(base + "/", "health"))
            if r.status_code != 200:
                return False
            data = r.json()
            return data.get("status") == "ok"
    except Exception:
        return False
