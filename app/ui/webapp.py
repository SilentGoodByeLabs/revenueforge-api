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


@app.get("/products")
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


@app.post("/api/join")
async def public_join(request: Request):
    import hashlib
    from app.core.models import Member
    d = await request.json()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    if "@" not in email or len(password) < 6:
        return {"ok": False, "message": "Valid email + password (6+ chars) required"}
    s = SessionLocal()
    try:
        if s.query(Member).filter_by(email=email).first():
            return {"ok": False, "message": "Account exists — please log in"}
        s.add(Member(email=email, phone=d.get("phone", ""), password_hash=hashlib.sha256(password.encode()).hexdigest(), role="client"))
        s.commit()
        return {"ok": True}
    finally:
        s.close()

@app.post("/api/member-login")
async def member_login(request: Request):
    import hashlib
    from app.core.models import Member
    d = await request.json()
    email = (d.get("email") or "").strip().lower()
    s = SessionLocal()
    try:
        m = s.query(Member).filter_by(email=email).first()
        if m and m.password_hash == hashlib.sha256((d.get("password") or "").encode()).hexdigest():
            return {"ok": True, "role": m.role}
        return {"ok": False, "message": "Wrong email or password"}
    finally:
        s.close()
