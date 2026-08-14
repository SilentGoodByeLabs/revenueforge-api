import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

SECRET_PATTERNS = [
    r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{6,}['\"]",
    r"(?i)(api[_-]?key|apikey)\s*=\s*['\"][^'\"]{10,}['\"]",
    r"(?i)(secret|token)\s*=\s*['\"][^'\"]{10,}['\"]",
    r"(?i)bearer\s+[a-zA-Z0-9\-_.]{20,}",
]

SKIP_DIRS = {".venv", "node_modules", "__pycache__", ".git", "static"}


def scan_secrets():
    findings = []
    for path in BASE.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in ("security.py",):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for pat in SECRET_PATTERNS:
                if re.search(pat, line) and "os.getenv" not in line and "os.environ" not in line and "Form(" not in line and "placeholder" not in line:
                    findings.append({
                        "file": str(path.relative_to(BASE)),
                        "line": i,
                        "issue": "Possible hardcoded secret",
                        "snippet": line.strip()[:80],
                    })
    return findings


def check_gitignore():
    gi = BASE / ".gitignore"
    required = [".env", "data/", "logs/", "__pycache__/", "*.pyc", ".venv/"]
    if not gi.exists():
        return {"ok": False, "missing_file": True, "missing_entries": required}
    content = gi.read_text()
    missing = [r for r in required if r not in content]
    return {"ok": not missing, "missing_file": False, "missing_entries": missing}


def check_env_usage():
    env = BASE / ".env"
    issues = []
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key and ("TOKEN" in key.upper() or "KEY" in key.upper() or "PASSWORD" in key.upper()):
                    issues.append(f".env holds secret '{key}' — keep it git-ignored and never share it.")
    return issues


def run_audit():
    return {
        "secrets": scan_secrets(),
        "gitignore": check_gitignore(),
        "env": check_env_usage(),
    }
