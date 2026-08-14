import re
from typing import Any, Dict, List, Tuple

from app.core.config import get_categories_config


def normalize(value: str) -> str:
    return (value or "").lower()


def extract_numbers(text: str) -> List[float]:
    if not text:
        return []

    cleaned = text.replace(",", "")
    matches = re.findall(r"\d+(?:\.\d+)?", cleaned)
    numbers = []

    for match in matches:
        try:
            numbers.append(float(match))
        except ValueError:
            continue

    return numbers


def budget_score(budget_text: str) -> Tuple[float, str]:
    text = normalize(budget_text or "")
    numbers = extract_numbers(text)

    if not numbers:
        return 40.0, "No clear budget; treat as medium uncertainty."

    value = max(numbers)

    if "hourly" in text or "/hr" in text or "per hour" in text:
        if value >= 100:
            return 100.0, "High hourly budget."
        if value >= 50:
            return 85.0, "Strong hourly budget."
        if value >= 30:
            return 70.0, "Moderate hourly budget."
        if value >= 20:
            return 55.0, "Low-mid hourly budget."
        if value >= 10:
            return 35.0, "Low hourly budget."
        return 15.0, "Very low hourly budget."

    if value >= 5000:
        return 100.0, "High fixed budget."
    if value >= 2000:
        return 85.0, "Strong fixed budget."
    if value >= 1000:
        return 70.0, "Moderate fixed budget."
    if value >= 500:
        return 55.0, "Small fixed budget."
    if value >= 100:
        return 35.0, "Very small fixed budget."
    return 15.0, "Micro budget."


def technical_fit(full_text: str, config: Dict[str, Any]) -> Tuple[float, List[str]]:
    skills = config.get("skills", [])
    text = normalize(full_text)
    matched = []

    for skill in skills:
        term = normalize(skill)
        if term and term in text:
            matched.append(skill)

    if not matched:
        return 15.0, []

    score = min(100.0, 20.0 + len(matched) * 15.0)
    return score, matched


def clarity_score(description: str) -> Tuple[float, str]:
    desc = description or ""
    length = len(desc.strip())

    if length >= 1200:
        score = 88.0
    elif length >= 800:
        score = 78.0
    elif length >= 500:
        score = 68.0
    elif length >= 250:
        score = 55.0
    elif length >= 100:
        score = 40.0
    else:
        score = 20.0

    text = normalize(desc)

    for keyword in [
        "deliverable",
        "milestone",
        "requirements",
        "scope",
        "timeline",
        "acceptance criteria",
        "budget",
        "deadline",
    ]:
        if keyword in text:
            score += 2.0

    score = min(100.0, score)

    if score >= 65:
        quality = "good"
    else:
        quality = "moderate/low"

    reason = f"Description length {length} chars; specificity {quality}."
    return score, reason


def client_quality_score(platform: str, description: str) -> Tuple[float, str]:
    score = 45.0
    text = normalize((platform or "") + " " + (description or ""))

    trusted_platforms = [
        "upwork",
        "fiverr",
        "linkedin",
        "company website",
        "referral",
        "wellfound",
        "remoteok",
        "weworkremotely",
    ]

    if normalize(platform or "") in trusted_platforms:
        score += 10.0

    positives = [
        "verified",
        "payment verified",
        "top rated",
        "5.0",
        "5 star",
        "positive feedback",
        "repeat client",
        "hired",
        "reviews",
    ]

    hits = 0

    for keyword in positives:
        if keyword in text:
            score += 8.0
            hits += 1

    reason = f"Platform trust baseline plus {hits} positive client signals."
    return min(100.0, score), reason


def competition_score(full_text: str) -> Tuple[float, str]:
    text = normalize(full_text)

    less_than = re.search(r"less than (\d+)", text)
    if less_than:
        count = int(less_than.group(1))
        if count <= 5:
            return 90.0, f"Less than {count} applicants/proposals reported."

    explicit = re.search(r"(\d+)\s*(?:proposals|applicants|bids)", text)
    if explicit:
        count = int(explicit.group(1))
        if count < 5:
            return 90.0, f"Low reported competition: {count}."
        if count < 10:
            return 75.0, f"Moderate-low competition: {count}."
        if count < 20:
            return 60.0, f"Moderate-high competition: {count}."
        return 30.0, f"High reported competition: {count}."

    return 50.0, "Competition unknown; assume moderate."


def urgency_score(full_text: str) -> Tuple[float, str]:
    text = normalize(full_text)

    urgent_terms = [
        "asap",
        "urgent",
        "immediately",
        "start today",
        "today",
    ]

    long_terms = [
        "long-term",
        "long term",
        "months",
    ]

    if any(term in text for term in urgent_terms):
        return 75.0, "Urgent start can help conversion but requires fast delivery."

    if any(term in text for term in long_terms):
        return 45.0, "Not urgent; long horizon."

    return 50.0, "Normal urgency."


