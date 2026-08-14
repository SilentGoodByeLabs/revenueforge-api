import json
import requests
from pathlib import Path
from app.core.config import CONFIG_DIR

NOTIF_CONFIG_PATH = CONFIG_DIR / "notifications.json"

def get_telegram_config():
    if not NOTIF_CONFIG_PATH.exists():
        return {"bot_token": "", "chat_id": ""}
    return json.loads(NOTIF_CONFIG_PATH.read_text(encoding="utf-8"))

def send_telegram_message(message: str):
    cfg = get_telegram_config()
    token = cfg.get("bot_token")
    chat_id = cfg.get("chat_id")
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        return True
    except Exception:
        return False


def build_briefing_message() -> str:
    """Build a concise morning briefing message from current database state."""
    from app.core.db import SessionLocal
    from app.core.models import Job, Prospect, Deal, Product
    from app.agents.followup_agent import engine as fu_engine
    from app.core.config import get_profile_config

    s = SessionLocal()
    try:
        jobs = s.query(Job).filter(Job.status.in_(["scored", "approved"])).order_by(Job.opportunity_score.desc()).limit(3).all()
        products = {p.id: p.name for p in s.query(Product).all()}
        for j in jobs:
            j._product_name = products.get(j.matched_product_id, "")

        prospects = s.query(Prospect).filter(Prospect.status == "new", Prospect.fit_score >= 60).order_by(Prospect.fit_score.desc()).limit(3).all()

        deals = s.query(Deal).all()
        total_rev = sum(d.value for d in deals if d.stage == "won")
        pipe_val = sum(d.value for d in deals if d.stage not in ("won", "lost"))
        followups_due = fu_engine.list_due()
    finally:
        s.close()

    profile = get_profile_config()
    name = profile.get("name", "Operator")
    lines = [f"☀️ <b>Good morning, {name}</b>", ""]

    lines.append(f"💰 Revenue: ${total_rev:,.0f}  |  Pipeline: ${pipe_val:,.0f}")
    lines.append("")

    if jobs:
        lines.append("<b>🎯 Top jobs to apply to:</b>")
        for j in jobs:
            pitch = f" → pitch <b>{j._product_name}</b>" if j._product_name else ""
            lines.append(f"  • {j.title[:45]} ({j.opportunity_score:.0f}){pitch}")
    else:
        lines.append("<b>🎯 No high-priority jobs waiting.</b>")

    lines.append("")
    if prospects:
        lines.append("<b>📞 Prospects to contact:</b>")
        for p in prospects:
            lines.append(f"  • {p.name} (fit {p.fit_score:.0f})")
    else:
        lines.append("<b>📞 All prospects contacted.</b>")

    lines.append("")
    if followups_due:
        lines.append(f"<b>🔄 {len(followups_due)} follow-ups due today.</b>")
    else:
        lines.append("<b>🔄 No follow-ups due.</b>")

    lines.append("")
    lines.append("Open your Control Center to review.")
    return "\n".join(lines)


def send_morning_briefing() -> bool:
    return send_telegram_message(build_briefing_message())
