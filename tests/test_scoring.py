import unittest
from types import SimpleNamespace

from app.core.scoring import analyze_job


class ScoringTests(unittest.TestCase):
    def test_scam_skip(self):
        job = SimpleNamespace(
            title="Easy copy paste",
            description="Pay a fee then earn $5000 daily. whatsapp: +2348000000000",
            required_skills="",
            budget_text="",
            platform="manual",
        )

        result = analyze_job(job)

        self.assertGreaterEqual(result["scam_risk"], 60.0)
        self.assertEqual(result["recommendation"], "SKIP")

    def test_reasonable_automation_job(self):
        job = SimpleNamespace(
            title="Python API integration automation",
            description=(
                "We need Python automation to connect our CRM API to Google Sheets "
                "using webhooks. Scope, deliverables, and timeline are clear. "
                "Long-term ongoing support possible."
            ),
            required_skills="python api crm webhook google sheets",
            budget_text="Fixed $1200",
            platform="Upwork",
        )

        result = analyze_job(job)

        self.assertGreaterEqual(result["opportunity_score"], 50.0)
        self.assertIn(result["recommendation"], ["APPLY", "REVIEW"])


if __name__ == "__main__":
    unittest.main()
