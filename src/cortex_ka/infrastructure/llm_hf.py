"""Hugging Face Inference API provider implementing LLMPort (Router-based)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterator, Optional

import httpx

from ..domain.ports import LLMPort


class HFLLM(LLMPort):
    """Hugging Face text generation using Inference API Router.

    Expects HF_API_KEY via parameter or environment. Default model can be overridden
    via CKA_HF_MODEL or HF_MODEL. Supports automatic fallback across candidates.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        env_model = os.getenv("CKA_HF_MODEL") or os.getenv("HF_MODEL")
        self.api_key = (api_key or os.getenv("HF_API_KEY") or "").strip()
        # Optional preferred model (will be validated against Router /v1/models)
        self.model = (model or env_model or "").strip()
        self._client = httpx.Client(timeout=20)
        self._last_status: int | None = None
        self._last_error: str | None = None
        self._ROUTER_MODELS = "https://router.huggingface.co/v1/models"
        self._ROUTER_CHAT = "https://router.huggingface.co/v1/chat/completions"

    def healthy(self) -> bool:  # type: ignore[override]
        if not self.api_key:
            self._last_error = "missing_key"
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            # Simple, quick health: list models from Router /v1
            r = self._client.get(self._ROUTER_MODELS, headers=headers)
            self._last_status = r.status_code
            if r.status_code == 200:
                self._last_error = None
                # Optionally prime a supported model if none set
                if not self.model:
                    self.model = self._pick_supported_model(r.json()) or ""
                return True
            if r.status_code == 401:
                self._last_error = "unauthorized"
            elif r.status_code == 403:
                self._last_error = "forbidden"
            else:
                self._last_error = f"status_{r.status_code}"
            return False
        except Exception as e:
            self._last_error = f"exception:{type(e).__name__}"
            return False

    # --- Internal helpers (keep small for readability) ---
    def _pick_supported_model(self, models_payload: Dict[str, Any]) -> str:
        try:
            data = models_payload.get("data", [])
            if not isinstance(data, list):
                return ""

            def ok_outputs(m: Dict[str, Any]) -> bool:
                outputs = (m.get("architecture", {}) or {}).get("output_modalities", [])
                return isinstance(outputs, list) and ("text" in outputs)

            def live(m: Dict[str, Any]) -> bool:
                providers = m.get("providers", []) or []
                return any((p or {}).get("status") == "live" for p in providers)

            def bad_id(mid: str) -> bool:
                s = (mid or "").lower()
                return any(x in s for x in ["thinking", "ocr", "vision"])  # avoid CoT/vision models

            def good_id(mid: str) -> bool:
                s = (mid or "").lower()
                return any(x in s for x in ["instruct", "chat"])  # prefer instruct/chat

            # Pass 1: prefer instruct/chat without thinking/ocr
            for m in data:
                mid = m.get("id", "")
                if not mid or bad_id(mid):
                    continue
                if ok_outputs(m) and live(m) and good_id(mid):
                    return mid
            # Pass 2: any non-thinking text model
            for m in data:
                mid = m.get("id", "")
                if not mid or bad_id(mid):
                    continue
                if ok_outputs(m) and live(m):
                    return mid
            return ""
        except Exception:
            return ""

    def generate(self, prompt: str) -> str:  # type: ignore[override]
        if not self.api_key:
            raise RuntimeError("HF_API_KEY missing")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        self._ensure_model(headers)
        payload = self._build_chat_payload(prompt)
        r = self._post_chat(headers, payload)
        if r.status_code == 401:
            raise RuntimeError("Unauthorized HF API key")
        r.raise_for_status()
        return self._extract_text(r.json())

    def _ensure_model(self, headers: Dict[str, str]) -> None:
        if self.model:
            return
        resp = self._client.get(self._ROUTER_MODELS, headers=headers)
        if resp.status_code == 200:
            self.model = self._pick_supported_model(resp.json())
        if not self.model:
            raise RuntimeError("No supported HF Router model available for this token")

    def _build_chat_payload(self, prompt: str) -> Dict[str, Any]:
        """Build chat completion payload.

        Note: The RAG prompt already includes system instructions via build_prompt(),
        so we only pass a minimal system message here. The full prompt with context
        and instructions is in the user message.
        """
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente profesional. Responde en español de forma clara y COMPLETA. Usa UN SOLO salto de linea entre parrafos. Para formulas matematicas usa LaTeX: $P(x)=\\frac{e^{-\\lambda}\\lambda^x}{x!}$. Siempre termina tus respuestas, nunca las dejes incompletas.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": int(os.getenv("CKA_MAX_OUTPUT_TOKENS", "8192")),
            "temperature": float(os.getenv("CKA_TEMPERATURE", "0.3")),
        }

    def _post_chat(self, headers: Dict[str, str], payload: Dict[str, Any]) -> httpx.Response:
        # Try up to 2 models if the chosen one is not supported
        response = self._client.post(self._ROUTER_CHAT, headers=headers, json=payload)
        if response.status_code == 400 and "model_not_supported" in response.text:
            mlist = self._client.get(self._ROUTER_MODELS, headers=headers)
            if mlist.status_code == 200:
                new_model = self._pick_supported_model(mlist.json())
                if new_model and new_model != payload.get("model"):
                    self.model = new_model
                    payload["model"] = new_model
                    response = self._client.post(self._ROUTER_CHAT, headers=headers, json=payload)
        return response

    def _extract_text(self, data: Dict[str, Any]) -> str:
        # Extract a best-effort text from OpenAI-compatible response shapes.
        # Use a configurable max length to avoid aggressive truncation.
        max_chars = int(os.getenv("CKA_EXTRACT_MAX_CHARS", "16000"))
        try:
            choices = data.get("choices") or []
            if not choices:
                return str(data)[:max_chars]
            first = choices[0]
            if not isinstance(first, dict):
                return str(data)[:max_chars]
            # 1) message.content
            msg = first.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()[:max_chars]
                # Nota: intencionalmente NO exponemos reasoning_content.
            # 3) choice-level content
            c = first.get("content")
            if isinstance(c, str) and c.strip():
                return c.strip()[:max_chars]
            # 4) text field fallback
            t = first.get("text")
            if isinstance(t, str) and t.strip():
                return t.strip()[:max_chars]
            return str(data)[:max_chars]
        except Exception:
            return str(data)[:max_chars]

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Generate completion with real streaming. Yields tokens as they arrive."""
        if not self.api_key:
            raise RuntimeError("HF_API_KEY missing")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        self._ensure_model(headers)
        payload = self._build_chat_payload(prompt)
        payload["stream"] = True  # Enable streaming

        # Use streaming client
        with httpx.Client(timeout=60) as client:
            with client.stream("POST", self._ROUTER_CHAT, headers=headers, json=payload) as response:
                if response.status_code == 401:
                    raise RuntimeError("Unauthorized HF API key")
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
