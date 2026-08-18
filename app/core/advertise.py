"""Shared auto-advertise engine (owner + customers)."""
import os, json
from urllib.request import urlopen, Request

def send_telegram(chat, text):
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not tok or not chat: return False
    try:
        url = f"https://api.telegram.org/bot{tok}/sendMessage"
        data = json.dumps({"chat_id": chat if chat.startswith("@") else "@" + chat, "text": text}).encode()
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=8).read(); return True
    except Exception:
        return False

def advertise_owner(force=False):
    from app.core.db import SessionLocal
    from app.core.models import Product, SubscriberProfile
    s = SessionLocal()
    try:
        owner = os.getenv("OWNER_EMAIL", "admin@gmail.com")
        oprof = s.query(SubscriberProfile).filter_by(email=owner).first()
        on = bool(oprof and getattr(oprof, "engine_on", False))
        if not on and not force: return 0
        n = 0
        for pr in s.query(Product).filter_by(status="active").all():
            if not getattr(pr, "advertised", False):
                send_telegram("@" + (os.getenv("TG_CHANNEL", "") or "revenueforge_ads"),
                              "🛒 " + pr.name + " — " + (pr.description or "") + " $" + str(pr.price or 0) +
                              " | contact: " + (getattr(pr, "contact_value", "") or owner))
                pr.advertised = True; n += 1
        s.commit(); return n
    finally:
        s.close()

def advertise_member(email, force=False):
    from app.core.db import SessionLocal
    from app.core.models import SubscriberProduct, SubscriberProfile
    s = SessionLocal()
    try:
        prof = s.query(SubscriberProfile).filter_by(email=email).first()
        on = bool(prof and getattr(prof, "engine_on", False))
        if not on and not force: return 0
        n = 0
        for sv in s.query(SubscriberProduct).filter_by(owner_email=email, status="active").all():
            if not getattr(sv, "advertised", False):
                send_telegram("@" + (os.getenv("TG_CHANNEL", "") or "revenueforge_ads"),
                              "🛒 " + sv.name + " — " + (sv.description or "") + " $" + str(sv.price or 0) +
                              " | contact: " + (sv.contact_value or email))
                sv.advertised = True; n += 1
        s.commit(); return n
    finally:
        s.close()
