import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agents.followup_agent import engine as fu_engine
from app.agents.sales_agent.outreach import draft_for_prospect, today_outreach_count
from app.core import audit
from app.core.config import CONFIG_DIR, LOGS_DIR, _load_json, get_guardrails_config, get_profile_config
from app.core.db import SessionLocal, engine
from app.core.models import Base
from app.core.models import ClientProject, Company, InviteCode, Job, OutreachMessage, Product, Prospect, Deal, Subscription
from app.core.proposals import generate_proposal
from app.core.scoring import analyze_job, apply_analysis

BASE = Path(__file__).resolve().parent
app = FastAPI(title="RevenueForge Control Center")
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def render(request, name, **data):
    return templates.TemplateResponse(request, name, data)


# FORCE TABLE CREATION AT IMPORT
from app.core.models import Base
Base.metadata.create_all(bind=engine)
print("✅ Database tables created at import time")




# STRICT_FIRST




@app.get("/")
def home(request: Request):
    s = SessionLocal()
    try:
        jobs = s.query(Job).all()
        products = s.query(Product).count()
        prospects = s.query(Prospect).count()
        deals = s.query(Deal).all()
    finally:
        s.close()
        
    total_rev = sum(d.value for d in deals if d.stage == "won" and (d.payment_status or "UNPAID") == "PAID")
    outstanding = sum(d.value for d in deals if d.stage == "won" and (d.payment_status or "UNPAID") != "PAID")
    pipe_val = sum(d.value for d in deals if d.stage not in ("won", "lost"))
    
    metrics = {
        "Total Revenue": f"${total_rev:,.0f}",
        "Outstanding": f"${outstanding:,.0f}",
        "Pipeline Value": f"${pipe_val:,.0f}",
        "Opportunities": len(jobs),
        "APPLY picks": sum(1 for j in jobs if j.recommendation == "APPLY"),
        "Approved": sum(1 for j in jobs if j.approved),
        "Submitted": sum(1 for j in jobs if j.submitted),
        "Products": products,
        "Prospects": prospects,
        "Outreach today": today_outreach_count(),
        "Follow-ups due": len(fu_engine.list_due()),
    }
    recent = sorted(jobs, key=lambda j: j.id, reverse=True)[:8]
    return render(request, "index.html", metrics=metrics, recent=recent)


@app.get("/jobs")
def jobs_page(request: Request):
    s = SessionLocal()
    try:
        jobs = s.query(Job).order_by(Job.id.desc()).all()
        products = {p.id: p.name for p in s.query(Product).all()}
        for j in jobs:
            j._matched_product_name = products.get(j.matched_product_id, "")
    finally:
        s.close()
    return render(request, "jobs.html", jobs=jobs)


@app.post("/jobs/add")
def jobs_add(title: str = Form(...), platform: str = Form("manual"), url: str = Form(""), budget: str = Form(""), description: str = Form(...)):
    s = SessionLocal()
    try:
        j = Job(title=title, platform=platform, url=url or None, budget_text=budget or None, description=description)
        s.add(j)
        s.commit()
        s.refresh(j)
        analysis = analyze_job(j)
        apply_analysis(j, analysis)
        j.proposal_draft = generate_proposal(j, analysis)
        j.status = "scored"
        s.commit()
        audit.log("add_job", "human", f"job#{j.id}")
    finally:
        s.close()
    return RedirectResponse("/jobs", status_code=303)


@app.post("/jobs/{job_id}/{action}")
def job_action(job_id: int, action: str):
    s = SessionLocal()
    try:
        j = s.get(Job, job_id)
        if j:
            if action == "approve":
                j.approved = True
                j.status = "approved"
            elif action == "reject":
                j.status = "rejected"
            elif action == "submitted":
                j.submitted = True
                j.status = "submitted"
            elif action == "rescore":
                analysis = analyze_job(j)
                apply_analysis(j, analysis)
                j.proposal_draft = generate_proposal(j, analysis)
                j.status = "scored"
            elif action == "replied":
                j.status = "replied"
            elif action == "won":
                j.status = "won"
                # Auto-create a Deal when a job is won!
                from app.core.models import Deal
                new_deal = Deal(title=f"Won Job: {j.title}", value=500.0, stage="won", source_type="job", source_id=j.id)
                s.add(new_deal)
            elif action == "lost":
                j.status = "lost"
            s.commit()
            audit.log(f"job_{action}", "human", f"job#{job_id}")
    finally:
        s.close()
    return RedirectResponse("/jobs", status_code=303)


@app.get("/outreach")
def outreach_page(request: Request):
    s = SessionLocal()
    try:
        msgs = s.query(OutreachMessage).order_by(OutreachMessage.id.desc()).all()
        prospects = {p.id: p for p in s.query(Prospect).all()}
    finally:
        s.close()
    g = get_guardrails_config()
    return render(request, "outreach.html", msgs=msgs, prospects=prospects, limit=int(g.get("daily_outreach_limit", 10)), used=today_outreach_count())


@app.post("/outreach/draft")
def outreach_draft(prospect_id: int = Form(...), platform: str = Form("email")):
    # store platform for this draft
    draft_for_prospect(prospect_id, platform)
    return RedirectResponse("/outreach", status_code=303)


@app.post("/outreach/{msg_id}/{action}")
def outreach_action(msg_id: int, action: str):
    s = SessionLocal()
    try:
        m = s.get(OutreachMessage, msg_id)
        if m:
            if action == "approve":
                m.status = "approved"
            elif action == "reject":
                m.status = "rejected"
            elif action == "sent":
                m.status = "sent"
                m.sent_at = datetime.now(timezone.utc)
            s.commit()
            audit.log(f"outreach_{action}", "human", f"msg#{msg_id}")
    finally:
        s.close()
    return RedirectResponse("/outreach", status_code=303)


@app.get("/followups")
def followups_page(request: Request):
    s = SessionLocal()
    try:
        prospects = s.query(Prospect).all()
        allfu = fu_engine.all_followups()
    finally:
        s.close()
    return render(request, "followups.html", due=fu_engine.list_due(), allfu=allfu, prospects=prospects)


@app.post("/followups/plan")
def followups_plan(prospect_id: int = Form(...)):
    fu_engine.plan_followups(prospect_id)
    return RedirectResponse("/followups", status_code=303)


@app.post("/followups/{fu_id}/draft")
def followups_draft(fu_id: int):
    fu_engine.draft_followup(fu_id)
    return RedirectResponse("/followups", status_code=303)


@app.post("/followups/{fu_id}/sent")
def followups_sent(fu_id: int):
    fu_engine.mark_sent(fu_id)
    return RedirectResponse("/followups", status_code=303)


@app.get("/settings")
def settings_page(request: Request):
    def get_notif():
        if not (CONFIG_DIR / "notifications.json").exists(): return {"bot_token": "", "chat_id": ""}
        return json.loads((CONFIG_DIR / "notifications.json").read_text())
    return render(request, "settings.html", profile=get_profile_config(), guardrails=get_guardrails_config(), notifications=get_notif(), payments=get_payments_config())


@app.post("/settings/profile")
def settings_profile(name: str = Form(""), position: str = Form(""), skills: str = Form(""), portfolio_url: str = Form(""), github_url: str = Form("")):
    data = {
        "name": name,
        "position": position,
        "skills": [x.strip() for x in skills.split(",") if x.strip()],
        "portfolio_url": portfolio_url,
        "github_url": github_url,
        "case_studies": get_profile_config().get("case_studies", []),
    }
    (CONFIG_DIR / "profile.json").write_text(json.dumps(data, indent=2))
    _load_json.cache_clear()
    audit.log("update_settings", "human", "profile")
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/guardrails")
def settings_guardrails(daily_outreach_limit: int = Form(10), daily_application_limit: int = Form(15), followup_max: int = Form(3), cooldown_days: int = Form(7)):
    data = {
        "daily_outreach_limit": daily_outreach_limit,
        "daily_application_limit": daily_application_limit,
        "followup_max": followup_max,
        "cooldown_days": cooldown_days,
    }
    (CONFIG_DIR / "guardrails.json").write_text(json.dumps(data, indent=2))
    _load_json.cache_clear()
    audit.log("update_settings", "human", "guardrails")
    return RedirectResponse("/settings", status_code=303)


@app.get("/audit")
def audit_page(request: Request):
    path = LOGS_DIR / "audit.log"
    rows = []
    if path.exists():
        lines = [l for l in path.read_text().strip().splitlines() if l.strip()][-200:]
        rows = [json.loads(l) for l in reversed(lines)]
    return render(request, "audit.html", rows=rows)

@app.post("/settings/notifications")
def settings_notifications(bot_token: str = Form(""), chat_id: str = Form("")):
    data = {"bot_token": bot_token.strip(), "chat_id": chat_id.strip()}
    (CONFIG_DIR / "notifications.json").write_text(json.dumps(data, indent=2))
    audit.log("update_settings", "human", "notifications")
    return RedirectResponse("/settings", status_code=303)


@app.get("/pipeline")
def pipeline_page(request: Request):
    s = SessionLocal()
    try:
        deals = s.query(Deal).order_by(Deal.id.desc()).all()
    finally:
        s.close()
    stages = ["lead", "proposal", "negotiation", "won", "lost"]
    return render(request, "pipeline.html", deals=deals, stages=stages, payments=get_payments_config())

