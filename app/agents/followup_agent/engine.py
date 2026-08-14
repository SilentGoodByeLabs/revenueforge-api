from datetime import date, datetime, timezone, timedelta

from app.core import audit
from app.core.config import get_guardrails_config, get_profile_config
from app.core.db import SessionLocal
from app.core.models import Company, FollowUp, Prospect

INTERVALS_DAYS = [3, 7, 14]
TERMINAL = {"replied", "won", "lost", "do_not_contact"}


def plan_followups(prospect_id):
    session = SessionLocal()
    try:
        p = session.get(Prospect, prospect_id)
        if not p:
            return {"ok": False, "message": "Prospect not found."}
        if p.opted_out or p.status == "do_not_contact":
            return {"ok": False, "message": "Blocked: opted out."}
        if session.query(FollowUp).filter_by(prospect_id=prospect_id).count():
            return {"ok": False, "message": "Follow-ups already scheduled."}
        g = get_guardrails_config()
        n = min(int(g.get("followup_max", 3)), len(INTERVALS_DAYS))
        now = datetime.now(timezone.utc)
        for i in range(n):
            session.add(FollowUp(prospect_id=prospect_id, step=i + 1, due_date=now + timedelta(days=INTERVALS_DAYS[i])))
        session.commit()
        audit.log("plan_followups", "followup_agent", f"prospect#{prospect_id}", result=f"{n} scheduled")
        return {"ok": True, "message": f"{n} follow-ups scheduled."}
    finally:
        session.close()


def list_due():
    session = SessionLocal()
    try:
        out = []
        today = date.today()
        for f in session.query(FollowUp).filter_by(status="planned").all():
            p = session.get(Prospect, f.prospect_id)
            if p and (p.opted_out or p.status in TERMINAL):
                f.status = "skipped"
                continue
            if f.due_date and f.due_date.date() <= today:
                out.append({"fu": f, "prospect": p})
        session.commit()
        return out
    finally:
        session.close()


def draft_followup(fu_id):
    session = SessionLocal()
    try:
        f = session.get(FollowUp, fu_id)
        if not f:
            return {"ok": False, "message": "Not found."}
        p = session.get(Prospect, f.prospect_id)
        if not p or p.opted_out or p.status in TERMINAL:
            f.status = "skipped"
            session.commit()
            return {"ok": False, "message": "Blocked: prospect opted out or closed."}
        first = (p.name or "").split()[0] if p.name else ""
        sender = get_profile_config().get("name", "")
        f.draft = (
            (f"Hi {first}," if first else "Hi,")
            + "\n\nJust floating this back to the top of your inbox. If now is not the time, reply \"not now\" and I will pause.\n\n- "
            + (sender or "RevenueForge")
        )
        session.commit()
        return {"ok": True, "message": "Draft ready."}
    finally:
        session.close()


def mark_sent(fu_id):
    session = SessionLocal()
    try:
        f = session.get(FollowUp, fu_id)
        if f:
            f.status = "sent"
            f.sent_at = datetime.now(timezone.utc)
            session.commit()
            audit.log("followup_sent", "human", f"followup#{fu_id}")
        return {"ok": True}
    finally:
        session.close()


def all_followups():
    session = SessionLocal()
    try:
        return session.query(FollowUp).order_by(FollowUp.id.desc()).all()
    finally:
        session.close()
