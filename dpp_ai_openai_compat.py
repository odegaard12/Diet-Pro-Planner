"""OpenAI-compatible provider (Ollama, LM Studio, OpenAI, Gemini's compat endpoint…).

Kept separate from the Claude provider. Useful for a fully local setup:
``DPP_AI_BASE_URL=http://ollama:11434/v1`` + ``DPP_AI_MODEL=llama3.1``.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import requests

from dpp_ai_claude import ProviderError


def generate_json(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    text: str,
    schema: dict[str, Any],
    image: tuple[bytes, str] | None = None,
    max_tokens: int = 4000,
    timeout: float = 120.0,
) -> tuple[dict[str, Any], dict[str, int]]:
    if not base_url or not model:
        raise ProviderError("Configura DPP_AI_BASE_URL y DPP_AI_MODEL", 503)
    user_content: Any = text
    if image:
        data, media_type = image
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"}},
            {"type": "text", "text": text},
        ]
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system + "\nResponde solo con JSON válido que cumpla el esquema."},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_schema", "json_schema": {"name": "result", "strict": True, "schema": schema}},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.post(base_url.rstrip("/") + "/chat/completions", json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise ProviderError("Sin conexión con el proveedor de IA", 502) from exc
    if response.status_code == 429:
        raise ProviderError("Límite del proveedor de IA alcanzado", 429)
    if response.status_code >= 400:
        raise ProviderError(f"Error del proveedor de IA ({response.status_code})", 502)
    try:
        body = response.json()
        raw = body["choices"][0]["message"]["content"] or ""
        start, end = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[start:end + 1] if start >= 0 else raw)
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError("El proveedor de IA devolvió una respuesta no válida", 502) from exc
    usage = body.get("usage") or {}
    return parsed, {
        "input_tokens": int(usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or 0),
    }