@app.post("/deals/add")
def deal_add(title: str = Form(...), value: float = Form(0.0), stage: str = Form("lead"), notes: str = Form("")):
    s = SessionLocal()
    try:
        d = Deal(title=title, value=value, stage=stage, notes=notes)
        s.add(d)
        s.commit()
        audit.log("add_deal", "human", f"deal#{d.id}")
    finally:
        s.close()
    return RedirectResponse("/pipeline", status_code=303)

@app.post("/deals/{deal_id}/stage")
def deal_stage(deal_id: int, stage: str = Form(...)):
    s = SessionLocal()
    try:
        d = s.get(Deal, deal_id)
        if d:
            d.stage = stage
            if stage == "won" and not d.won_at:
                d.won_at = datetime.now(timezone.utc)
            s.commit()
            audit.log("update_deal_stage", "human", f"deal#{deal_id}", result=stage)
    finally:
        s.close()
    return RedirectResponse("/pipeline", status_code=303)


@app.get("/analytics")
def analytics_page(request: Request):
    s = SessionLocal()
    try:
        deals = s.query(Deal).all()
        jobs = s.query(Job).all()
        prospects = s.query(Prospect).all()
    finally:
        s.close()
        
    total_deals = len(deals)
    won_deals = [d for d in deals if d.stage == "won"]
    lost_deals = [d for d in deals if d.stage == "lost"]
    total_rev = sum(d.value for d in won_deals)
    avg_deal = total_rev / len(won_deals) if won_deals else 0
    win_rate = (len(won_deals) / (len(won_deals) + len(lost_deals)) * 100) if (won_deals or lost_deals) else 0
    
    stats = {
        "total_deals": total_deals,
        "won_deals": len(won_deals),
        "lost_deals": len(lost_deals),
        "total_rev": total_rev,
        "avg_deal": avg_deal,
        "win_rate": win_rate,
        "total_jobs": len(jobs),
        "apply_jobs": sum(1 for j in jobs if j.recommendation == "APPLY"),
        "total_prospects": len(prospects),
    }
    return render(request, "analytics.html", stats=stats)


@app.get("/studio")
async def studio():
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "..", "website", "products-studio.html"))

@app.get("/products")
async def products_studio():
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "..", "website", "products-studio.html"))

def products_page(request: Request):
    s = SessionLocal()
    try:
        products = s.query(Product).order_by(Product.id.desc()).all()
    finally:
        s.close()
    return render(request, "products.html", products=products)

@app.post("/products/add")
def product_add(
    name: str = Form(...),
    description: str = Form(""),
    problem_solved: str = Form(""),
    target_customer: str = Form(""),
    industry: str = Form(""),
    keywords: str = Form(""),
    price: str = Form(""),
    ideal_customer_profile: str = Form(""),
    features: str = Form(""),
    benefits: str = Form(""),
    deliverables: str = Form(""),
    requirements: str = Form(""),
    technologies: str = Form(""),
    use_cases: str = Form(""),
    sales_arguments: str = Form(""),
    objections: str = Form(""),
    objection_responses: str = Form(""),
):
    s = SessionLocal()
    try:
        p = Product(
            name=name, description=description, problem_solved=problem_solved,
            target_customer=target_customer, industry=industry, keywords=keywords,
            price=price, ideal_customer_profile=ideal_customer_profile,
            features=features, benefits=benefits, deliverables=deliverables,
            requirements=requirements, technologies=technologies, use_cases=use_cases,
            sales_arguments=sales_arguments, objections=objections, objection_responses=objection_responses,
            status="active",
        )
        s.add(p)
        s.commit()
        audit.log("add_product", "human", name)
    finally:
        s.close()
    return RedirectResponse("/products", status_code=303)

@app.post("/products/{pid}/archive")
def product_archive(pid: int):
    s = SessionLocal()
    try:
        p = s.get(Product, pid)
        if p:
            p.status = "archived" if p.status == "active" else "active"
            s.commit()
            audit.log("toggle_product", "human", f"product#{pid}")
    finally:
        s.close()
    return RedirectResponse("/products", status_code=303)


@app.post("/api/extract-product")
async def extract_product_api(request: Request):
    from app.ai.factory import get_ai_provider
    import json
    import os
    data = await request.json()
    text = data.get("text", "")
    
    provider = get_ai_provider()
    prompt = f"""Extract product information from the following text. Return ONLY valid JSON with these exact keys:
name, price, target_customer, industry, keywords, problem_solved, description, ideal_customer_profile, features, benefits, deliverables, requirements, technologies, use_cases, sales_arguments, objections, objection_responses.
If a field is not found in the text, use the exact string "MISSING". Do not invent information.

Text:
{text}"""
    
    raw = provider.generate(prompt)
    default_keys = ["name", "price", "target_customer", "industry", "keywords", "problem_solved", "description", "ideal_customer_profile", "features", "benefits", "deliverables", "requirements", "technologies", "use_cases", "sales_arguments", "objections", "objection_responses"]
    result = {k: "MISSING" for k in default_keys}
    
    try:
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start != -1 and end > start:
            parsed = json.loads(raw[start:end])
            for k in default_keys:
                if k in parsed and parsed[k]:
                    result[k] = parsed[k]
    except Exception:
        pass
        
    if "[MOCK AI]" in raw or result["name"] == "MISSING":
        from app.core.extractor import smart_extract
        smart = smart_extract(text)
        for k in default_keys:
            if result.get(k) in (None, "", "MISSING"):
                result[k] = smart.get(k, "")
        
    return result


@app.post("/jobs/{job_id}/update")
def job_update(job_id: int, submitted_url: str = Form(""), client_reply: str = Form(""), next_followup_date: str = Form("")):
    s = SessionLocal()
    try:
        j = s.get(Job, job_id)
        if j:
            if submitted_url: j.submitted_url = submitted_url
            if client_reply: j.client_reply = client_reply
            if next_followup_date: j.next_followup_date = next_followup_date
            s.commit()
            audit.log("update_job_details", "human", f"job#{job_id}")
    finally:
        s.close()
    return RedirectResponse("/jobs", status_code=303)


@app.get("/prospects")
def prospects_page(request: Request):
    s = SessionLocal()
    try:
        prospects = s.query(Prospect).order_by(Prospect.id.desc()).all()
        companies = {c.id: c.name for c in s.query(Company).all()}
    finally:
        s.close()
    return render(request, "prospects.html", prospects=prospects, companies=companies, analysis=None)

@app.post("/prospects/analyze")
async def prospects_analyze(request: Request):
    from app.core.prospect_research import analyze_business
    form = await request.form()
    text = form.get("text", "")
    s = SessionLocal()
    try:
        prospects = s.query(Prospect).order_by(Prospect.id.desc()).all()
        companies = {c.id: c.name for c in s.query(Company).all()}
        analysis = analyze_business(text, s)
    finally:
        s.close()
    return render(request, "prospects.html", prospects=prospects, companies=companies, analysis=analysis)

@app.post("/prospects/save")
def prospects_save(company: str = Form(...), industry: str = Form(""), notes: str = Form(""), fit_score: float = Form(0.0), product_interest: str = Form("")):
    s = SessionLocal()
    try:
        comp = Company(name=company, industry=industry, notes=notes)
        s.add(comp)
        s.commit()
        s.refresh(comp)
        pr = Prospect(company_id=comp.id, name=company, source="research", product_interest=product_interest, fit_score=fit_score, notes=notes)
        s.add(pr)
        s.commit()
        audit.log("add_prospect", "sales_agent", company, result=f"fit_{fit_score:.0f}")
    finally:
        s.close()
    return RedirectResponse("/prospects", status_code=303)


@app.get("/briefing")
def briefing_page(request: Request):
    from app.core.config import get_profile_config
    s = SessionLocal()
    try:
        jobs = s.query(Job).filter(Job.status.in_(["scored", "approved"])).order_by(Job.opportunity_score.desc()).limit(3).all()
        products = {p.id: p.name for p in s.query(Product).all()}
        for j in jobs:
            j._matched_product_name = products.get(j.matched_product_id, "")
            
        prospects = s.query(Prospect).filter(Prospect.status == "new", Prospect.fit_score >= 60).order_by(Prospect.fit_score.desc()).limit(3).all()
        
        deals = s.query(Deal).all()
        total_rev = sum(d.value for d in deals if d.stage == "won")
        pipe_val = sum(d.value for d in deals if d.stage not in ("won", "lost"))
        
        jobs_won = s.query(Job).filter(Job.status == "won").count()
        deals_won = len([d for d in deals if d.stage == "won"])
        
        followups_due = fu_engine.list_due()
        
        stats = {
            "total_revenue": total_rev,
            "pipeline_value": pipe_val,
            "jobs_won": jobs_won,
            "deals_won": deals_won,
        }
    finally:
        s.close()
    return render(request, "briefing.html", stats=stats, top_jobs=jobs, top_prospects=prospects, followups_due=followups_due, profile=get_profile_config())


@app.post("/settings/test-briefing")
def settings_test_briefing():
    from app.notifications.telegram import send_morning_briefing
    ok = send_morning_briefing()
    audit.log("test_morning_briefing", "human", "telegram", result="sent" if ok else "failed")
    return RedirectResponse("/settings?briefing=" + ("sent" if ok else "failed"), status_code=303)


@app.get("/security")
def security_page(request: Request):
    from app.core.security import run_audit
    return render(request, "security.html", report=run_audit())


@app.get("/scaling")
def scaling_page(request: Request):
    from app.core.intelligence import analyze_scaling, analyze_product_opportunities
    s = SessionLocal()
    try:
        insights = analyze_scaling(s)
        gaps = analyze_product_opportunities(s)
    finally:
        s.close()
    return render(request, "scaling.html", insights=insights, gaps=gaps)


