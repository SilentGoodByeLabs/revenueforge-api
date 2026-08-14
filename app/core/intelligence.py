import re
from collections import Counter

from app.core.models import Company, Deal, Job, Product, Prospect


def _not_enough(what, need):
    return {"icon": "fa-hourglass-half", "title": f"NOT ENOUGH DATA: {what}", "detail": need, "muted": True}


def analyze_scaling(session):
    insights = []
    jobs = session.query(Job).all()
    deals = session.query(Deal).all()
    won_deals = [d for d in deals if d.stage == "won"]
    products = {p.id: p.name for p in session.query(Product).all()}

    apply_jobs = [j for j in jobs if j.recommendation == "APPLY"]
    if len(jobs) >= 10 and apply_jobs:
        src = Counter((j.source or j.platform or "unknown") for j in apply_jobs)
        best, n = src.most_common(1)[0]
        insights.append({"icon": "fa-tower-broadcast", "title": f"Best source: {best}", "detail": f"{n} APPLY-grade opportunities so far. Hunt here manually too.", "muted": False})
    else:
        insights.append(_not_enough("source ranking", "Track at least 10 jobs with some APPLY picks to rank sources."))

    matched = [j for j in jobs if j.matched_product_id]
    if len(matched) >= 5:
        c = Counter(j.matched_product_id for j in matched)
        pid, n = c.most_common(1)[0]
        insights.append({"icon": "fa-box", "title": f"Most demanded gig: {products.get(pid, pid)}", "detail": f"Matched {n} opportunities. Lead your outreach with this gig.", "muted": False})
    else:
        insights.append(_not_enough("gig ranking", "Need at least 5 product matches to rank your gigs."))

    if len(won_deals) >= 3:
        avg = sum(d.value for d in won_deals) / len(won_deals)
        insights.append({"icon": "fa-sack-dollar", "title": f"Pricing sweet spot: ${avg:,.0f}", "detail": "Your won deals average this. Try +10% on the next similar quote.", "muted": False})
    else:
        insights.append(_not_enough("pricing insight", "Win at least 3 deals to find your pricing sweet spot."))

    companies = {c.id: (c.industry or "").lower() for c in session.query(Company).all()}
    hot = [companies.get(p.company_id, "") for p in session.query(Prospect).all() if p.fit_score >= 60]
    hot = [i for i in hot if i]
    if len(hot) >= 5:
        ind, n = Counter(hot).most_common(1)[0]
        insights.append({"icon": "fa-industry", "title": f"Hottest industry: {ind}", "detail": f"{n} high-fit prospects. Build one more gig aimed at {ind}.", "muted": False})
    else:
        insights.append(_not_enough("industry insight", "Need at least 5 high-fit prospects to rank industries."))

    return insights


TECH_WORDS = ["automation", "python", "api", "excel", "pdf", "ocr", "chatbot", "crm", "zapier", "n8n", "scraping", "invoice", "dashboard", "telegram", "whatsapp", "sheets", "airtable", "hubspot", "shopify", "email"]


def analyze_product_opportunities(session):
    jobs = session.query(Job).all()
    if len(jobs) < 10:
        return None
    covered = set()
    for p in session.query(Product).all():
        for k in (p.keywords or "").lower().split(","):
            k = k.strip()
            if k:
                covered.add(k)
    gap = Counter()
    for j in jobs:
        if j.matched_product_id:
            continue
        text = ((j.title or "") + " " + (j.description or "")).lower()
        for w in TECH_WORDS:
            if w in text and w not in covered:
                gap[w] += 1
    return gap.most_common(6)
