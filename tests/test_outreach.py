import unittest

from app.core.db import Base, engine, SessionLocal
from app.core.models import Company, OutreachMessage, Product, Prospect
from app.agents.sales_agent.outreach import MIN_FIT, draft_for_prospect
from app.ai.voice import contains_ai_speak


class OutreachTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.ids = {"c": [], "p": [], "pr": [], "m": []}

    def tearDown(self):
        for i in self.ids["m"]:
            o = self.session.get(OutreachMessage, i)
            if o:
                self.session.delete(o)
        for i in self.ids["p"]:
            o = self.session.get(Prospect, i)
            if o:
                self.session.delete(o)
        for i in self.ids["c"]:
            o = self.session.get(Company, i)
            if o:
                self.session.delete(o)
        for i in self.ids["pr"]:
            o = self.session.get(Product, i)
            if o:
                self.session.delete(o)
        self.session.commit()
        self.session.close()

    def _make(self, opted_out=False, keywords="automation, crm, lead follow-up", industry="marketing agency"):
        c = Company(name="Test Agency Ltd", industry=industry, notes="They handle lead follow-up manually and want automation.")
        self.session.add(c)
        self.session.commit()
        self.session.refresh(c)
        self.ids["c"].append(c.id)

        p = Prospect(company_id=c.id, name="Jane Doe", email="jane@test.example", opted_out=opted_out, notes="lead follow-up is slow")
        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
        self.ids["p"].append(p.id)

        pr = Product(name="LeadFlow", keywords=keywords, industry=industry, problem_solved="slow lead response", status="active")
        self.session.add(pr)
        self.session.commit()
        self.session.refresh(pr)
        self.ids["pr"].append(pr.id)
        return p

    def _collect_msgs(self, pid):
        msgs = self.session.query(OutreachMessage).filter_by(prospect_id=pid).all()
        self.ids["m"].extend([m.id for m in msgs])
        return msgs

    def test_opted_out_blocked(self):
        p = self._make(opted_out=True)
        result = draft_for_prospect(p.id)
        self.assertFalse(result["ok"])
        self.assertIn("opted out", result["message"])

    def test_good_fit_drafts_human_voice(self):
        p = self._make()
        result = draft_for_prospect(p.id)
        self.assertTrue(result["ok"], result["message"])
        msgs = self._collect_msgs(p.id)
        self.assertEqual(len(msgs), 1)
        self.assertGreaterEqual(msgs[0].fit_score, MIN_FIT)
        self.assertFalse(contains_ai_speak(msgs[0].body))

    def test_low_fit_blocked(self):
        p = self._make(keywords="quantum blockchain nano", industry="mining")
        result = draft_for_prospect(p.id)
        self.assertFalse(result["ok"])
        self.assertIn("fit", result["message"].lower())

    def test_cooldown_blocks_second_draft(self):
        p = self._make()
        self.assertTrue(draft_for_prospect(p.id)["ok"])
        self._collect_msgs(p.id)
        second = draft_for_prospect(p.id)
        self.assertFalse(second["ok"])


if __name__ == "__main__":
    unittest.main()