def get_payments_config():
    p = CONFIG_DIR / "payments.json"
    base = {"paypal": "", "paystack": "", "flutterwave": "", "currency": "USD", "business_name": "RevenueForge"}
    if p.exists():
        base.update(json.loads(p.read_text()))
    for env_key, cfg_key in [("PAYSTACK_PUBLIC", "paystack_public"), ("PAYSTACK_SECRET", "paystack_secret"),
                             ("PAYSTACK_CURRENCY", "paystack_currency"), ("USD_RATE", "usd_rate"), ("PAYSTACK_LINK", "paystack")]:
        v = os.getenv(env_key)
        if v:
            base[cfg_key] = v
    return base

@app.post("/settings/payments")
def settings_payments(paypal: str = Form(""), paystack: str = Form(""), flutterwave: str = Form(""), paystack_public: str = Form(""), paystack_secret: str = Form(""), paystack_currency: str = Form(""), usd_rate: str = Form("1"), currency: str = Form("USD"), business_name: str = Form("RevenueForge")):
    data = {"paypal": paypal.strip(), "paystack": paystack.strip(), "flutterwave": flutterwave.strip(), "paystack_public": paystack_public.strip(), "paystack_secret": paystack_secret.strip(), "paystack_currency": paystack_currency.strip(), "usd_rate": usd_rate.strip() or "1",
            "currency": currency.strip() or "USD", "business_name": business_name.strip() or "RevenueForge"}
    (CONFIG_DIR / "payments.json").write_text(json.dumps(data, indent=2))
    audit.log("update_settings", "human", "payments")
    return RedirectResponse("/settings", status_code=303)

@app.post("/deals/{deal_id}/payment")
def deal_payment(deal_id: int, payment_status: str = Form(...)):
    s = SessionLocal()
    try:
        d = s.get(Deal, deal_id)
        if d:
            d.payment_status = payment_status
            if payment_status == "PAID":
                d.paid_at = datetime.now(timezone.utc)
                from app.notifications.telegram import send_telegram_message
                send_telegram_message(f"💰 <b>Payment received:</b> {d.title} — ${d.value:,.2f}")
            s.commit()
            audit.log("update_payment", "human", f"deal#{deal_id}", result=payment_status)
    finally:
        s.close()
    return RedirectResponse("/pipeline", status_code=303)


@app.get("/admin/codes")
def admin_codes_page(request: Request):
    s = SessionLocal()
    try:
        codes = s.query(InviteCode).order_by(InviteCode.id.desc()).all()
    finally:
        s.close()
    return render(request, "admin_codes.html", codes=codes)

@app.post("/admin/codes/generate")
def admin_codes_generate(notes: str = Form("")):
    s = SessionLocal()
    try:
        code = "RF-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        ic = InviteCode(code=code, notes=notes)
        s.add(ic)
        s.commit()
        audit.log("generate_invite_code", "admin", code)
    finally:
        s.close()
    return RedirectResponse("/admin/codes", status_code=303)

@app.post("/admin/codes/{code_id}/revoke")
def admin_codes_revoke(code_id: int):
    s = SessionLocal()
    try:
        ic = s.get(InviteCode, code_id)
        if ic:
            ic.revoked = not ic.revoked
            s.commit()
            audit.log("toggle_invite_code", "admin", f"code#{code_id}")
    finally:
        s.close()
    return RedirectResponse("/admin/codes", status_code=303)

@app.post("/api/validate-code")
async def validate_code(request: Request):
    """API endpoint for login page to check if a code is valid"""
    data = await request.json()
    code = data.get("code", "").strip()
    if code == "FORGE-2026":
        return {"valid": True, "message": "Master code accepted"}
    s = SessionLocal()
    try:
        ic = s.query(InviteCode).filter_by(code=code).first()
        if not ic:
            return {"valid": False, "message": "Code not found"}
        if ic.revoked:
            return {"valid": False, "message": "Code has been revoked"}
        return {"valid": True, "message": "Code accepted"}
    finally:
        s.close()


@app.post("/api/mark-code-used")
async def mark_code_used(request: Request):
    data = await request.json()
    code = data.get("code", "").strip()
    email = data.get("email", "").strip()
    if code == "FORGE-2026":
        return {"ok": True}
    s = SessionLocal()
    try:
        ic = s.query(InviteCode).filter_by(code=code).first()
        if ic and not ic.revoked:
            ic.used_by_email = email
            ic.used_at = datetime.now(timezone.utc)
            s.commit()
            audit.log("invite_code_used", "system", code, result=email)
    finally:
        s.close()
    return {"ok": True}


@app.get("/api/client-projects/{email}")
async def get_client_projects(email: str):
    """API for website portal to fetch client's projects"""
    s = SessionLocal()
    try:
        projects = s.query(ClientProject).filter_by(client_email=email).all()
        deals = s.query(Deal).filter(Deal.title.like(f"%{email}%")).all()
        
        result = {
            "projects": [{
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "description": p.description,
                "milestones": json.loads(p.milestones) if p.milestones else [],
                "deliverables": json.loads(p.deliverables) if p.deliverables else [],
                "updated": p.updated_at.isoformat() if p.updated_at else None
            } for p in projects],
            "invoices": [{
                "id": d.id,
                "title": d.title,
                "value": d.value,
                "stage": d.stage,
                "payment_status": d.payment_status or "UNPAID"
            } for d in deals]
        }
        return result
    finally:
        s.close()

@app.post("/admin/projects/add")
def admin_add_project(
    client_email: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    status: str = Form("planning")
):
    s = SessionLocal()
    try:
        proj = ClientProject(
            client_email=client_email,
            title=title,
            description=description,
            status=status,
            milestones="[]",
            deliverables="[]"
        )
        s.add(proj)
        s.commit()
        audit.log("add_client_project", "admin", client_email)
    finally:
        s.close()
    return RedirectResponse("/admin/projects", status_code=303)

@app.get("/admin/projects")
def admin_projects_page(request: Request):
    s = SessionLocal()
    try:
        projects = s.query(ClientProject).order_by(ClientProject.id.desc()).all()
    finally:
        s.close()
    return render(request, "admin_projects.html", projects=projects)

@app.post("/admin/projects/{proj_id}/update")
def admin_update_project(
    proj_id: int,
    status: str = Form(...),
    description: str = Form(""),
    milestones: str = Form("")
):
    s = SessionLocal()
    try:
        proj = s.get(ClientProject, proj_id)
        if proj:
            proj.status = status
            proj.description = description
            proj.updated_at = datetime.now(timezone.utc)
            if milestones:
                proj.milestones = json.dumps([m.strip() for m in milestones.split("\n") if m.strip()])
            s.commit()
            audit.log("update_client_project", "admin", f"project#{proj_id}")
    finally:
        s.close()
    return RedirectResponse("/admin/projects", status_code=303)


@app.get("/api/paystack-key")
async def paystack_key():
    cfg = get_payments_config()
    return {"key": cfg.get("paystack_public", ""), "currency": cfg.get("paystack_currency", "") or cfg.get("currency", "USD"), "rate": float(cfg.get("usd_rate", 1) or 1), "business": cfg.get("business_name", "RevenueForge")}

@app.post("/api/subscribe/confirm")
async def subscribe_confirm(request: Request):
    import requests as _rq
    from datetime import timedelta
    data = await request.json()
    ref = data.get("reference", "")
    email = data.get("email", "")
    cfg = get_payments_config()
    secret = cfg.get("paystack_secret", "")
    if not secret or not ref:
        return {"ok": False, "message": "Payment keys not configured"}
    try:
        r = _rq.get(f"https://api.paystack.co/transaction/verify/{ref}",
                    headers={"Authorization": f"Bearer {secret}"}, timeout=15)
        d = r.json()
        if not (d.get("status") and d.get("data", {}).get("status") == "success"):
            return {"ok": False, "message": "Payment not verified"}
    except Exception:
        return {"ok": False, "message": "Verification failed"}
    s = SessionLocal()
    try:
        sub = Subscription(
            email=email,
            plan_label=data.get("plan_label", "Custom"),
            modules=json.dumps(data.get("modules", [])),
            volume=data.get("volume", ""),
            price_monthly=float(data.get("price", 0)),
            status="active",
            paystack_ref=ref,
            renews_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        s.add(sub)
        s.commit()
        audit.log("subscription_created", "system", email, result=f"${sub.price_monthly:.0f}/mo")
        from app.notifications.telegram import send_telegram_message
        send_telegram_message(f"💳 <b>New subscriber:</b> {email} — ${sub.price_monthly:.0f}/mo ({sub.plan_label})")
    finally:
        s.close()
    return {"ok": True, "message": "Subscription active"}

@app.get("/api/subscription/{email}")
async def get_subscription(email: str):
    s = SessionLocal()
    try:
        sub = s.query(Subscription).filter_by(email=email).order_by(Subscription.id.desc()).first()
        if not sub:
            return {"active": False}
        return {"active": True, "plan": sub.plan_label, "modules": json.loads(sub.modules or "[]"),
                "volume": sub.volume, "price": sub.price_monthly, "status": sub.status,
                "renews": sub.renews_at.isoformat() if sub.renews_at else None}
    finally:
        s.close()

@app.get("/admin/subscriptions")
def admin_subscriptions_page(request: Request):
    s = SessionLocal()
    try:
        subs = s.query(Subscription).order_by(Subscription.id.desc()).all()
    finally:
        s.close()
    mrr = sum(x.price_monthly for x in subs if x.status == "active")
    return render(request, "admin_subscriptions.html", subs=subs, mrr=mrr)

@app.post("/admin/subscriptions/{sub_id}/toggle")
def admin_sub_toggle(sub_id: int):
    s = SessionLocal()
    try:
        sub = s.get(Subscription, sub_id)
        if sub:
            sub.status = "cancelled" if sub.status == "active" else "active"
            s.commit()
            audit.log("toggle_subscription", "admin", f"sub#{sub_id}", result=sub.status)
    finally:
        s.close()
    return RedirectResponse("/admin/subscriptions", status_code=303)


@app.get("/health")
def health_check():
    """Health check that verifies database is working"""
    from app.core.models import Job
    s = SessionLocal()
    try:
        # Try to query - this will fail if tables don't exist
        count = s.query(Job).count()
        return {"status": "ok", "jobs_count": count, "database": "connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
    finally:
        s.close()



DISPOSABLE_DOMAINS = {"mailinator.com","tempmail.com","temp-mail.org","10minutemail.com","guerrillamail.com","yopmail.com","trashmail.com","fakeinbox.com","sharklasers.com","getnada.com","dispostable.com","maildrop.cc","mohmal.com","emailondeck.com","mytemp.email","mintemail.com","spamgourmet.com","throwawaymail.com","tempinbox.com","mailnesia.com"}
CAPTCHA_STORE = {}


@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@app.options("/api/join")
@app.options("/api/member-login")
@app.options("/api/captcha")
@app.options("/api/subscriber/profile")
async def cors_preflight(request: Request):
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True})

