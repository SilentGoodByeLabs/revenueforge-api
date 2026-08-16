import os, time, json, urllib.request
from datetime import datetime
from app.core.db import SessionLocal
from app.core.models import Member, Subscription, SubscriberProfile, SubscriberJob, Job

LIMITS = {"": 2, "v50": 10, "v300": 25, "v1000": 60}  # matches per DAY
TG = os.getenv("TELEGRAM_BOT_TOKEN", "")

def send_telegram(chat, text):
    if not TG or not chat: return
    try:
        url = f"https://api.telegram.org/bot{TG}/sendMessage"
        data = json.dumps({"chat_id": chat if chat.startswith("@") else "@" + chat, "text": text}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8).read()
    except Exception as e:
        print("tg alert failed:", str(e)[:80])

def scan():
    import xml.etree.ElementTree as ET
    added = 0; s = SessionLocal()
    def add(title, url, platform):
        nonlocal added
        if not url or s.query(Job).filter_by(url=url).first(): return
        s.add(Job(title=title[:200], url=url, platform=platform, opportunity_score=70)); added += 1
    try:
        with urllib.request.urlopen("https://hn.algolia.com/api/v1/search?query=python+developer&tags=story", timeout=15) as r:
            for h in json.loads(r.read())["hits"][:8]:
                if h.get("url"): add(h.get("title"), h["url"], "HackerNews")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://weworkremotely.com/categories/remote-programming-jobs.rss", timeout=15) as r:
            for it in ET.fromstring(r.read()).findall(".//item")[:8]:
                add(it.findtext("title"), it.findtext("link"), "WeWorkRemotely")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://www.reddit.com/r/PythonJobs.json", timeout=15) as r:
            for c in json.loads(r.read())["data"]["children"][:8]:
                d = c["data"]; add(d.get("title"), "https://reddit.com" + d.get("permalink"), "Reddit")
    except Exception: pass
    s.commit(); s.close(); print("scan added", added)

def deliver():
    s = SessionLocal(); alerts = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        members = s.query(Member).all()
        pool = s.query(Job).filter(Job.opportunity_score >= 60).order_by(Job.id.desc()).limit(60).all()
        count = 0
        for m in members:
            prof = s.query(SubscriberProfile).filter_by(email=m.email).first()
            if not prof: continue
            sub = s.query(Subscription).filter_by(email=m.email, status="active").first()
            active = bool(sub) and (getattr(sub, "expires_at", None) is None or sub.expires_at > datetime.now())
            vol = sub.volume if active else ""
            q = s.query(SubscriberJob).filter_by(owner_email=m.email)
            if hasattr(SubscriberJob, "created_at"):
                q = q.filter(SubscriberJob.created_at >= today)
            room = LIMITS.get(vol, 2) - q.count()
            if room <= 0: continue
            for j in pool[:room]:
                if s.query(SubscriberJob).filter_by(owner_email=m.email, url=j.url).first(): continue
                s.add(SubscriberJob(owner_email=m.email, title=j.title, url=j.url, platform=j.platform,
                                    score=j.opportunity_score or 0, draft=j.proposal_draft))
                count += 1
                if vol in ("v300", "v1000") and prof.telegram:
                    alerts.append((prof.telegram, f"🤖 RevenueForge: new match — {j.title} ({j.platform}). Open your portal for the draft."))
        s.commit(); print(f"[{datetime.now():%H:%M:%S}] delivered {count}")
    finally:
        s.close()
    for chat, text in alerts: send_telegram(chat, text)

if __name__ == "__main__":
    print("Host runner active (scan + daily delivery + Telegram). Ctrl+C to stop.")
    while True:
        try: scan(); deliver()
        except Exception as e: print("host error:", e)
        time.sleep(600)
