from app.core.product_matcher import match_products

INDUSTRY_SIGNALS = {
    "accounting": ["invoice", "accounting", "bookkeeping", "tax", "receipt", "payroll"],
    "ecommerce": ["shopify", "ecommerce", "e-commerce", "store", "orders", "dropship"],
    "real estate": ["real estate", "property", "listing", "rentals", "realtor"],
    "healthcare": ["clinic", "patient", "medical", "dental", "appointment", "practice"],
    "marketing": ["marketing", "agency", "ads", "campaign", "brand", "social media"],
    "logistics": ["shipping", "logistics", "delivery", "freight", "tracking", "warehouse"],
    "education": ["school", "academy", "course", "students", "training", "tutor"],
    "hospitality": ["hotel", "restaurant", "cafe", "booking", "guest", "menu"],
    "legal": ["law", "legal", "attorney", "law firm", "paralegal"],
}

PAIN_BY_INDUSTRY = {
    "accounting": ["manual invoice data entry", "slow month-end reporting", "chasing missing receipts"],
    "ecommerce": ["order status emails", "abandoned cart follow-up", "inventory sync errors"],
    "real estate": ["slow lead response", "manual listing updates", "scheduling viewings"],
    "healthcare": ["no-show appointments", "manual reminders", "paper intake forms"],
    "marketing": ["manual client reporting", "lead follow-up gaps", "campaign data consolidation"],
    "logistics": ["manual tracking updates", "customer status inquiries", "paperwork delays"],
    "education": ["enquiry response delays", "manual enrollment follow-up", "scheduling classes"],
    "hospitality": ["manual booking confirmations", "review follow-up", "shift scheduling"],
    "legal": ["slow client intake", "manual document assembly", "deadline tracking"],
}


def analyze_business(text: str, session) -> dict:
    t = (text or "").lower()
    first = next((l.strip() for l in (text or "").splitlines() if l.strip()), "Unknown business")

    ind_hits = {}
    for n, keys in INDUSTRY_SIGNALS.items():
        hits = sum(1 for k in keys if k in t)
        if hits:
            ind_hits[n] = hits
    industry = max(ind_hits, key=ind_hits.get) if ind_hits else ""

    pains = PAIN_BY_INDUSTRY.get(industry, ["repetitive manual admin work", "slow response times"])

    score = 20
    if industry:
        score += min(30, ind_hits.get(industry, 0) * 10)
    auto_words = ["manual", "paper", "spreadsheet", "excel", "email", "follow", "booking", "data entry", "process"]
    score += min(30, sum(1 for w in auto_words if w in t) * 6)
    size_words = ["team", "employees", "staff", "clients", "customers", "locations"]
    score += min(20, sum(1 for w in size_words if w in t) * 5)
    score = min(100, score)

    best = match_products(text, session).get("best_match")

    if best and best["score"] >= 70 and score >= 60:
        action = "SELL"
    elif score >= 40:
        action = "REVIEW"
    else:
        action = "SKIP"

    return {
        "company": first[:80],
        "industry": industry or "general",
        "pains": pains,
        "opportunities": [f"Automate {p}" for p in pains[:3]],
        "fit_score": score,
        "best_product": best,
        "action": action,
    }
