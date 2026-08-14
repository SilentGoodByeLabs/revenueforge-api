"""Standalone script for cron. Run daily at 8 AM."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.notifications.telegram import send_morning_briefing
from app.core import audit

if __name__ == "__main__":
    ok = send_morning_briefing()
    audit.log("morning_briefing", "agent", "telegram", result="sent" if ok else "failed")
    print("Morning briefing:", "sent" if ok else "failed")
    sys.exit(0 if ok else 1)
