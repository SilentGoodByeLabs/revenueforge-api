import re

TECH_DICT = {
    "python": ["python"],
    "ocr": ["ocr", "tesseract", "optical character"],
    "excel": ["excel", "xlsx", "spreadsheet", "google sheets"],
    "pdf": ["pdf"],
    "invoice": ["invoice"],
    "api": ["api", "rest", "endpoint", "webhook"],
    "web scraping": ["scrap", "beautifulsoup", "selenium", "crawler"],
    "automation": ["automat", "workflow", "n8n", "make.com", "zapier"],
    "chatbot": ["chatbot", "assistant bot"],
    "crm": ["crm", "hubspot", "salesforce", "pipedrive"],
    "ai": [" ai", "gpt", "openai", "llm", "machine learning"],
    "sql": ["sql", "database", "sqlite", "postgres", "mysql"],
    "email": ["email", "smtp", "imap", "gmail"],
    "telegram": ["telegram"],
    "whatsapp": ["whatsapp"],
}

INDUSTRY_DICT = {
    "accounting": ["invoice", "accounting", "bookkeeping", "receipt"],
    "ecommerce": ["shopify", "ecommerce", "e-commerce", "store", "product listing"],
    "real estate": ["real estate", "property", "listing"],
    "healthcare": ["clinic", "patient", "medical", "appointment"],
    "marketing": ["marketing", "agency", "leads", "campaign"],
    "logistics": ["shipping", "logistics", "delivery", "tracking"],
}

PRICE_PATTERNS = [
    r"(?:from|starting at|starts at|for only)\s*\$?\s*(\d+(?:\.\d+)?)",
    r"\$\s*(\d+(?:\.\d+)?)",
    r"(\d+(?:\.\d+)?)\s*usd",
]


def smart_extract(text: str) -> dict:
    t = (text or "").lower()
    r = {}

    first = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    r["name"] = first[:80] or ""

    r["price"] = ""
    for pat in PRICE_PATTERNS:
        m = re.search(pat, t)
        if m:
            r["price"] = f"From ${float(m.group(1)):,.0f}"
            break

    techs = [n for n, keys in TECH_DICT.items() if any(k in t for k in keys)]
    industries = [n for n, keys in INDUSTRY_DICT.items() if any(k in t for k in keys)]

    r["technologies"] = ", ".join(techs)
    r["industry"] = ", ".join(industries)

    keywords = list(techs) + list(industries)
    r["keywords"] = ", ".join(keywords)

    problems = []
    if "ocr" in techs or "pdf" in techs:
        problems.append("manual data entry from PDF documents")
    if "excel" in techs:
        problems.append("slow spreadsheet work")
    if "web scraping" in techs:
        problems.append("manual data collection from websites")
    if "crm" in techs:
        problems.append("disorganized leads and follow-ups")
    if "chatbot" in techs:
        problems.append("slow customer responses")
    if "email" in techs:
        problems.append("repetitive email handling")
    if not problems:
        problems.append("repetitive manual work")
    r["problem_solved"] = "; ".join(problems)

    targets = []
    if "accounting" in industries:
        targets.append("accounting firms and finance teams")
    if "ecommerce" in industries:
        targets.append("e-commerce stores")
    if "real estate" in industries:
        targets.append("real estate agencies")
    if "healthcare" in industries:
        targets.append("clinics and practices")
    if not targets:
        targets.append("small businesses and agencies")
    r["target_customer"] = ", ".join(targets)

    deliver = [l.strip() for l in (text or "").splitlines()
               if l.strip().lower().startswith(("you will get", "deliver", "includes", "what you get"))]
    r["deliverables"] = "\n".join(deliver) or "Working automation + source code + documentation"

    r["benefits"] = "Saves hours of manual work every week\nReduces human errors\nOne-time cost, no recurring fees"
    r["features"] = "\n".join(f"- {x} pipeline" for x in techs) or "- Custom automation pipeline"
    r["description"] = (text or "")[:500]
    r["use_cases"] = r["problem_solved"]
    r["sales_arguments"] = f"Purpose-built for {r['target_customer']}. Removes {r['problem_solved']} with a reliable, documented automation."
    r["ideal_customer_profile"] = f"Businesses dealing with {r['problem_solved']} who want it handled reliably without hiring full-time staff."
    r["requirements"] = "Access to sample documents/data and a short onboarding call."
    r["objections"] = ("'Is my data safe?' -> Everything runs on your own systems; no data leaves your control.\n"
                       "'Too expensive?' -> It pays for itself in saved hours within the first month.")
    r["objection_responses"] = ""
    return r
