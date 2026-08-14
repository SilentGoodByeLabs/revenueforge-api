import re
import sys
import time
from datetime import datetime, timezone

from app.agents.job_agent.ingest import fetch_feed, load_sources, parse_rss
from app.core import audit
from app.core.config import get_categories_config
from app.core.db import SessionLocal
from app.core.models import Job
from app.core.proposals import generate_proposal
from app.core.scoring import analyze_job, apply_analysis
from app.core.product_matcher import match_products
from app.notifications.telegram import send_telegram_message

def clean_html(text):
    return re.sub(r"<[^>]+>", " ", text or "")

def relevance(text):
    cfg = get_categories_config()
    t = text.lower()
    hits = [s for s in cfg.get("skills", []) if s and s in t]
    excluded = [k for k in cfg.get("exclude_keywords", []) if k and k in t]
    return hits, excluded

def ingest_once():
    session = SessionLocal()
    added = 0
    filtered = 0
    try:
        existing = {j.url for j in session.query(Job).all() if j.url}
        for src in load_sources():
            try:
                items = parse_rss(fetch_feed(src["url"]))
            except Exception as e:
                audit.log("ingest_error", "job_agent", src["url"], result="error", error=str(e)[:200])
                continue
            for it in items[: int(src.get("max_items", 10))]:
                link = it["link"]
                if not link or link in existing:
                    continue
                raw_text = (it["title"] or "") + " " + clean_html(it["description"] or "")
                hits, excluded = relevance(raw_text)
                if excluded or len(hits) < 2:
                    filtered += 1
                    continue
                job = Job(
                    title=it["title"][:200] or "Untitled opportunity",
                    platform=src.get("platform", "feed"),
                    source="rss",
                    url=link,
                    description=clean_html(it["description"])[:4000],
                )
                session.add(job)
                session.commit()
                session.refresh(job)
                analysis = analyze_job(job)
                apply_analysis(job, analysis)
                job.proposal_draft = generate_proposal(job, analysis)
                
                # PHASE 2: PRODUCT MATCHING
                match_result = match_products(job.description, session)
                best = match_result.get("best_match")
                if best:
                    job.matched_product_id = best["product_id"]
                    job.product_fit_score = best["score"]
                    job.product_match_reason = " | ".join(best["reasons"])
                    job.sales_angle = best["sales_angle"]
                    
                job.status = "scored"
                session.commit()
                audit.log("auto_ingest", "job_agent", f"job#{job.id}", result=f"{analysis['opportunity_score']:.0f} {analysis['recommendation']}")
                added += 1
                
                # TELEGRAM ALERT TRIGGER
                if analysis["recommendation"] == "APPLY" and analysis["opportunity_score"] >= 75:
                    msg = f"🚨 <b>High-Value Job Found!</b>\n\n<b>Title:</b> {job.title}\n<b>Score:</b> {analysis['opportunity_score']:.0f}/100\n<b>Platform:</b> {job.platform}\n\nOpen your RevenueForge Control Center to review and approve."
                    send_telegram_message(msg)
                    
        audit.log("ingest_cycle", "job_agent", "all_sources", result=f"added={added} filtered={filtered}")
    finally:
        session.close()
    return added, filtered

def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
    print(f"RevenueForge autonomous agent running. Polling every {interval}s. Ctrl+C to stop.")
    consecutive_errors = 0
    while True:
        try:
            added, filtered = ingest_once()
            consecutive_errors = 0
            print(f"[{datetime.now(timezone.utc).isoformat()}] added {added} relevant opportunities, filtered out {filtered} irrelevant")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            consecutive_errors += 1
            audit.log("runner_error", "agent", "loop", result=f"error_{consecutive_errors}", error=str(e)[:200])
            print("runner error:", str(e)[:200])
            if consecutive_errors >= 3:
                from app.notifications.telegram import send_telegram_message
                send_telegram_message("🛑 <b>RevenueForge agent paused.</b> 3 consecutive failures detected — human review required. Check the Audit Log.")
                print("🛑 Agent paused after 3 consecutive failures. Human review required.")
                return
        time.sleep(interval)

if __name__ == "__main__":
    main()
