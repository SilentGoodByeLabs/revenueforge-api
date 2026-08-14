import unittest
import os
from app.ai.factory import get_ai_provider

class AIFactoryTests(unittest.TestCase):
    def test_default_is_mock(self):
        os.environ["AI_PROVIDER"] = "mock"
        provider = get_ai_provider()
        response = provider.generate("Test prompt")
        self.assertIn("[MOCK AI]", response)

    def test_ollama_initializes(self):
        os.environ["AI_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = "test-model"
        provider = get_ai_provider()
        self.assertEqual(provider.model, "test-model")
        # We don't actually call generate() here to avoid requiring Ollama to be running during tests
        
        # Reset env
        os.environ["AI_PROVIDER"] = "mock"

if __name__ == "__main__":
    unittest.main()
