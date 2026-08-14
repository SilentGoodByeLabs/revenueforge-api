import requests
from abc import ABC, abstractmethod

class BaseAIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

class MockProvider(BaseAIProvider):
    def generate(self, prompt: str) -> str:
        return f"[MOCK AI] Processed prompt of {len(prompt)} chars. Replace with real AI in production."

class OllamaProvider(BaseAIProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            return f"[AI ERROR] Ollama failed: {str(e)}"
