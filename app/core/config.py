import os
from pathlib import Path
import json
from functools import lru_cache
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_DIR = BASE_DIR / "config"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

DATABASE_PATH = DATA_DIR / "agent.db"


@lru_cache
def _load_json(path_str: str, default_str: str):
    path = Path(path_str)
    if not path.exists():
        return json.loads(default_str)
    return json.loads(path.read_text(encoding="utf-8"))


def get_categories_config():
    default = '{"priority_categories": [], "skills": [], "red_flags": []}'
    return _load_json(str(CONFIG_DIR / "categories.json"), default)


def get_profile_config():
    default = '{"name": "Your Name", "position": "AI Automation Engineer", "skills": [], "portfolio_url": "", "github_url": "", "case_studies": []}'
    return _load_json(str(CONFIG_DIR / "profile.json"), default)


def get_guardrails_config():
    default = '{"daily_outreach_limit": 10, "daily_application_limit": 15, "followup_max": 3, "cooldown_days": 7}'
    return _load_json(str(CONFIG_DIR / "guardrails.json"), default)
