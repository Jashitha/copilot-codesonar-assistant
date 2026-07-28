import os
from typing import Any, Dict, Optional

from .base import BaseLLM
from .prompts import build_chat_prompt


class OpenAIClient(BaseLLM):
    def __init__(self, model: Optional[str] = None):
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")
        self.client = OpenAI(api_key=api_key)

    def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        input_text = build_chat_prompt(prompt, context)

        response = self.client.responses.create(
            model=self.model,
            input=input_text,
            temperature=0.2,
        )

        output_text = getattr(response, "output_text", "")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        # Compatibility extraction for SDK variations.
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") == "output_text":
                    text = getattr(content, "text", "")
                    if text:
                        return str(text).strip()

        raise RuntimeError("OpenAI response did not contain text output")
