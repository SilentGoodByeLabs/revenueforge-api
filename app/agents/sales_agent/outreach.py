from datetime import datetime, timezone

from app.core import audit
from app.core.config import get_profile_config
from app.core.db import SessionLocal
from app.core.models import Company, OutreachMessage, Product, Prospect


def _build_prompt(prospect, product, profile, platform: str):
    tone_prefix = {
        "email": "Professional email:",
        "linkedin": "Casual LinkedIn DM, 4-5 sentences max, no 'I hope this finds you well', conversational:",
        "reddit": "Helpful Reddit DM, no sales pitch upfront, offer value first, mention their post/comment context:",
        "twitter": "Short Twitter DM, 2-3 sentences, punchy:",
        "whatsapp": "Short WhatsApp message, friendly but direct:",
    }
    tone = tone_prefix.get(platform, tone_prefix['email'])
    
    return f"""You are a professional business development specialist writing outreach.

CRITICAL COMPLIANCE RULES:
1. NEVER invent fake results, case studies, or client names.
2. Be honest about capabilities. Focus on the specific problem you can solve.
3. Keep it concise. No generic spam. Reference the actual business.

PROSPECT BUSINESS:
Name: {prospect.name or 'Unknown'}
Industry: {prospect.industry or 'general'}
Notes: {prospect.notes or 'No additional context'}

MY PRODUCT/SERVICE TO PITCH:
Name: {product.name}
Problem it solves: {product.problem_solved or 'Automation and efficiency'}
Price: {product.price or 'Custom quote'}
Sales angle: {product.sales_arguments or 'Saves time and reduces errors'}

MY PROFILE:
Name: {profile.get('name', 'Your Name')}
Position: {profile.get('position', 'Automation Specialist')}

PLATFORM: {platform}

TONE REQUIREMENTS:
{tone}

Write a {platform} message with:
1. Relevant opening (reference their business/problem)
2. Specific value proposition (what you can solve for them)
3. Clear next step (call, reply, or link to portfolio)

Keep it under 150 words for LinkedIn/Reddit/Twitter, under 200 for email/WhatsApp.
"""


def draft_for_prospect(prospect_id: int, platform: str = 'email'):
    session = SessionLocal()
    try:
        prospect = session.get(Prospect, prospect_id)
        if not prospect:
            return {"ok": False, "message": "Prospect not found."}
        
        product = None
        if prospect.product_interest:
            for p in session.query(Product).all():
                if prospect.product_interest.lower() in p.name.lower():
                    product = p
                    break
        
        if not product:
            product = session.query(Product).filter_by(status="active").first()
        
        if not product:
            return {"ok": False, "message": "No products in catalog. Add one first."}
        
        profile = get_profile_config()
        
        try:
            from app.ai.factory import get_ai_provider
            provider = get_ai_provider()
            prompt = _build_prompt(prospect, product, profile, platform)
            ai_response = provider.generate(prompt)
            
            if ai_response.startswith("[MOCK AI]") or ai_response.startswith("[AI ERROR]"):
                body = _fallback_outreach(prospect, product, profile, platform)
            else:
                from app.ai.voice import contains_ai_speak
                if contains_ai_speak(ai_response):
                    body = _fallback_outreach(prospect, product, profile, platform)
                else:
                    body = ai_response.strip()
        except Exception:
            body = _fallback_outreach(prospect, product, profile, platform)
        
        msg = OutreachMessage(
            prospect_id=prospect_id,
            subject=f"Quick question about {prospect.name}",
            body=body,
            status="draft",
            fit_score=prospect.fit_score or 0,
        )
        session.add(msg)
        session.commit()
        audit.log("outreach_draft", "sales_agent", f"prospect#{prospect_id}", result="drafted")
        return {"ok": True, "message": "Draft created."}
    finally:
        session.close()


def _fallback_outreach(prospect, product, profile, platform: str):
    name = prospect.name or "your business"
    problem = product.problem_solved or "manual processes"
    angle = product.sales_arguments or "saves time and reduces errors"
    sender = profile.get("name", "Your Name")
    
    if platform == "linkedin":
        return f"""Hi,

I saw {name} and noticed you're likely dealing with {problem}. We've built a solution that {angle}.

Would you be open to a 10-minute call to see if it could help? No pressure either way.

Best,
{sender}"""
    
    elif platform == "reddit":
        return f"""Hey, saw your post about {problem}. I've built an automation that handles exactly that — {angle}.

Happy to share how it works if you're curious. No sales pitch, just showing what's possible.

Cheers,
{sender}"""
    
    elif platform == "twitter":
        return f"""Hey — noticed {name} deals with {problem}. We built something that {angle}. Worth a quick chat?"""
    
    elif platform == "whatsapp":
        return f"""Hi, this is {sender}. I help businesses like {name} solve {problem}. We have a solution that {angle}. Would you be open to a quick call?"""
    
    else:  # email
        return f"""Subject: Quick question about {name}

Hi,

I came across {name} and noticed you're likely dealing with {problem}.

We've built a solution that {angle}. I'd love to show you how it works and see if it could help.

Would you be open to a 10-minute call this week? No pressure either way.

Best regards,
{sender}
{profile.get('position', 'Automation Specialist')}
{profile.get('portfolio_url', '')}"""


def today_outreach_count():
    session = SessionLocal()
    try:
        today = datetime.now(timezone.utc).date()
        count = session.query(OutreachMessage).filter(
            OutreachMessage.created_at >= today
        ).count()
        return count
    finally:
        session.close()