@app.get("/api/captcha")
async def get_captcha():
    import uuid
    if len(CAPTCHA_STORE) > 1000: CAPTCHA_STORE.clear()
    cid = uuid.uuid4().hex[:10]
    CAPTCHA_STORE[cid] = 0
    return {"id": cid}

@app.post("/api/captcha/pass")
async def captcha_pass(request: Request):
    d = await request.json()
    cid = d.get("id") or ""
    try: ms = int(d.get("ms") or 0)
    except Exception: ms = 0
    if cid in CAPTCHA_STORE and ms >= 400:
        CAPTCHA_STORE[cid] = 1
        return {"ok": True}
    return {"ok": False}

@app.post("/api/join")
async def public_join(request: Request):
    import hashlib, re as _re
    from app.core.models import Member
    d = await request.json()
    if (d.get("website") or "").strip():
        return {"ok": False, "message": "Spam detected"}
    try:
        ms = int(d.get("slide_ms") or 0)
    except Exception:
        ms = 0
    if ms < 400 or ms > 60000:
        return {"ok": False, "message": "Please slide the verification bar first"}
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    if not _re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", email):
        return {"ok": False, "message": "Enter a valid email address"}
    if email.split("@")[1] in DISPOSABLE_DOMAINS:
        return {"ok": False, "message": "Temporary emails are not allowed. Use a real inbox (Gmail, Outlook, Yahoo or work email)."}
    if len(password) < 6:
        return {"ok": False, "message": "Password must be 6+ characters"}
    s = SessionLocal()
    try:
        if s.query(Member).filter_by(email=email).first():
            return {"ok": False, "message": "Account exists — please log in"}
        s.add(Member(email=email, password_hash=hashlib.sha256(password.encode()).hexdigest(), role="client"))
        s.commit()
        return {"ok": True, "key": email}
    finally:
        s.close()



