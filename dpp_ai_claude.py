"""Claude provider for the optional AI features (official Anthropic SDK).

Credentials are resolved by the SDK from the environment (ANTHROPIC_API_KEY,
or an ``ant auth login`` profile); nothing is stored on disk by this app.
"""

from __future__ import annotations

import base64
import json
from typing import Any

DEFAULT_MODEL = "claude-opus-5-5"
# Models that support server-side refusal fallbacks with the "default" routing.
_FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")


class ProviderError(RuntimeError):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _client(timeout: float):
    try:
        import anthropic
    except ImportError as exc:  # optional dependency
        raise ProviderError("Falta el paquete 'anthropic' (pip install anthropic)", 503) from exc
    return anthropic, anthropic.Anthropic(timeout=timeout, max_retries=2)


def generate_json(
    *,
    model: str,
    system: str,
    text: str,
    schema: dict[str, Any],
    image: tuple[bytes, str] | None = None,
    effort: str = "medium",
    # Thinking is always on for Opus 5.5 and counts against max_tokens.
    max_tokens: int = 16000,
    timeout: float = 120.0,
) -> tuple[dict[str, Any], dict[str, int]]:
    """One structured-output call. Returns (parsed JSON, token usage)."""
    anthropic, client = _client(timeout)
    content: list[dict[str, Any]] = []
    if image:
        data, media_type = image
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode("ascii")},
        })
    content.append({"type": "text", "text": text})

    request: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }
    try:
        if model.startswith(_FALLBACK_MODELS):
            # Re-run on Anthropic's recommended model if a safety classifier declines.
            response = client.beta.messages.create(
                **request, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        else:
            response = client.messages.create(**request)
    except anthropic.AuthenticationError as exc:
        raise ProviderError("Clave de Anthropic no válida", 502) from exc
    except anthropic.RateLimitError as exc:
        raise ProviderError("Límite de la API de Anthropic alcanzado; prueba más tarde", 429) from exc
    except anthropic.BadRequestError as exc:
        raise ProviderError(f"Petición rechazada por Anthropic: {exc.message}", 502) from exc
    except anthropic.APIStatusError as exc:
        raise ProviderError(f"Error de Anthropic ({exc.status_code})", 502) from exc
    except anthropic.APIConnectionError as exc:
        raise ProviderError("Sin conexión con la API de Anthropic", 502) from exc

    if response.stop_reason == "refusal":
        raise ProviderError("El modelo declinó responder a esta petición", 422)
    if response.stop_reason == "max_tokens":
        raise ProviderError("Respuesta de IA incompleta (límite de tokens)", 502)
    raw = next((block.text for block in response.content if block.type == "text"), "")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("La IA devolvió JSON no válido", 502) from exc
    usage = {
        "input_tokens": int(getattr(response.usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(response.usage, "output_tokens", 0) or 0),
    }
    return parsed, usage
