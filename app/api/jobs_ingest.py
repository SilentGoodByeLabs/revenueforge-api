from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from app.core.db import SessionLocal
from app.core.models import Job

router = APIRouter(prefix="/jobs", tags=["jobs-ingest"])

class IngestJob(BaseModel):
    title: str
    platform: str
    url: str
    source: Optional[str] = "home-worker"
    description: Optional[str] = ""
    opportunity_score: Optional[float] = 85.0
    recommendation: Optional[str] = "REVIEW"
    client: Optional[str] = None
    budget_text: Optional[str] = None
    required_skills: Optional[str] = None

class IngestRequest(BaseModel):
    jobs: List[IngestJob]
    source: Optional[str] = "home-worker"

@router.post("/ingest")
def ingest_jobs(request: IngestRequest):
    """Accept jobs from private engine (home IP worker). Deduplicates by URL."""
    session = SessionLocal()
    try:
        added = 0
        skipped = 0
        
        for job_data in request.jobs:
            # Check if job already exists (by URL)
            existing = session.query(Job).filter(Job.url == job_data.url).first()
            if existing:
                skipped += 1
                continue
            
            # Create new job with all required fields
            new_job = Job(
                title=job_data.title[:200],
                platform=job_data.platform,
                source=job_data.source,
                url=job_data.url,
                description=job_data.description or "Job from home worker",
                client=job_data.client,
                budget_text=job_data.budget_text,
                required_skills=job_data.required_skills,
                opportunity_score=job_data.opportunity_score,
                recommendation=job_data.recommendation,
                status="new",
                approved=False
            )
            session.add(new_job)
            added += 1
        
        session.commit()
        
        # Cleanup old jobs (older than 24 hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        deleted = session.query(Job).filter(Job.created_at < cutoff).delete()
        
        return {
            "status": "ok",
            "added": added,
            "skipped_duplicates": skipped,
            "cleaned_old": deleted,
            "total_in_db": session.query(Job).count()
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
