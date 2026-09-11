from fastapi import FastAPI
from app.api.routes import router
from app.api.jobs_ingest import router as ingest_router

app = FastAPI(
    title="RevenueForge Approval Center API",
    description="Secure, local-only backend for human-in-the-loop business automation.",
    version="1.0.0"
)

app.include_router(router)
app.include_router(ingest_router)

@app.get("/")
def read_root():
    return {"status": "RevenueForge API is running"}

@app.get("/health")
def health():
    from app.core.db import SessionLocal
    from app.core.models import Job
    session = SessionLocal()
    try:
        count = session.query(Job).count()
        return {"status": "ok", "jobs_count": count, "database": "connected"}
    finally:
        session.close()
