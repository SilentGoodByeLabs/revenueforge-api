import os
from app.ai.providers import BaseAIProvider, MockProvider, OllamaProvider

def get_ai_provider() -> BaseAIProvider:
    provider_type = os.getenv("AI_PROVIDER", "mock").lower()

    if provider_type == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama3")
        return OllamaProvider(model=model)
        
    # Default to Mock for safe local development and $0 cost
    return MockProvider()
