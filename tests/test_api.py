import unittest
from fastapi.testclient import TestClient
from app.api.main import app
from app.core.db import Base, engine, SessionLocal
from app.core.models import Job

class APITests(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.created_job_ids = []

    def tearDown(self):
        # ONLY delete rows this test created. Never touch real data.
        session = SessionLocal()
        for jid in self.created_job_ids:
            job = session.get(Job, jid)
            if job:
                session.delete(job)
        session.commit()
        session.close()

    def test_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_get_jobs_returns_list(self):
        response = self.client.get("/jobs/")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_approve_job(self):
        session = SessionLocal()
        job = Job(title="TEMP TEST JOB", description="Testing approval endpoint")
        session.add(job)
        session.commit()
        self.created_job_ids.append(job.id)
        job_id = job.id
        session.close()

        response = self.client.post(f"/jobs/{job_id}/approve")
        self.assertEqual(response.status_code, 200)

        session = SessionLocal()
        job = session.get(Job, job_id)
        self.assertTrue(job.approved)
        session.close()

if __name__ == "__main__":
    unittest.main()
