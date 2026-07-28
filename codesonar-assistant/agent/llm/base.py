from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseLLM(ABC):
    @abstractmethod
    def chat(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a response for a user prompt with optional structured context.
        """
