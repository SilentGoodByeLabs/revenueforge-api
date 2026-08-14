import json
from datetime import datetime, timezone

from app.core.config import LOGS_DIR

AUDIT_PATH = LOGS_DIR / "audit.log"


def log(action: str, agent: str, target: str, result: str = "ok", approval: str = "n/a", error: str = ""):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "agent": agent,
        "target": target,
        "result": result,
        "approval": approval,
        "error": error,
    }
    with open(AUDIT_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
