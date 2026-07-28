import json
import os
from typing import Any, Dict, Optional
from urllib import request

from .base import BaseLLM
from .prompts import build_chat_prompt


class OllamaClient(BaseLLM):
    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "30"))

    def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        input_text = build_chat_prompt(prompt, context)

        payload = {
            "model": self.model,
            "prompt": input_text,
            "stream": False,
            "options": {"temperature": 0.2},
        }

        req = request.Request(
            url=f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        answer = str(data.get("response", "")).strip()
        if not answer:
            raise RuntimeError("Ollama response did not contain text output")

        return answer
