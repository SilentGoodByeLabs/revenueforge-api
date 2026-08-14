import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import Base, engine
import app.core.models  # CRUCIAL: This registers all tables (jobs, followups, etc.)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database tables synchronized successfully. No data lost.")
