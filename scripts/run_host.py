"""Host runner: delivers results to FREE + PAID members, limited by plan. rf-host"""
import time
from datetime import datetime
from app.core.db import SessionLocal
from app.core.models import Member, Subscription, SubscriberProfile, SubscriberJob, Job

LIMITS = {"": 3, "v50": 10, "v300": 50, "v1000": 150}  # free=3, Starter=10, Growth=50, Agency=150

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
        try: deliver()
        except Exception as e: print("host error:", e)
        time.sleep(600)
