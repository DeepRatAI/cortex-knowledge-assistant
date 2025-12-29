"""Ollama LLM adapter."""

from __future__ import annotations

import httpx

from ..config import settings
from ..domain.ports import LLMPort


class OllamaLLM(LLMPort):
    """HTTP client for Ollama generate API."""

    def __init__(self) -> None:
        self._base = settings.ollama_url.rstrip("/")
        self._model = settings.ollama_model

    def generate(self, prompt: str) -> str:
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        with httpx.Client(timeout=10) as client:
            try:
                resp = client.post(f"{self._base}/api/generate", json=payload)
                resp.raise_for_status()
            except Exception as exc:  # pragma: no cover - network error path
                raise RuntimeError(f"Ollama request failed: {exc}") from exc
            data = resp.json()
        return data.get("response", "")
