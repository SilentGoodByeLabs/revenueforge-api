from typing import Any, Dict, Optional, List
from app.core.config import get_profile_config
from app.ai.factory import get_ai_provider
from app.ai.voice import contains_ai_speak, HUMAN_VOICE_RULES


def _build_ai_prompt(job, profile: Dict, matched_skills: List[str], product_info: str = "") -> str:
    skills_str = ", ".join(matched_skills) if matched_skills else "Python automation, API integration, workflow automation"
    desc = (job.description or "")[:2000]
    
    return f"""You are a professional AI Automation Engineer writing a freelance proposal.

CRITICAL COMPLIANCE RULES:
1. NEVER invent fake experience, portfolio pieces, or case studies.
2. NEVER make unrealistic financial claims or guarantees.
3. Be honest. If exact experience is missing, focus on adjacent technical capability and a concrete implementation plan.
4. Keep it under 300 words. No generic spam. Reference the actual problem.

CLIENT JOB TITLE: {job.title}
CLIENT JOB DESCRIPTION:
{desc}

MY ACTUAL SKILLS: {skills_str}
MY NAME: {profile.get('name', 'Your Name')}
{product_info}

Write a proposal with exactly these sections:
1. Relevant opening
2. Understanding of problem
3. Proposed solution
4. Relevant technical capability
5. Specific implementation approach
6. Honest positioning (no fake experience)
7. One intelligent technical question
8. Clear next step

MANDATORY STYLE (human voice, not AI voice):
{HUMAN_VOICE_RULES}
"""


def _fallback_static_proposal(job, profile: Dict, matched_skills: List[str], product_info: str = "") -> str:
    name = profile.get("name", "Your Name")
    position = profile.get("position", "AI Automation Engineer")

    if matched_skills:
        skills = ", ".join(matched_skills[:6])
    else:
        skills = "Python automation, API integration, and workflow automation"

    problem = (job.description or job.title or "your project").strip()[:300]
    pitch = ("\\nI have a specific pre-built solution for this: " + product_info.split("Sales Angle:")[-1].strip() + "\\n") if "Sales Angle:" in product_info else ""

    portfolio_url = profile.get("portfolio_url", "")
    github_url = profile.get("github_url", "")

    if portfolio_url:
        proof = f"6. Relevant portfolio: {portfolio_url}. I can point to the closest relevant implementation during review."
    elif github_url:
        proof = f"6. Relevant code/portfolio: {github_url}. I can point to the closest relevant implementation during review."
    else:
        proof = "6. Relevant proof: I can share relevant code samples and a short implementation plan. I will not claim a finished case study I do not have."

    honest = (
        "If this requires an exact prior implementation I have not publicly documented, "
        "I will say so and instead provide a concrete plan, relevant adjacent work, "
        "and a small paid discovery step if useful."
    )

    return f"""Hello,

1. Relevant opening
I saw your need for: {job.title or "an automation project"}. I am responding because this matches {position} work.

2. Understanding of problem
{problem}.
{pitch}

3. Proposed solution
I would build a controlled automation workflow that covers the core job: input capture, processing/integration, output, logging, and handoff/approval where needed.

4. Relevant technical capability
Relevant skills: {skills}.

5. Specific implementation approach
- Confirm source systems, fields, triggers, and success criteria.
- Build the smallest reliable version first.
- Add error handling, logging, and human approval points.
- Test with real samples and document usage.

{proof}

7. Honest positioning
{honest}

8. One intelligent question
What is the main system that must be treated as the source of truth for this workflow?

Next step
If this direction is useful, I can prepare a short implementation plan with milestones and questions before any commitment.

Best regards,
{name}
"""


def generate_proposal(job, analysis: Optional[Dict[str, Any]] = None) -> str:
    profile = get_profile_config()
    matched_skills = (analysis or {}).get("matched_skills", [])
    
    # Fetch matched product from catalog
    product_info = ""
    if getattr(job, 'matched_product_id', None):
        from app.core.db import SessionLocal
        from app.core.models import Product
        s = SessionLocal()
        try:
            prod = s.get(Product, job.matched_product_id)
            if prod:
                product_info = f"""
RECOMMENDED PRODUCT TO PITCH (FROM CATALOG):
Name: {prod.name}
Price: {prod.price or 'Custom'}
Sales Angle: {getattr(job, 'sales_angle', '') or prod.sales_arguments or prod.problem_solved}
"""
        finally:
            s.close()
    
    try:
        provider = get_ai_provider()
        prompt = _build_ai_prompt(job, profile, matched_skills, product_info)
        ai_response = provider.generate(prompt)
        
        # FAIL-SAFE: If AI is in Mock mode or fails, fall back to static template
        if ai_response.startswith("[MOCK AI]") or ai_response.startswith("[AI ERROR]"):
            return _fallback_static_proposal(job, profile, matched_skills, product_info)
        
        if contains_ai_speak(ai_response):
            return _fallback_static_proposal(job, profile, matched_skills, product_info)
        
        return ai_response.strip()
        
    except Exception:
        # FAIL-SAFE: Never break the pipeline. Always produce a draft for human approval.
        return _fallback_static_proposal(job, profile, matched_skills, product_info)
