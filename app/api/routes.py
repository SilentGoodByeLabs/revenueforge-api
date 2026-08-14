from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel

from app.core.db import SessionLocal
from app.core.models import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobResponse(BaseModel):
    id: int
    title: str
    platform: str
    opportunity_score: float
    recommendation: str
    status: str
    approved: bool

    class Config:
        from_attributes = True

class JobDetailResponse(BaseModel):
    id: int
    title: str
    platform: str
    opportunity_score: float
    recommendation: str
    status: str
    approved: bool
    proposal_draft: str
    reason: str

    class Config:
        from_attributes = True

@router.get("/", response_model=List[JobResponse])
def get_jobs():
    """Fetch all jobs for the approval dashboard."""
    session = SessionLocal()
    try:
        jobs = session.query(Job).order_by(Job.id.desc()).all()
        return jobs
    finally:
        session.close()

@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: int):
    """Fetch full details of a specific job, including the proposal draft."""
    session = SessionLocal()
    try:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    finally:
        session.close()

@router.post("/{job_id}/approve")
def approve_job(job_id: int):
    """Approve a job for manual submission. Does NOT auto-submit."""
    session = SessionLocal()
    try:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        job.approved = True
        job.status = "approved"
        session.commit()
        
        return {
            "message": f"Job {job_id} approved.",
            "action_required": "Submit manually via official platform UI/API."
        }
    finally:
        session.close()