def verify_recaptcha(token):
    import os, json as _json
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
    secret = os.getenv("RECAPTCHA_SECRET", "")
    if not secret:
        return True  # dev mode: secret not set yet
    if not token:
        return False
    try:
        req = Request("https://www.google.com/recaptcha/api/siteverify",
                      data=urlencode({"secret": secret, "response": token}).encode(),
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(req, timeout=10) as r:
            return bool(_json.loads(r.read().decode()).get("success", False))
    except Exception:
        return False


SITE = "https://silentgoodbyelabs.github.io/revenueforge"

@app.post("/api/join-form")
async def join_form(request: Request):
    import hashlib, re as _re, random, os
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    try:
        form = await request.form()
        email = (form.get("email") or "").strip().lower()
        password = form.get("password") or ""
        captcha = form.get("g-recaptcha-response") or ""
        err = ""
        if not _re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", email):
            err = "Enter a valid email address"
        elif email.split("@")[1] in DISPOSABLE_DOMAINS:
            err = "Temporary emails not allowed"
        elif len(password) < 6:
            err = "Password must be 6+ characters"
        elif not verify_recaptcha(captcha):
            err = "Please tick the I'm-not-a-robot box"
        if err:
            return RedirectResponse(SITE + "/register.html?err=" + quote(err))
        s = SessionLocal()
        try:
            m = s.query(Member).filter_by(email=email).first()
            if m and getattr(m, "verified", True):
                return RedirectResponse(SITE + "/signin.html?err=" + quote("Account exists — please log in"))
            if not m:
                m = Member(email=email, password_hash=hashlib.sha256(password.encode()).hexdigest(), role="client")
                s.add(m)
            code6 = str(random.randint(100000, 999999))
            m.verify_code = code6; m.verified = False
            s.commit()
            if send_code(email, code6):
                return RedirectResponse(SITE + "/verify.html?email=" + quote(email))
            m.verified = True; s.commit()
            return RedirectResponse(SITE + "/portal.html?authed=" + quote(email))
        finally:
            s.close()
    except Exception as e:
        return RedirectResponse(SITE + "/register.html?err=" + quote("Server: " + str(e)[:120]))

@app.post("/api/login-form")
async def login_form(request: Request):
    import hashlib, random, os
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    try:
        form = await request.form()
        email = (form.get("email") or "").strip().lower()
        password = form.get("password") or ""
        captcha = form.get("g-recaptcha-response") or ""
        if not verify_recaptcha(captcha):
            return RedirectResponse(SITE + "/signin.html?err=" + quote("Please tick the captcha box"))
        s = SessionLocal()
        try:
            m = s.query(Member).filter_by(email=email).first()
            ok = bool(m and m.password_hash == hashlib.sha256(password.encode()).hexdigest())
            if not ok:
                return RedirectResponse(SITE + "/signin.html?err=" + quote("Wrong email or password"))
            if not getattr(m, "verified", True):
                code6 = str(random.randint(100000, 999999))
                m.verify_code = code6; s.commit()
                if send_code(email, code6):
                    return RedirectResponse(SITE + "/verify.html?email=" + quote(email) + "&err=" + quote("Verify your email first — code sent"))
                m.verified = True; s.commit()
            return RedirectResponse(SITE + "/portal.html?authed=" + quote(email))
        finally:
            s.close()
    except Exception as e:
        return RedirectResponse(SITE + "/signin.html?err=" + quote("Server: " + str(e)[:120]))


@app.get("/api/paystack-public")
async def paystack_public():
    import os
    try: rate = float(os.getenv("USD_RATE", "1"))
    except Exception: rate = 1.0
    return {"key": os.getenv("PAYSTACK_PUBLIC", ""), "currency": os.getenv("PAYSTACK_CURRENCY", "USD"), "rate": rate}


@app.post("/api/subscribe")
async def subscribe(request: Request):
    from app.core.models import Subscription
    d = await request.json()
    email = (d.get("email") or "").strip().lower()
    if not email: return {"ok": False}
    s = SessionLocal()
    try:
        r = s.query(Subscription).filter_by(email=email).first()
        if not r:
            r = Subscription(email=email, volume=d.get("volume", "v50"), status="active")
            s.add(r)
        r.status = "active"
        if hasattr(r, "volume"): r.volume = d.get("volume", "v50")
        if hasattr(r, "plan"): r.plan = d.get("plan", "Starter")
        if hasattr(r, "modules"): r.modules = d.get("modules", "")
        s.commit()
        return {"ok": True}
    finally:
        s.close()


SERVICE_MAP = {
 "python": [("Custom automation scripts","Turn repetitive tasks into one-click Python tools"),("Data extraction tools","Scrape & structure data from any website"),("API integrations","Connect apps so data flows automatically")],
 "ocr": [("Document digitization","Convert scanned PDFs/images into editable data"),("Invoice data-entry automation","Extract invoice fields straight into Excel")],
 "automation": [("Workflow automation","Automate emails, reports & approvals for small business"),("Zapier / Make setup","Design no-code automations that save hours weekly")],
 "web": [("Business websites","Fast, mobile-friendly sites that convert visitors"),("E-commerce stores","Online shops with payments built in")],
 "data": [("Dashboards & reporting","Live dashboards built from messy spreadsheets"),("Data cleaning","Reliable, de-duplicated datasets")],
 "ai": [("AI chatbots","24/7 customer-support bots for any business"),("AI content pipelines","Automate drafting, summarizing & research")],
}
LEAD_MAP = {
 "account": ["Accounting & bookkeeping firms","Tax preparation services","Payroll companies"],
 "ecommerce": ["E-commerce store owners","Dropshipping brands","Amazon FBA sellers"],
 "real": ["Real-estate agencies","Property managers","Airbnb hosts"],
 "clinic": ["Medical & dental clinics","Physiotherapy centers","Vet clinics"],
 "restaurant": ["Restaurants & cafes","Catering companies","Food delivery brands"],
 "school": ["Private schools","Tutoring centers","Online course creators"],
 "law": ["Law firms","Legal consultancies"],
 "fitness": ["Gyms & personal trainers","Yoga studios","Supplement brands"],
}
def suggest_leads(target):
    low = (target or "").lower(); out = []
    for k, v in LEAD_MAP.items():
        if k in low: out += v
    if not out and target.strip():
        t = target.strip().title()
        out = [t + " businesses", "Companies hiring for " + target.strip(), "Agencies serving " + target.strip()]
    seen = set(); res = []
    for s2 in out:
        if s2 not in seen: seen.add(s2); res.append(s2)
    return res[:6]

@app.get("/api/audit")
async def free_audit(request: Request, skills: str = "", target: str = "", member: str = ""):
    from app.core.models import Job, AuditUse, Member
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if not ip and request.client: ip = request.client.host
    s = SessionLocal()
    try:
        allowed = False
        if member:
            mm = s.query(Member).filter_by(email=member.strip().lower()).first()
            allowed = bool(mm and mm.verified)
        if not allowed and ip and s.query(AuditUse).filter_by(ip=ip).first():
            return {"used": True, "jobs": [], "services": [], "leads": []}
        jobs = s.query(Job).order_by(Job.opportunity_score.desc()).limit(20).all()
        kw = [k for k in (skills + " " + target).lower().split() if len(k) > 2]
        out = []
        for j in jobs:
            base = j.opportunity_score or 50
            text = ((j.title or "") + " " + (j.platform or "")).lower()
            hits = sum(1 for k in kw if k in text)
            out.append({"title": j.title, "url": j.url, "platform": j.platform, "score": min(99, base + hits * 5)})
        out.sort(key=lambda x: -x["score"])
        if not allowed and ip:
            s.add(AuditUse(ip=ip, email=member or None)); s.commit()
        return {"jobs": out[:6], "services": suggest_services(skills), "leads": suggest_leads(target)}
    finally:
        s.close()


@app.get("/api/verify")
async def verify_email(email: str = "", code: str = ""):
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    email = email.strip().lower()
    s = SessionLocal()
    try:
        m = s.query(Member).filter_by(email=email).first()
        if m and m.verify_code and m.verify_code == code.strip():
            m.verified = True; m.verify_code = None; s.commit()
            return RedirectResponse(SITE + "/portal.html?authed=" + quote(email))
        return RedirectResponse(SITE + "/verify.html?email=" + quote(email) + "&err=" + quote("Wrong code — try again"))
    finally:
        s.close()

@app.get("/api/resend")
async def resend_code(email: str = ""):
    import random
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    email = email.strip().lower()
    s = SessionLocal()
    try:
        m = s.query(Member).filter_by(email=email).first()
        if m:
            code = str(random.randint(100000, 999999))
            m.verify_code = code; m.verified = False; s.commit()
            send_code(email, code)
        return RedirectResponse(SITE + "/verify.html?email=" + quote(email) + "&err=" + quote("New code sent — check your inbox"))
    finally:
        s.close()


def send_code(email, code):
    import os, json as _json
    txt = "Your RevenueForge verification code is: " + code
    try:
        rk = os.getenv("RESEND_KEY", "")
        if rk:
            from urllib.request import urlopen, Request
            req = Request("https://api.resend.com/emails",
                          data=_json.dumps({"from": "RevenueForge <noreply@resend.dev>", "to": [email],
                                            "subject": "Your verification code", "html": "<p>" + txt + "</p>"}).encode(),
                          headers={"Authorization": "Bearer " + rk, "Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=8) as r: r.read()
            return True
        u = os.getenv("GMAIL_USER", ""); pw = os.getenv("GMAIL_APP_PASS", "")
        if u and pw:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(txt); msg["Subject"] = "RevenueForge verification code"; msg["From"] = u; msg["To"] = email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=8) as s:
                s.login(u, pw); s.sendmail(u, [email], msg.as_string())
            return True
    except Exception as e:
        print("email send failed:", str(e)[:120])
    return False


@app.get("/api/verify")
async def verify_email(email: str = "", code: str = ""):
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    email = email.strip().lower()
    s = SessionLocal()
    try:
        m = s.query(Member).filter_by(email=email).first()
        if m and m.verify_code and m.verify_code == code.strip():
            m.verified = True; m.verify_code = None; s.commit()
            return RedirectResponse(SITE + "/portal.html?authed=" + quote(email))
        return RedirectResponse(SITE + "/verify.html?email=" + quote(email) + "&err=" + quote("Wrong code — try again"))
    finally:
        s.close()

@app.get("/api/resend")
async def resend_code(email: str = ""):
    import random
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    email = email.strip().lower()
    s = SessionLocal()
    try:
        m = s.query(Member).filter_by(email=email).first()
        if m:
            code = str(random.randint(100000, 999999))
            m.verify_code = code; m.verified = False; s.commit()
            send_code(email, code)
        return RedirectResponse(SITE + "/verify.html?email=" + quote(email) + "&err=" + quote("New code sent — check your inbox"))
    finally:
        s.close()





RUN_LIMITS = {"": 2, "v50": 10, "v300": 25, "v1000": 60}

@app.get("/api/run-now")
async def run_now(email: str = ""):
    from datetime import datetime as _dt
    from app.core.models import Subscription, SubscriberProfile, SubscriberJob, Job
    email = email.strip().lower()
    s = SessionLocal()
    try:
        if not s.query(SubscriberProfile).filter_by(email=email).first():
            return {"ok": False, "message": "Set up your robot first in Settings."}
        sub = s.query(Subscription).filter_by(email=email, status="active").first()
        active = bool(sub) and (getattr(sub, "expires_at", None) is None or sub.expires_at > _dt.now())
        vol = getattr(sub, "volume", "") if active else ""
        limit = RUN_LIMITS.get(vol, 2)
        have = 0
        try:
            today = _dt.now().date()
            for sj in s.query(SubscriberJob).filter_by(owner_email=email).all():
                ca = getattr(sj, "created_at", None)
                if ca and getattr(ca, "date", None) and ca.date() == today:
                    have += 1
        except Exception:
            have = 0
        room = limit - have
        if room <= 0:
            return {"ok": True, "delivered": 0, "message": "Daily limit reached. Upgrade for more."}
        pool = s.query(Job).order_by(Job.id.desc()).limit(40).all()
        added = 0
        for j in pool:
            if added >= room: break
            j_url = getattr(j, "url", "") or ""
            if not j_url: continue
            if s.query(SubscriberJob).filter_by(owner_email=email, url=j_url).first(): continue
            try:
                nj = SubscriberJob()
                nj.owner_email = email
                nj.title = getattr(j, "title", "")[:200] or ""
                nj.url = j_url
                # Only write extra columns if they exist on the class
                if hasattr(nj, "platform"): nj.platform = getattr(j, "platform", "") or ""
                if hasattr(nj, "score"): nj.score = getattr(j, "opportunity_score", 0) or 0
                if hasattr(nj, "draft"): nj.draft = getattr(j, "proposal_draft", "") or ""
                s.add(nj)
                added += 1
            except Exception as e:
                continue
        s.commit()
        return {"ok": True, "delivered": added}
    except Exception as e:
        return {"ok": False, "message": "Server: " + str(e)[:120]}
    finally:
        s.close()




def deliver_all():
    import json, urllib.request
    from datetime import datetime
    from app.core.models import Job, SubscriberJob, SubscriberProfile, Subscription, Member
    s = SessionLocal()
    def add(title, url, platform):
        if not url or s.query(Job).filter_by(url=url).first(): return
        s.add(Job(title=title[:200], url=url, platform=platform, opportunity_score=70))
    try:
        with urllib.request.urlopen("https://hn.algolia.com/api/v1/search?query=python+developer&tags=story", timeout=12) as r:
            for h in json.loads(r.read())["hits"][:6]:
                if h.get("url"): add(h.get("title"), h["url"], "HackerNews")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://weworkremotely.com/categories/remote-programming-jobs.rss", timeout=12) as r:
            import xml.etree.ElementTree as ET
            for it in ET.fromstring(r.read()).findall(".//item")[:6]:
                add(it.findtext("title"), it.findtext("link"), "WeWorkRemotely")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://remoteok.com/api", timeout=12) as r:
            for h in json.loads(r.read())[1:7]:
                if h.get("url") and h.get("position"): add(h["position"], h["url"], "RemoteOK")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://www.reddit.com/r/PythonJobs.json", timeout=12) as r:
            for c in json.loads(r.read())["data"]["children"][:6]:
                d = c["data"]; add(d.get("title"), "https://reddit.com" + d.get("permalink"), "Reddit")
    except Exception: pass
    s.commit()
    LIMITS = {"": 2, "v50": 10, "v300": 25, "v1000": 60}
    first = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for m in s.query(Member).all():
        # deliver to every member (profile optional)
        sub = s.query(Subscription).filter_by(email=m.email, status="active").first()
        vol = sub.volume if sub else ""
        room = LIMITS.get(vol, 2) - s.query(SubscriberJob).filter_by(owner_email=m.email).filter(SubscriberJob.created_at >= first).count()
        if room <= 0: continue
        pool = s.query(Job).order_by(Job.opportunity_score.desc()).limit(40).all()
        for j in pool[:room]:
            if not s.query(SubscriberJob).filter_by(owner_email=m.email, url=j.url).first():
                s.add(SubscriberJob(owner_email=m.email, title=j.title, url=j.url, platform=j.platform,
                                    score=j.opportunity_score or 0, draft=j.proposal_draft))
    # OWNER auto-advertise (private engine)
    owner = os.getenv("OWNER_EMAIL", "admin@gmail.com")
    oprof = s.query(SubscriberProfile).filter_by(email=owner).first()
    if oprof and getattr(oprof, "engine_on", False):
        from app.core.models import Product
        for pr in s.query(Product).filter_by(status="active").all():
            if not getattr(pr, "advertised", False):
                send_telegram("@" + (os.getenv("TG_CHANNEL", "") or "revenueforge_ads"),
                              "🛒 " + pr.name + " — " + (pr.description or "") + " $" + str(pr.price or 0) +
                              " | contact: " + (getattr(pr, "contact_value", "") or owner))
                pr.advertised = True
        s.commit()
    s.close()

import asyncio


@app.get("/portal.html")
async def portal_html():
    from fastapi.responses import FileResponse
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "..", "website", "portal.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "portal.html not found"}

@app.get("/api/marketplace")
async def api_marketplace():
    from app.core.models import SubscriberProduct
    s = SessionLocal()
    try:
        rows = s.query(SubscriberProduct).filter_by(status="active").order_by(SubscriberProduct.id.desc()).limit(60).all()
        return {
            "ok": True,
            "products": [
                {
                    "name": r.name,
                    "price": r.price,
                    "description": r.description or "",
                    "seller": r.owner_email,
                    "image": getattr(r, "image_url", "") or "",
                    "video": getattr(r, "video_url", "") or "",
                    "contact_method": getattr(r, "contact_method", "") or "email",
                    "contact_value": getattr(r, "contact_value", "") or r.owner_email
                }
                for r in rows
            ]
        }
    finally:
        s.close()


async def _robot_loop():
    await asyncio.sleep(15)
    while True:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, deliver_all)
        except Exception as e:
            print("robot loop:", str(e)[:100])
        await asyncio.sleep(600)

@app.on_event("startup")
async def _start_robot():
    asyncio.create_task(_robot_loop())


@app.post("/api/save-profile")
async def save_profile(request: Request):
    from app.core.models import SubscriberProfile
    d = await request.json()
    email = (d.get("email") or "").strip().lower()
    if not email: return {"ok": False}
    s = SessionLocal()
    try:
        r = s.query(SubscriberProfile).filter_by(email=email).first()
        if not r:
            r = SubscriberProfile(email=email); s.add(r)
        for f in ["mode", "skills", "target", "whatsapp", "telegram", "engine"]:
            if hasattr(r, f): setattr(r, f, d.get(f, "") or "")
        s.commit(); return {"ok": True}
    finally:
        s.close()

@app.get("/api/get-profile")
async def get_profile(email: str = ""):
    from app.core.models import SubscriberProfile
    email = email.strip().lower()
    s = SessionLocal()
    try:
        r = s.query(SubscriberProfile).filter_by(email=email).first()
        if not r: return {"has": False}
        return {"has": True, "mode": r.mode or "", "skills": r.skills or "", "target": r.target or "", "whatsapp": r.whatsapp or "", "telegram": r.telegram or "", "engine_on": bool(getattr(r, "engine_on", False))}

    finally:
        s.close()

@app.get("/api/run-robot")
async def run_robot(email: str = ""):
    import json, urllib.request, xml.etree.ElementTree as ET
    from datetime import datetime
    from app.core.models import Job, SubscriberJob, SubscriberProfile, Subscription
    email = email.strip().lower()
    s = SessionLocal()
    def add(title, url, platform):
        if not url or s.query(Job).filter_by(url=url).first(): return
        s.add(Job(title=title[:200], url=url, platform=platform, opportunity_score=70))
    try:
        with urllib.request.urlopen("https://hn.algolia.com/api/v1/search?query=python+developer&tags=story", timeout=12) as r:
            for h in json.loads(r.read())["hits"][:6]:
                if h.get("url"): add(h.get("title"), h["url"], "HackerNews")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://weworkremotely.com/categories/remote-programming-jobs.rss", timeout=12) as r:
            for it in ET.fromstring(r.read()).findall(".//item")[:6]:
                add(it.findtext("title"), it.findtext("link"), "WeWorkRemotely")
    except Exception: pass
    try:
        with urllib.request.urlopen("https://www.reddit.com/r/PythonJobs.json", timeout=12) as r:
            for c in json.loads(r.read())["data"]["children"][:6]:
                d = c["data"]; add(d.get("title"), "https://reddit.com" + d.get("permalink"), "Reddit")
    except Exception: pass
    s.commit()
    sub = s.query(Subscription).filter_by(email=email, status="active").first()
    vol = sub.volume if sub else ""
    limit = {"": 2, "v50": 10, "v300": 25, "v1000": 60}.get(vol, 2)
    first = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        have = s.query(SubscriberJob).filter_by(owner_email=email).filter(SubscriberJob.created_at >= first).count()
    except Exception:
        have = s.query(SubscriberJob).filter_by(owner_email=email).count()
    room = limit - have
    pool = s.query(Job).order_by(Job.opportunity_score.desc()).limit(40).all()
    if room > 0:
        for j in pool[:room]:
            if not s.query(SubscriberJob).filter_by(owner_email=email, url=j.url).first():
                s.add(SubscriberJob(owner_email=email, title=j.title, url=j.url, platform=j.platform,
                                    score=j.opportunity_score or 0, draft=j.proposal_draft))
    s.commit()
    rows = s.query(SubscriberJob).filter_by(owner_email=email).order_by(SubscriberJob.id.desc()).limit(20).all()
    out = [{"title": r.title, "url": r.url, "platform": r.platform, "score": r.score, "draft": r.draft} for r in rows]
    s.close()
    return {"results": out}

@app.get("/api/join-get")
async def join_get(request: Request, email: str = "", password: str = "", slide_ms: int = 0, website: str = "", captcha: str = ""):
    import hashlib, re as _re, random, os
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    if not captcha: captcha = request.query_params.get("g-recaptcha-response", "")
    try:
        email = email.strip().lower(); err = ""
        if not _re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", email): err = "Enter a valid email address"
        elif email.split("@")[1] in DISPOSABLE_DOMAINS: err = "Temporary emails not allowed"
        elif len(password) < 6: err = "Password must be 6+ characters"
        elif not verify_recaptcha(captcha): err = "Please tick the I'm-not-a-robot box"
        if err: return RedirectResponse(SITE + "/register.html?err=" + quote(err))
        s = SessionLocal()
        try:
            m = s.query(Member).filter_by(email=email).first()
            if m and getattr(m, "verified", True):
                return RedirectResponse(SITE + "/signin.html?err=" + quote("Account exists — please log in"))
            if not m:
                m = Member(email=email, password_hash=hashlib.sha256(password.encode()).hexdigest(), role="client"); s.add(m)
            code6 = str(random.randint(100000, 999999)); m.verify_code = code6; m.verified = False; s.commit()
            if send_code(email, code6):
                return RedirectResponse(SITE + "/verify.html?email=" + quote(email))
            m.verified = True; s.commit()
            return RedirectResponse(SITE + "/portal.html?authed=" + quote(email))
        finally:
            s.close()
    except Exception as e:
        return RedirectResponse(SITE + "/register.html?err=" + quote("Server: " + str(e)[:120]))

@app.get("/api/login-get")
async def login_get(request: Request, email: str = "", password: str = "", captcha: str = ""):
    import hashlib, random
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    from app.core.models import Member
    if not captcha: captcha = request.query_params.get("g-recaptcha-response", "")
    try:
        email = email.strip().lower()
        if not verify_recaptcha(captcha):
            return RedirectResponse(SITE + "/signin.html?err=" + quote("Please tick the captcha box"))
        s = SessionLocal()
        try:
            m = s.query(Member).filter_by(email=email).first()
            ok = bool(m and m.password_hash == hashlib.sha256(password.encode()).hexdigest())
            if not ok: return RedirectResponse(SITE + "/signin.html?err=" + quote("Wrong email or password"))
            if not getattr(m, "verified", True):
                code6 = str(random.randint(100000, 999999)); m.verify_code = code6; s.commit()
                if send_code(email, code6):
                    return RedirectResponse(SITE + "/verify.html?email=" + quote(email) + "&err=" + quote("Verify first — code sent"))
                m.verified = True; s.commit()
            return RedirectResponse(SITE + "/portal.html?authed=" + quote(email))
        finally:
            s.close()
    except Exception as e:
        return RedirectResponse(SITE + "/signin.html?err=" + quote("Server: " + str(e)[:120]))


@app.post("/api/member-login")
async def member_login(request: Request):
    import hashlib, re
    from app.core.models import Member
    d = await request.json()
    ident = (d.get("identifier") or d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    s = SessionLocal()
    try:
        if "@" in ident:
            m = s.query(Member).filter_by(email=ident).first()
        else:
            m = s.query(Member).filter_by(phone=re.sub(r"[^0-9+]", "", ident)).first()
        if m and m.password_hash == hashlib.sha256(password.encode()).hexdigest():
            return {"ok": True, "role": m.role, "key": m.email or m.phone}
        return {"ok": False, "message": "Wrong email/phone or password"}
    finally:
        s.close()


def _heal_schema():
    try:
        from app.core.db import engine
        from sqlalchemy import text, inspect as sa_inspect
        if not engine.url.drivername.startswith("postgres"):
            return
        from app.core.models import Base
        insp = sa_inspect(engine)
        added = []
        with engine.connect() as c:
            for table in Base.metadata.sorted_tables:
                if not insp.has_table(table.name):
                    continue
                existing = {col["name"] for col in insp.get_columns(table.name)}
                for col in table.columns:
                    if col.name not in existing:
                        typ = col.type.compile(engine.dialect)
                        c.execute(text('ALTER TABLE %s ADD COLUMN IF NOT EXISTS "%s" %s' % (table.name, col.name, typ)))
                        added.append(f"{table.name}.{col.name}")
            c.commit()
        print("✅ schema synced" + (": " + ", ".join(added) if added else " (nothing missing)"))
    except Exception as e:
        print("schema heal skipped:", e)

_heal_schema()

@app.get("/api/owner/products")
async def owner_products():
    from app.core.models import Product
    s = SessionLocal()
    try:
        rows = s.query(Product).filter_by(status="active").order_by(Product.id.desc()).all()
        return {"products": [{"id": r.id, "name": r.name, "price": r.price, "description": r.description or "", 
                "image": getattr(r,"image_url","") or "", "video": getattr(r,"video_url","") or "",
                "contact_method": getattr(r,"contact_method","") or "email", 
                "contact_value": getattr(r,"contact_value","") or ""} for r in rows]}
    finally:
        s.close()

@app.post("/api/owner/products")
async def add_owner_product(request: Request):
    from app.core.models import Product
    d = await request.json()
    name = (d.get("name") or "").strip()
    if not name: return {"ok": False}
    s = SessionLocal()
    try:
        p = Product(name=name, price=int(d.get("price") or 0), description=d.get("description") or "")
        if hasattr(p, "image_url"): p.image_url = d.get("image_url", "")
        if hasattr(p, "video_url"): p.video_url = d.get("video_url", "")
        if hasattr(p, "contact_method"): p.contact_method = d.get("contact_method", "email")
        if hasattr(p, "contact_value"): p.contact_value = d.get("contact_value", "")
        s.add(p); s.commit(); return {"ok": True, "id": p.id}
    finally:
        s.close()


@app.post("/api/engine-toggle")
async def engine_toggle(request: Request):
    from app.core.models import SubscriberProfile
    d = await request.json(); email = (d.get("email") or "").strip().lower(); on = bool(d.get("on"))
    s = SessionLocal()
    try:
        r = s.query(SubscriberProfile).filter_by(email=email).first()
        if not r: r = SubscriberProfile(email=email); s.add(r)
        if hasattr(r, "engine_on"): r.engine_on = on
        s.commit(); return {"ok": True, "on": on}
    finally:
        s.close()

@app.post("/api/owner/advertise-now")
async def owner_advertise_now():
    import os
    from app.core.models import Product
    from app.core.advertise import send_telegram
    s = SessionLocal(); n = 0
    try:
        owner = os.getenv("OWNER_EMAIL", "admin@gmail.com")
        for pr in s.query(Product).filter_by(status="active").all():
            if not getattr(pr, "advertised", False):
                send_telegram("@" + (os.getenv("TG_CHANNEL", "") or "revenueforge_ads"),
                              "🛒 " + pr.name + " — " + (pr.description or "") + " $" + str(pr.price or 0) +
                              " | contact: " + (getattr(pr, "contact_value", "") or owner))
                pr.advertised = True; n += 1
        s.commit(); return {"ok": True, "advertised": n}
    finally:
        s.close()




@app.post("/api/owner/products/{pid}/delete")
async def owner_delete_product(pid: int):
    from app.core.models import Product
    s = SessionLocal()
    try:
        p = s.query(Product).filter_by(id=pid).first()
        if not p:
            return {"ok": False, "error": "Product not found"}
        s.delete(p)
        s.commit()
        return {"ok": True, "id": pid}
    finally:
        s.close()






@app.get("/api/job-sources")
async def job_sources():
    from app.core.hiring_search import SOURCE_NAMES
    return {"ok": True, "count": len(SOURCE_NAMES), "sources": SOURCE_NAMES}

@app.post("/api/save-alerts")
async def save_alerts(request: Request):
    p = await request.json(); email = p.get("email", "")
    s = SessionLocal()
    try:
        from app.core.models import Subscriber
        row = s.query(Subscriber).filter_by(email=email).first()
        if row:
            for k in ["telegram", "whatsapp"]:
                if hasattr(row, k): setattr(row, k, p.get(k, ""))
            s.commit()
        return {"ok": True}
    finally:
        s.close()

@app.post("/api/alert-test")
async def alert_test(request: Request):
    p = await request.json(); email = p.get("email", "")
    from app.core.alerts import send_telegram, send_whatsapp, telegram_ok, whatsapp_ok
    s = SessionLocal(); tg = wa = ""
    try:
        from app.core.models import Subscriber
        row = s.query(Subscriber).filter_by(email=email).first()
        if row: tg = getattr(row, "telegram", "") or ""; wa = getattr(row, "whatsapp", "") or ""
    finally:
        s.close()
    ok_t = send_telegram(tg, "✅ RevenueForge alerts connected!") if telegram_ok() and tg else False
    ok_w = send_whatsapp(wa, "RevenueForge alerts connected!") if whatsapp_ok() and wa else False
    return {"ok": True, "telegram": "sent" if ok_t else ("no token" if not telegram_ok() else "no chat id"), "whatsapp": "sent" if ok_w else ("no token" if not whatsapp_ok() else "no number")}

@app.post("/api/auto-advertise")
async def auto_advertise(request: Request):
    p = await request.json(); email = p.get("email", "")
    from app.core.models import SubscriberProduct, Subscriber
    from app.core.alerts import send_telegram, telegram_ok
    s = SessionLocal()
    try:
        rows = s.query(SubscriberProduct).filter_by(owner_email=email, status="active").all()
        caps = "\n".join([f"🛒 {r.name} — ${r.price}. Contact: {r.contact_method} {r.contact_value}" for r in rows]) or "No services yet"
        row = s.query(Subscriber).filter_by(email=email).first()
        plan = getattr(row, "plan", "Free") if row else "Free"
        tg_id = getattr(row, "telegram", "") if row else ""
        tg = (plan == "Pro") and telegram_ok() and tg_id and send_telegram(tg_id, "📢 RevenueForge Marketplace:\n" + caps)
        return {"ok": True, "marketplace": "auto", "telegram": "auto" if tg else ("Pro required" if plan != "Pro" else "not connected"), "whatsapp": "not connected", "social_20": "one-tap (connect logins for full auto)"}
    finally:
        s.close()

@app.post("/api/upgrade")
async def upgrade(request: Request):
    import os
    import requests as rq
    p = await request.json(); email = p.get("email", "")
    key = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not key: return {"ok": False, "error": "Paystack keys not in Render env"}
    try:
        r = rq.post("https://api.paystack.co/transaction/initialize",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json={"email": email, "amount": int(os.environ.get("PRO_AMOUNT", "1900")),
                  "currency": os.environ.get("PAYSTACK_CURRENCY", "USD"),
                  "callback_url": "https://silentgoodbyelabs.github.io/revenueforge/portal.html?pay=1",
                  "metadata": {"email": email}}, timeout=15)
        d = r.json()
        if d.get("status"): return {"ok": True, "url": d["data"]["authorization_url"], "ref": d["data"]["reference"]}
        return {"ok": False, "error": d.get("message", "Paystack error")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}

@app.get("/api/paystack/verify")
async def paystack_verify(ref: str = "", email: str = ""):
    import os
    import requests as rq
    key = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not key or not ref: return {"ok": False, "plan": "Free"}
    try:
        r = rq.get("https://api.paystack.co/transaction/verify/" + ref, headers={"Authorization": "Bearer " + key}, timeout=15)
        d = r.json()
        ok = bool(d.get("status")) and d.get("data", {}).get("status") == "success"
        if ok:
            s = SessionLocal()
            try:
                from app.core.models import Subscriber
                em = email or d.get("data", {}).get("customer", {}).get("email", "")
                row = s.query(Subscriber).filter_by(email=em).first()
                if row: row.plan = "Pro"; s.commit()
            finally:
                s.close()
        return {"ok": ok, "plan": "Pro" if ok else "Free"}
    except Exception:
        return {"ok": False, "plan": "Free"}

@app.get("/api/my/products")
async def my_products(email: str = ""):
    from app.core.models import SubscriberProduct, Product
    if not email: return {"ok": True, "products": []}
    s = SessionLocal()
    try:
        owner_names = set()
        try: owner_names = {r.name for r in s.query(Product).all()}
        except Exception: pass
        rows = s.query(SubscriberProduct).filter_by(owner_email=email).order_by(SubscriberProduct.id.desc()).all()
        rows = [r for r in rows if r.name not in owner_names]
        return {"ok": True, "products": [{"id": r.id, "name": r.name, "price": r.price, "description": r.description or "", "image": getattr(r, "image_url", "") or "", "contact_method": getattr(r, "contact_method", "") or "email", "contact_value": getattr(r, "contact_value", "") or email} for r in rows]}
    finally:
        s.close()


@app.post("/api/my/products/{pid}/delete")
async def my_delete_product(pid: int, email: str = ""):
    from app.core.models import SubscriberProduct
    s = SessionLocal()
    try:
        row = s.query(SubscriberProduct).filter_by(id=pid, owner_email=email).first()
        if not row: return {"ok": False, "error": "not yours"}
        s.delete(row); s.commit()
        return {"ok": True}
    finally:
        s.close()

async def _sub_info(email, request):
    import time as _t
    out = {"plan": "Free", "paid": False, "trial_active": False, "active": False, "trial_hours_left": 0, "flagged": False, "limits": {"matches": 5, "can_sell": False, "alerts": False}}
    if not email: return out
    try:
        from app.core.models import Subscriber
        s = SessionLocal()
        try:
            row = s.query(Subscriber).filter_by(email=email).first()
            if not row: return out
            try:
                if not getattr(row, "trial_expires", ""):
                    row.trial_expires = str(_t.time() + 24*3600); s.commit()
            except Exception: s.rollback()
            if request is not None:
                try:
                    ip = request.client.host if request.client else ""
                    if ip and not getattr(row, "ip", ""):
                        row.ip = ip; s.commit()
                    if ip and s.query(Subscriber).filter_by(ip=ip).count() > 1:
                        for r2 in s.query(Subscriber).filter_by(ip=ip).all(): r2.flagged = "1"
                        s.commit()
                except Exception: s.rollback()
            plan = getattr(row, "plan", "Free") or "Free"
            paid = plan not in ("Free", "free", "")
            try: left = max(0.0, (float(getattr(row, "trial_expires", "0") or 0) - _t.time())/3600.0)
            except Exception: left = 0.0
            out.update({"plan": plan, "paid": paid, "trial_active": left > 0, "active": paid or left > 0, "trial_hours_left": round(left, 1), "flagged": str(getattr(row, "flagged", "0")) == "1", "limits": {"matches": 5 if not paid else 999, "can_sell": paid, "alerts": paid}})
            return out
        finally:
            s.close()
    except Exception:
        return out


@app.get("/api/sub/{email}")
async def api_sub(email: str, request: Request):
    return await _sub_info(email, request)

@app.get("/api/search-hiring")
async def api_search_hiring(q: str = "", limit: int = 25, email: str = ""):
    from app.core.hiring_search import search_hiring
    sub = await _sub_info(email, None)
    if not sub["active"]:
        return {"ok": False, "error": "trial_expired", "query": q, "count": 0, "results": []}
    if not sub["paid"]:
        limit = min(limit, 5)
    results = search_hiring(q, limit)
    return {"ok": True, "query": q, "count": len(results), "results": results, "plan": sub["plan"]}

@app.post("/api/my/products")
async def my_add_product(request: Request):
    from app.core.models import SubscriberProduct
    p = await request.json()
    email = p.get("email", "")
    sub = await _sub_info(email, None)
    if not sub["paid"]:
        return {"ok": False, "error": "Publishing & selling is a Pro feature - upgrade in Plan & Billing."}
    s = SessionLocal()
    try:
        row = SubscriberProduct(owner_email=email, name=p.get("name", ""), price=p.get("price", 0), description=p.get("description", ""), status="active")
        for k in ["image_url", "video_url", "contact_method", "contact_value"]:
            if hasattr(row, k): setattr(row, k, p.get(k, ""))
        s.add(row); s.commit()
        return {"ok": True, "id": row.id}
    finally:
        s.close()

@app.post("/api/redeem")
async def redeem(request: Request):
    p = await request.json(); email = p.get("email", ""); code = (p.get("code") or "").strip().upper()
    from app.core.models import Subscriber, UpgradeCode
    s = SessionLocal()
    try:
        rowc = s.query(UpgradeCode).filter_by(code=code, used="").first()
        if not rowc: return {"ok": False, "error": "Invalid or already used code"}
        row = s.query(Subscriber).filter_by(email=email).first()
        if not row: return {"ok": False, "error": "Account not found"}
        row.plan = rowc.plan; rowc.used = email; s.commit()
        return {"ok": True, "plan": rowc.plan}
    finally:
        s.close()

@app.post("/api/owner/codes")
async def owner_codes(request: Request):
    import random, string
    p = await request.json(); plan = p.get("plan", "Pro")
    from app.core.models import UpgradeCode
    s = SessionLocal()
    try:
        code = plan.upper()[:1] + "-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        s.add(UpgradeCode(code=code, plan=plan, used="")); s.commit()
        return {"ok": True, "code": code}
    finally:
        s.close()

@app.get("/api/owner/flagged")
async def owner_flagged():
    from app.core.models import Subscriber
    s = SessionLocal()
    try:
        return {"ok": True, "accounts": [{"email": r.email, "ip": getattr(r, "ip", ""), "plan": getattr(r, "plan", "Free")} for r in s.query(Subscriber).filter_by(flagged="1").all()]}
    finally:
        s.close()

def _ps_secret():
    import os
    return os.environ.get("PAYSTACK_SECRET_KEY") or os.environ.get("PAYSTACK_SECRET") or os.environ.get("PAYSTACK_SK") or ""

@app.get("/api/paystack/key")
async def paystack_key():
    import os
    k = os.environ.get("PAYSTACK_PUBLIC_KEY") or os.environ.get("PAYSTACK_PUBLIC") or ""
    found = [n for n in os.environ.keys() if "PAY" in n.upper() or "STACK" in n.upper()]
    return {"ok": True, "key": k, "found": found}

@app.post("/api/paystack/init")
async def paystack_init(request: Request):
    import requests as _rq
    p = await request.json()
    email = p.get("email", ""); amount = float(p.get("amount", 0)); plan = p.get("plan", "Pro")
    secret = _ps_secret()
    if not secret: return {"ok": False, "error": "Payment keys not configured on server"}
    hdr = {"Authorization": "Bearer " + secret}
    body = {"email": email, "metadata": {"plan": plan}, "callback_url": "https://silentgoodbyelabs.github.io/revenueforge/portal.html"}
    for cur, mult in [("USD", 100), ("NGN", 160000)]:
        try:
            b2 = dict(body); b2["amount"] = int(amount * mult); b2["currency"] = cur
            r = _rq.post("https://api.paystack.co/transaction/initialize", json=b2, headers=hdr, timeout=15)
            d = r.json()
            if d.get("status"):
                return {"ok": True, "url": d["data"]["authorization_url"], "reference": d["data"]["reference"]}
        except Exception:
            continue
    return {"ok": False, "error": "Could not start payment — check Paystack dashboard"}

@app.post("/api/paystack/verify")
async def paystack_verify(request: Request):
    import requests as _rq
    p = await request.json()
    ref = p.get("reference", ""); email = p.get("email", "")
    secret = _ps_secret()
    if not secret or not ref: return {"ok": False, "error": "missing"}
    try:
        r = _rq.get("https://api.paystack.co/transaction/verify/" + ref, headers={"Authorization": "Bearer " + secret}, timeout=15)
        d = r.json()
    except Exception:
        return {"ok": False, "error": "Verification failed"}
    if d.get("status") and (d.get("data") or {}).get("status") == "success":
        plan = "Pro"
        meta = d["data"].get("metadata") or {}
        if isinstance(meta, dict) and meta.get("plan"): plan = str(meta["plan"])
        else:
            amt = (d["data"].get("amount", 0) or 0) / 100.0
            plan = "Pro" if amt < 4000 else "Growth"
        from app.core.models import Subscriber
        s = SessionLocal()
        try:
            row = s.query(Subscriber).filter_by(email=email).first()
            if row: row.plan = plan; s.commit()
        finally:
            s.close()
        return {"ok": True, "plan": plan}
    return {"ok": False, "error": "Payment not successful"}

@app.post("/api/advertise-service")
async def advertise_service(request: Request):
    import os
    p = await request.json(); email = p.get("email", ""); pid = p.get("id")
    from app.core.models import SubscriberProduct
    s = SessionLocal()
    actions = ["Listed live on the public Marketplace"]
    try:
        row = s.query(SubscriberProduct).filter_by(id=pid, owner_email=email).first()
        if row:
            tok = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
            chat = os.environ.get("TELEGRAM_CHANNEL") or ""
            if tok and chat:
                try:
                    import requests as _rq
                    txt = "🚀 " + str(row.name) + " — $" + str(row.price) + "\n" + (row.description or "") + "\nContact: " + (row.contact_method or "") + " " + (row.contact_value or email)
                    _rq.post("https://api.telegram.org/bot" + tok + "/sendMessage", json={"chat_id": chat, "text": txt}, timeout=10)
                    actions.append("Posted to your Telegram channel")
                except Exception:
                    actions.append("Telegram post queued")
            else:
                actions.append("Telegram auto-post activates once bot token is set")
    finally:
        s.close()
    actions.append("20+ platform ad pack copied (one tap each)")
    return {"ok": True, "actions": actions}

def _rf_clean_owner_copy():
    # removes private products the loop copied into the customer marketplace (admin only)
    try:
        from app.core.models import SubscriberProduct
        s = SessionLocal()
        try:
            for r in s.query(SubscriberProduct).filter_by(owner_email="admin@gmail.com").all():
                s.delete(r)
            s.commit(); print("CLEAN_OWNER_COPY done")
        finally:
            s.close()
    except Exception as e:
        print("clean skip:", e)

def _rf_migrate():
    try:
        from sqlalchemy import inspect, text
        from app.core.db import engine
        from app.core.models import Subscriber
        tn = Subscriber.__tablename__
        insp = inspect(engine)
        if insp.has_table(tn):
            cols = [x["name"] for x in insp.get_columns(tn)]
            with engine.begin() as conn:
                if "ip" not in cols: conn.execute(text("ALTER TABLE " + tn + " ADD COLUMN ip VARCHAR DEFAULT ''"))
                if "flagged" not in cols: conn.execute(text("ALTER TABLE " + tn + " ADD COLUMN flagged VARCHAR DEFAULT '0'"))
                if "trial_expires" not in cols: conn.execute(text("ALTER TABLE " + tn + " ADD COLUMN trial_expires VARCHAR DEFAULT ''"))
    except Exception as e:
        print("migrate skip:", e)
_rf_clean_owner_copy()
_rf_migrate()
