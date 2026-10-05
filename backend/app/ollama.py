import json
from typing import Any

import httpx

from . import config


class OllamaError(Exception):
    pass


async def _post(path: str, body: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT) as client:
            r = await client.post(config.OLLAMA_URL + path, json=body)
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError("Ollama nicht erreichbar oder Fehler bei der Anfrage.") from exc


async def models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(config.OLLAMA_URL + "/api/tags")
            r.raise_for_status()
            return sorted(m["name"] for m in r.json().get("models", []))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise OllamaError("Ollama nicht erreichbar.") from exc


async def chat(model: str, messages: list[dict], json_mode: bool = False) -> str:
    body: dict[str, Any] = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.2}}
    if json_mode:
        body["format"] = "json"
    data = await _post("/api/chat", body)
    return (data.get("message") or {}).get("content", "")


async def chat_json(model: str, messages: list[dict]) -> dict:
    raw = await chat(model, messages, json_mode=True)
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise OllamaError("Ollama lieferte kein gültiges JSON.") from exc
    if not isinstance(parsed, dict):
        raise OllamaError("Ollama lieferte kein gültiges JSON.")
    return parsed
