import unittest
import os
from types import SimpleNamespace
from app.core.proposals import generate_proposal

class ProposalTests(unittest.TestCase):
    def test_fallback_to_static_when_mocked(self):
        # Ensure AI is in mock mode
        os.environ["AI_PROVIDER"] = "mock"
        
        job = SimpleNamespace(
            title="Python API integration",
            description="We need to connect our CRM to Google Sheets using webhooks.",
        )
        
        proposal = generate_proposal(job, {"matched_skills": ["python", "api"]})
        
        # Because AI is mocked, it MUST fall back to the static template
        self.assertIn("1. Relevant opening", proposal)
        self.assertIn("Honest positioning", proposal)
        self.assertNotIn("[MOCK AI]", proposal)

if __name__ == "__main__":
    unittest.main()
