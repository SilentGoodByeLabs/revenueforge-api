from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="RevenueForge Approval Center API",
    description="Secure, local-only backend for human-in-the-loop business automation.",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "RevenueForge API is running"}
