"""Minimal client for any OpenAI-compatible chat endpoint (Ollama, LM Studio,
Mistral La Plateforme, Hugging Face TGI, ...). Configured only through env vars,
never through code: see .env.example."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator

import httpx
from dotenv import load_dotenv

load_dotenv()


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self) -> None:
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "qwen2.5:3b")
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.timeout = float(os.getenv("LLM_TIMEOUT", "180"))

    def _payload(self, messages: list[dict], stream: bool) -> dict:
        return {"model": self.model, "messages": messages, "temperature": 0.1,
                "stream": stream}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def chat(self, messages: list[dict]) -> str:
        return "".join(self.stream(messages))

    def stream(self, messages: list[dict]) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        try:
            with httpx.stream("POST", url, json=self._payload(messages, True),
                              headers=self._headers(), timeout=self.timeout) as r:
                if r.status_code != 200:
                    r.read()
                    raise LLMError(f"{r.status_code}: {r.text[:300]}")
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    delta = json.loads(data)["choices"][0].get("delta", {})
                    if delta.get("content"):
                        yield delta["content"]
        except httpx.HTTPError as exc:
            raise LLMError(f"Modèle injoignable sur {self.base_url} ({exc})") from exc
