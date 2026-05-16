"""HTTP client for the chatbot dashboard API."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx


class AuthenticationError(Exception):
    """Raised when the API rejects the dashboard session."""


def resolve_base_url(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip().rstrip("/")
    try:
        import streamlit as st

        secrets_url = st.secrets.get("API_BASE_URL")
    except (AttributeError, FileNotFoundError, ImportError, KeyError, RuntimeError):
        secrets_url = None
    raw = secrets_url or os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
    return raw.rstrip("/")


def allow_api_base_url_override() -> bool:
    try:
        import streamlit as st

        secrets_value = st.secrets.get("ALLOW_API_BASE_URL_OVERRIDE")
    except (AttributeError, FileNotFoundError, ImportError, KeyError, RuntimeError):
        secrets_value = None
    raw = secrets_value if secrets_value is not None else os.environ.get("ALLOW_API_BASE_URL_OVERRIDE", "true")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    clean: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        clean[key] = value
    return clean or None


def _auth_headers(auth_token: str | None = None) -> dict[str, str] | None:
    if not auth_token:
        return None
    return {"Authorization": f"Bearer {auth_token}"}


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise AuthenticationError("La sesión no es válida o expiró.")
    response.raise_for_status()


def post_json(
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
    auth_token: str | None = None,
) -> dict[str, Any]:
    base = resolve_base_url(base_url)
    url = urljoin(base + "/", path.lstrip("/"))
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, json=payload or {}, headers=_auth_headers(auth_token))
        _raise_for_status(response)
        return response.json()


def patch_json(
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
    auth_token: str | None = None,
) -> dict[str, Any]:
    base = resolve_base_url(base_url)
    url = urljoin(base + "/", path.lstrip("/"))
    with httpx.Client(timeout=30.0) as client:
        response = client.patch(url, json=payload or {}, headers=_auth_headers(auth_token))
        _raise_for_status(response)
        return response.json()


def get_json(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """GET JSON from API. Drops None values and empty-string values from params."""
    base = resolve_base_url(base_url)
    url = urljoin(base + "/", path.lstrip("/"))
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=_clean_params(params), headers=_auth_headers(auth_token))
        _raise_for_status(response)
        return response.json()


def health_ok(base_url: str | None = None) -> bool:
    try:
        base = resolve_base_url(base_url)
        with httpx.Client(timeout=5.0) as client:
            r = client.get(urljoin(base + "/", "health"))
            if r.status_code != 200:
                return False
            data = r.json()
            return data.get("status") == "ok"
    except (httpx.HTTPError, ValueError):
        return False
