import os

from .base import BaseLLM


def get_llm() -> BaseLLM:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        from .openai_client import OpenAIClient
        return OpenAIClient()

    if provider == "ollama":
        from .ollama_client import OllamaClient
        return OllamaClient()

    raise ValueError(
        "Unsupported LLM_PROVIDER. Use 'openai' or 'ollama'."
    )
