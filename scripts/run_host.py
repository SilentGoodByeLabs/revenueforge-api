import time
from datetime import datetime
from app.core.db import SessionLocal
from app.core.models import Member, Subscription, SubscriberProfile, SubscriberJob, Job

LIMITS = {"": 3, "v50": 10, "v300": 50, "v1000": 150}


def scan():
    import json, urllib.request, xml.etree.ElementTree as ET
    added = 0
    s = SessionLocal()
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
            root = ET.fromstring(r.read())
            for it in root.findall(".//item")[:8]:
                add(it.findtext("title"), it.findtext("link"), "WeWorkRemotely")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://www.reddit.com/r/PythonJobs.json", timeout=15) as r:
            for c in json.loads(r.read())["data"]["children"][:8]:
                d = c["data"]; add(d.get("title"), "https://reddit.com"+d.get("permalink"), "Reddit")
    except Exception: pass
    s.commit(); s.close()
    print("scan added", added, "multi-platform jobs")

def deliver():
    s = SessionLocal()
    try:
        members = s.query(Member).all()
        pool = s.query(Job).filter(Job.opportunity_score >= 60).order_by(Job.id.desc()).limit(60).all()
        count = 0
        for m in members:
            if not s.query(SubscriberProfile).filter_by(email=m.email).first():
                continue
            sub = s.query(Subscription).filter_by(email=m.email, status="active").first()
            limit = LIMITS.get(sub.volume if sub else "", 3)
            have = s.query(SubscriberJob).filter_by(owner_email=m.email).count()
            room = limit - have
            if room <= 0: continue
            for j in pool[:room]:
                if s.query(SubscriberJob).filter_by(owner_email=m.email, url=j.url).first(): continue
                s.add(SubscriberJob(owner_email=m.email, title=j.title, url=j.url,
                                    platform=j.platform, score=j.opportunity_score or 0, draft=j.proposal_draft))
                count += 1
        s.commit()
        print(f"[{datetime.now():%H:%M:%S}] delivered {count} result(s)")
    finally:
        s.close()

if __name__ == "__main__":
    print("Host runner active (free + paid). Ctrl+C to stop.")
    while True:
        try:
            scan()
            deliver()
        except Exception as e: print("host error:", e)
        time.sleep(600)
