"""Thin LLM wrapper. The rest of the project only calls `llm.complete(system, prompt)`."""
import os
import time
from typing import Protocol


class LLM(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...


_TRANSIENT = ("429", "rate", "quota", "503", "unavailable", "overloaded", "timeout", "500")


def _with_backoff(fn, max_retries: int):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:  # provider SDKs raise many exception types
            transient = any(s in str(exc).lower() for s in _TRANSIENT)
            if not transient or attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt * 2)


class GeminiLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 temperature: float = 0.0, max_retries: int = 4):
        from google import genai
        from google.genai import types

        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
        self._types = types
        self._client = genai.Client(api_key=key)
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.temperature = temperature
        self.max_retries = max_retries

    def complete(self, system: str, prompt: str) -> str:
        def call():
            resp = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._types.GenerateContentConfig(
                    system_instruction=system, temperature=self.temperature
                ),
            )
            return (resp.text or "").strip()

        return _with_backoff(call, self.max_retries)


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None, max_retries: int = 4):
        import anthropic

        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to .env.")
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        self.max_retries = max_retries

    def complete(self, system: str, prompt: str) -> str:
        def call():
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in resp.content if b.type == "text").strip()

        return _with_backoff(call, self.max_retries)


def get_llm(provider: str | None = None, model: str | None = None) -> LLM:
    provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
    if provider == "gemini":
        return GeminiLLM(model=model)
    if provider == "anthropic":
        return AnthropicLLM(model=model)
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use 'gemini' or 'anthropic'.")
