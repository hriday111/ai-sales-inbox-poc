from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key: str = "ollama"
    timeout_s: float = 120.0

    @classmethod
    def from_env(cls) -> LLMConfig:
        # Defaults prefer a local llama.cpp OpenAI-compatible server if present;
        # override with OPENAI_BASE_URL / OPENAI_MODEL / OLLAMA_MODEL as needed.
        return cls(
            base_url=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8080/v1").rstrip(
                "/"
            ),
            model=os.getenv(
                "OPENAI_MODEL",
                os.getenv(
                    "OLLAMA_MODEL",
                    "/home/hriday/Downloads/MiniCPM5-2B-Q8_0.gguf",
                ),
            ),
            api_key=os.getenv("OPENAI_API_KEY", "local"),
            timeout_s=float(os.getenv("LLM_TIMEOUT", "180")),
        )


def chat(
    messages: list[dict[str, str]],
    config: LLMConfig | None = None,
    temperature: float = 0.1,
) -> str:
    cfg = config or LLMConfig.from_env()
    url = f"{cfg.base_url}/chat/completions"
    body = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "700")),
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"LLM request failed ({cfg.base_url}, model={cfg.model}). "
            f"Is Ollama running? Try: ollama serve && ollama pull {cfg.model}\n{exc}"
        ) from exc

    try:
        msg = payload["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        if not content:
            # Some local reasoning models put draft text in reasoning_content
            content = (msg.get("reasoning_content") or "").strip()
        if not content:
            raise RuntimeError(f"Empty model content: {payload!r}")
        return content
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM response: {payload!r}") from exc


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in model output:\n{text}")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise TypeError("Parsed JSON is not an object")
    return data
