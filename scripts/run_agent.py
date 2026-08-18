"""rf-agent: owner's autonomous agent = job search + product advertising."""
import time, json, urllib.request
from datetime import datetime
from app.core.db import SessionLocal
from app.core.models import Job
from app.core.advertise import advertise_owner

def scan_jobs():
    s = SessionLocal(); added = 0
    def add(t, u, p):
        nonlocal added
        if not u or s.query(Job).filter_by(url=u).first(): return
        s.add(Job(title=t[:200], url=u, platform=p, opportunity_score=70, description="Job posting found on "+p)); added += 1
    try:
        with urllib.request.urlopen("https://hn.algolia.com/api/v1/search?query=python+developer&tags=story", timeout=12) as r:
            for h in json.loads(r.read())["hits"][:6]:
                if h.get("url"): add(h.get("title"), h["url"], "HackerNews")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://www.reddit.com/r/PythonJobs.json", timeout=12) as r:
            for c in json.loads(r.read())["data"]["children"][:6]:
                d = c["data"]; add(d.get("title"), "https://reddit.com" + d.get("permalink"), "Reddit")
    except Exception: pass
    s.commit(); s.close(); return added

if __name__ == "__main__":
    print("rf-agent active: job search + product advertising (respects toggle). Ctrl+C to stop.")
    while True:
        try:
            a = scan_jobs()
            n = advertise_owner()   # only advertises when toggle ON
            print(f"[{datetime.now():%H:%M:%S}] jobs+{a} advertised+{n}")
        except Exception as e:
            print("agent error:", str(e)[:80])
        time.sleep(600)