def keyword_score(full_text: str, keywords: List[str], label: str) -> Tuple[float, str]:
    text = normalize(full_text)
    hits = []

    for keyword in keywords:
        term = normalize(keyword)
        if term and term in text:
            hits.append(keyword)

    if not hits:
        return 20.0, f"No clear {label.lower()} signals."

    score = min(100.0, 40.0 + len(hits) * 20.0)
    reason = f"{label} signals: " + ", ".join(hits[:3])
    return score, reason


def scam_risk_score(full_text: str, config: Dict[str, Any]) -> Tuple[float, List[str]]:
    text = normalize(full_text)
    flags = []

    for flag in config.get("red_flags", []):
        term = normalize(flag)
        if term and term in text:
            flags.append(flag)

    if not flags:
        return 0.0, []

    score = min(100.0, len(flags) * 30.0)
    return score, flags


def analyze_job(job) -> Dict[str, Any]:
    config = get_categories_config()

    full_text = " ".join(
        filter(
            None,
            [
                job.title,
                job.description,
                job.required_skills,
                job.budget_text,
            ],
        )
    )

    technical, matched_skills = technical_fit(full_text, config)
    budget, budget_reason = budget_score(job.budget_text or "")
    clarity, clarity_reason = clarity_score(job.description or "")
    client_quality, client_reason = client_quality_score(
        job.platform or "",
        job.description or "",
    )
    competition, competition_reason = competition_score(full_text)
    urgency, urgency_reason = urgency_score(full_text)

    long_term, long_reason = keyword_score(
        full_text,
        [
            "long-term",
            "long term",
            "ongoing",
            "retainer",
            "extension",
        ],
        "Long-term",
    )

    recurring, recurring_reason = keyword_score(
        full_text,
        [
            "monthly",
            "weekly",
            "recurring",
            "maintenance",
            "support",
            "subscription",
        ],
        "Recurring",
    )

    scam_risk, scam_flags = scam_risk_score(full_text, config)

    weighted = (
        technical * 25.0
        + budget * 15.0
        + clarity * 15.0
        + client_quality * 10.0
        + competition * 10.0
        + urgency * 5.0
        + long_term * 10.0
        + recurring * 10.0
    ) / 100.0

    opportunity = max(0.0, min(100.0, weighted - scam_risk * 0.6))

    if scam_risk >= 70.0 or opportunity < 35.0:
        recommendation = "SKIP"
    elif opportunity >= 75.0 and scam_risk < 40.0:
        recommendation = "APPLY"
    elif opportunity >= 55.0 and scam_risk < 60.0:
        recommendation = "REVIEW"
    else:
        recommendation = "SKIP"

    components = [
        ("Technical fit", technical),
        ("Budget", budget),
        ("Clarity", clarity),
        ("Client quality", client_quality),
        ("Competition", competition),
        ("Urgency", urgency),
        ("Long-term potential", long_term),
        ("Recurring potential", recurring),
    ]

    strengths = sorted(components, key=lambda item: item[1], reverse=True)[:3]

    concerns = []

    for name, score in components:
        if score < 45.0:
            concerns.append(f"{name} {score:.0f}")

    if scam_flags:
        concerns.append("Scam flags: " + ", ".join(scam_flags[:5]))

    reason = (
        f"Score {opportunity:.1f}/100. "
        f"Strengths: " + "; ".join([f"{name} {score:.0f}" for name, score in strengths])
    )

    if concerns:
        reason += ". Concerns: " + "; ".join(concerns)

    reason += ". " + " ".join([
        budget_reason,
        clarity_reason,
        client_reason,
        competition_reason,
        urgency_reason,
        long_reason,
        recurring_reason,
    ])

    if recommendation == "APPLY":
        strategy = (
            "Prepare a specific proposal focused on the client's workflow, "
            "include one implementation question, and submit only through the "
            "official permitted channel after approval."
        )
    elif recommendation == "REVIEW":
        strategy = (
            "Manually verify budget, client, and scope before applying. "
            "Ask one clarifying question if platform permits."
        )
    else:
        strategy = (
            "Do not spend time unless you manually verify it is safe and valuable."
        )

    return {
        "technical_fit": technical,
        "client_quality": client_quality,
        "budget_score": budget,
        "clarity_score": clarity,
        "competition_score": competition,
        "urgency_score": urgency,
        "long_term_score": long_term,
        "recurring_score": recurring,
        "scam_risk": scam_risk,
        "opportunity_score": opportunity,
        "recommendation": recommendation,
        "reason": reason,
        "proposal_strategy": strategy,
        "matched_skills": matched_skills,
        "scam_flags": scam_flags,
    }


def apply_analysis(job, analysis):
    job.technical_fit = analysis["technical_fit"]
    job.client_quality = analysis["client_quality"]
    job.budget_score = analysis["budget_score"]
    job.clarity_score = analysis["clarity_score"]
    job.competition_score = analysis["competition_score"]
    job.urgency_score = analysis["urgency_score"]
    job.long_term_score = analysis["long_term_score"]
    job.recurring_score = analysis["recurring_score"]
    job.scam_risk = analysis["scam_risk"]
    job.opportunity_score = analysis["opportunity_score"]
    job.recommendation = analysis["recommendation"]
    job.reason = analysis["reason"]
    job.proposal_strategy = analysis["proposal_strategy"]
