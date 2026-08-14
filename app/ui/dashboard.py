import json
import os

import streamlit as st

from app.core.db import Base, engine, SessionLocal
from app.core.models import Job, Product, Company, Prospect
from app.core.scoring import analyze_job
from app.core.proposals import generate_proposal
from app.core.config import (
    BASE_DIR,
    CONFIG_DIR,
    LOGS_DIR,
    get_profile_config,
    get_categories_config,
    get_guardrails_config,
    _load_json,
)
from app.core import audit

Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="RevenueForge Control Center", page_icon="🛡️", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer[role="contentinfo"] {visibility: hidden;}
    div[data-testid="stMetric"]{background:#ffffff;border:1px solid #E5ECF3;border-radius:12px;padding:12px;box-shadow:0 4px 14px rgba(10,37,64,.06)}
    div[data-testid="stMetric"] label{color:#5C7186 !important;font-weight:600}
    div[data-testid="stMetric"] div{color:#0A2540 !important}
    h1,h2,h3,h4{color:#0A2540 !important}
    div[data-testid="stSidebar"]{background:#0A2540 !important}
    div[data-testid="stSidebar"] p, div[data-testid="stSidebar"] span, div[data-testid="stSidebar"] label{color:#DCE7F3 !important}
    div[data-testid="stSidebar"] h1{color:#ffffff !important}
    div[data-testid="stExpander"]{border:1px solid #E5ECF3;border-radius:12px;background:#ffffff}
    .stButton>button{border-radius:10px}
    </style>
    """,
    unsafe_allow_html=True,
)

PROSPECT_STATUSES = [
    "new", "qualified", "contacted", "replied",
    "meeting", "proposal", "won", "lost", "do_not_contact",
]


def update_env_key(key: str, value: str):
    env_path = BASE_DIR / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            lines[i] = f"{key}={value}"
            found = True
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")


def page_overview():
    st.title("📊 Command Center")
    session = SessionLocal()
    try:
        jobs = session.query(Job).all()
        product_count = session.query(Product).count()
        prospect_count = session.query(Prospect).count()
    finally:
        session.close()

    approved = [j for j in jobs if j.approved]
    submitted = [j for j in jobs if j.submitted]
    apply_jobs = [j for j in jobs if j.recommendation == "APPLY"]
    avg = (sum(j.opportunity_score for j in jobs) / len(jobs)) if jobs else 0.0

    c = st.columns(6)
    c[0].metric("Opportunities", len(jobs))
    c[1].metric("APPLY picks", len(apply_jobs))
    c[2].metric("Approved", len(approved))
    c[3].metric("Submitted", len(submitted))
    c[4].metric("Products", product_count)
    c[5].metric("Prospects", prospect_count)

    st.metric("Average opportunity score", f"{avg:.1f}/100")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recommendation mix")
        dist = {
            "APPLY": len(apply_jobs),
            "REVIEW": len([j for j in jobs if j.recommendation == "REVIEW"]),
            "SKIP": len([j for j in jobs if j.recommendation == "SKIP"]),
        }
        st.bar_chart(dist)
    with col2:
        st.subheader("Recent opportunities")
        rows = [
            {
                "id": j.id,
                "title": j.title[:40],
                "score": round(j.opportunity_score, 1),
                "rec": j.recommendation,
                "status": j.status,
            }
            for j in sorted(jobs, key=lambda x: x.id, reverse=True)[:8]
        ]
        st.dataframe(rows)


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


def page_jobs():
    st.title("💼 Job Agent")
    tab_queue, tab_add = st.tabs(["📥 Approval Queue", "➕ Add Opportunity"])

    with tab_queue:
        session = SessionLocal()
        try:
            jobs = session.query(Job).order_by(Job.id.desc()).all()
        finally:
            session.close()

        rec_filter = st.selectbox("Filter by recommendation", ["ALL", "APPLY", "REVIEW", "SKIP"])
        status_filter = st.selectbox("Filter by status", ["ALL", "new", "scored", "approved", "submitted", "rejected"])

        filtered = jobs
        if rec_filter != "ALL":
            filtered = [j for j in filtered if j.recommendation == rec_filter]
        if status_filter != "ALL":
            filtered = [j for j in filtered if j.status == status_filter]

        if not filtered:
            st.info("No opportunities match this filter. Add one in the 'Add Opportunity' tab.")

        for job in filtered:
            with st.expander(f"#{job.id} · {job.title} · {job.opportunity_score:.0f}/100 · {job.recommendation} · {job.status}"):
                r1 = st.columns(5)
                r1[0].metric("Technical fit", f"{job.technical_fit:.0f}")
                r1[1].metric("Budget", f"{job.budget_score:.0f}")
                r1[2].metric("Clarity", f"{job.clarity_score:.0f}")
                r1[3].metric("Client quality", f"{job.client_quality:.0f}")
                r1[4].metric("Competition", f"{job.competition_score:.0f}")
                r2 = st.columns(4)
                r2[0].metric("Urgency", f"{job.urgency_score:.0f}")
                r2[1].metric("Long-term", f"{job.long_term_score:.0f}")
                r2[2].metric("Recurring", f"{job.recurring_score:.0f}")
                r2[3].metric("Scam risk", f"{job.scam_risk:.0f}")

                st.markdown("**Reasoning**")
                st.write(job.reason or "—")

                st.markdown("**Proposal draft**")
                st.text_area("Proposal", value=job.proposal_draft or "Run scoring first.", height=260, key=f"prop_{job.id}")

                b1, b2, b3, b4 = st.columns(4)
                if b1.button("✅ Approve", key=f"appr_{job.id}"):
                    s = SessionLocal()
                    try:
                        j = s.get(Job, job.id)
                        j.approved = True
                        j.status = "approved"
                        s.commit()
                        audit.log("approve_job", "human", f"job#{job.id}", approval="approved")
                    finally:
                        s.close()
                    st.success("Approved. Submit manually via the official platform.")
                    st.rerun()
                if b2.button("❌ Reject", key=f"rej_{job.id}"):
                    s = SessionLocal()
                    try:
                        j = s.get(Job, job.id)
                        j.status = "rejected"
                        s.commit()
                        audit.log("reject_job", "human", f"job#{job.id}", approval="rejected")
                    finally:
                        s.close()
                    st.rerun()
                if b3.button("📤 Mark Submitted", key=f"sub_{job.id}"):
                    s = SessionLocal()
                    try:
                        j = s.get(Job, job.id)
                        j.submitted = True
                        j.status = "submitted"
                        s.commit()
                        audit.log("mark_submitted", "human", f"job#{job.id}")
                    finally:
                        s.close()
                    st.rerun()
                if b4.button("🔁 Re-score", key=f"rescore_{job.id}"):
                    s = SessionLocal()
                    try:
                        j = s.get(Job, job.id)
                        analysis = analyze_job(j)
                        apply_analysis(j, analysis)
                        j.proposal_draft = generate_proposal(j, analysis)
                        j.status = "scored"
                        s.commit()
                        audit.log("rescore_job", "job_agent", f"job#{job.id}", result=f"{analysis['opportunity_score']:.0f} {analysis['recommendation']}")
                    finally:
                        s.close()
                    st.rerun()

    with tab_add:
        with st.form("add_job_form"):
            title = st.text_input("Title *")
            c1, c2 = st.columns(2)
            platform = c1.selectbox("Platform", ["Upwork", "Fiverr", "LinkedIn", "Company website", "Referral", "RemoteOK", "Wellfound", "Other"])
            source = c2.text_input("Source", value="manual")
            url = st.text_input("URL")
            client = st.text_input("Client")
            c3, c4 = st.columns(2)
            budget = c3.text_input("Budget (e.g. Fixed $1500 or $30/hr)")
            deadline = c4.text_input("Deadline")
            skills = st.text_input("Required skills (comma separated)")
            description = st.text_area("Description *", height=200)
            do_submit = st.form_submit_button("Add & Score")
            if do_submit:
                if not title or not description:
                    st.error("Title and description are required.")
                else:
                    s = SessionLocal()
                    try:
                        j = Job(
                            title=title, platform=platform, source=source, url=url,
                            client=client, description=description, budget_text=budget,
                            deadline=deadline, required_skills=skills,
                        )
                        s.add(j)
                        s.commit()
                        s.refresh(j)
                        analysis = analyze_job(j)
                        apply_analysis(j, analysis)
                        j.proposal_draft = generate_proposal(j, analysis)
                        j.status = "scored"
                        s.commit()
                        audit.log("add_job", "human", f"job#{j.id}")
                        audit.log("score_job", "job_agent", f"job#{j.id}", result=f"{analysis['opportunity_score']:.0f} {analysis['recommendation']}")
                        st.success(f"Added and scored: {analysis['opportunity_score']:.0f}/100 → {analysis['recommendation']}")
                    finally:
                        s.close()


def page_sales():
    st.title("🎯 Sales Agent")
    st.caption("Outreach is drafted for your approval only. Nothing is sent automatically. Opt-outs are always respected.")
    tab_pipe, tab_add = st.tabs(["🧲 Pipeline", "➕ Add Prospect"])

    with tab_pipe:
        session = SessionLocal()
        try:
            prospects = session.query(Prospect).order_by(Prospect.id.desc()).all()
        finally:
            session.close()

        if not prospects:
            st.info("No prospects yet. Add your first prospect in the 'Add Prospect' tab.")

        for p in prospects:
            with st.expander(f"#{p.id} · {p.name or 'Unknown'} · {p.status} · fit {p.fit_score:.0f}"):
                st.markdown(f"**Email:** {p.email or '—'}  |  **Role:** {p.role or '—'}  |  **Source:** {p.source}")
                st.markdown(f"**Product interest:** {p.product_interest or '—'}")
                st.write(p.notes or "")

                if p.opted_out or p.status == "do_not_contact":
                    st.warning("⛔ Opted out / do not contact. All outreach disabled.")
                    continue

                b1, b2 = st.columns(2)
                new_status = b1.selectbox("Update status", PROSPECT_STATUSES, index=PROSPECT_STATUSES.index(p.status), key=f"st_{p.id}")
                if b1.button("Save status", key=f"sts_{p.id}"):
                    s = SessionLocal()
                    try:
                        pr = s.get(Prospect, p.id)
                        pr.status = new_status
                        s.commit()
                        audit.log("update_prospect_status", "human", f"prospect#{p.id}", result=new_status)
                    finally:
                        s.close()
                    st.rerun()
                if b2.button("⛔ Mark do-not-contact", key=f"dnc_{p.id}"):
                    s = SessionLocal()
                    try:
                        pr = s.get(Prospect, p.id)
                        pr.opted_out = True
                        pr.status = "do_not_contact"
                        s.commit()
                        audit.log("opt_out", "human", f"prospect#{p.id}", approval="do_not_contact")
                    finally:
                        s.close()
                    st.rerun()

    with tab_add:
        with st.form("add_prospect_form"):
            company = st.text_input("Company *")
            website = st.text_input("Website")
            industry = st.text_input("Industry")
            country = st.text_input("Country")
            contact = st.text_input("Contact name")
            role = st.text_input("Role")
            email = st.text_input("Email")
            source = st.text_input("Source (e.g. company website, referral, inbound)", value="manual")
            interest = st.text_input("Product interest")
            notes = st.text_area("Notes / observed problem", height=120)
            do_submit = st.form_submit_button("Add Prospect")
            if do_submit:
                if not company:
                    st.error("Company is required.")
                else:
                    s = SessionLocal()
                    try:
                        comp = Company(name=company, website=website, industry=industry, country=country, notes=notes)
                        s.add(comp)
                        s.commit()
                        s.refresh(comp)
                        pr = Prospect(
                            company_id=comp.id, name=contact, role=role, email=email,
                            source=source, product_interest=interest, notes=notes,
                        )
                        s.add(pr)
                        s.commit()
                        audit.log("add_prospect", "human", f"{company}")
                        st.success(f"Prospect added for {company}.")
                    finally:
                        s.close()


def page_products():
    st.title("📦 Product Catalog")
    tab_cat, tab_add = st.tabs(["🗂️ Catalog", "➕ Add Product"])

    with tab_cat:
        session = SessionLocal()
        try:
            products = session.query(Product).order_by(Product.id.desc()).all()
        finally:
            session.close()

        if not products:
            st.info("No products yet. Add your first product in the 'Add Product' tab.")

        for prod in products:
            with st.expander(f"#{prod.id} · {prod.name} · {prod.status}"):
                st.markdown(f"**Problem solved:** {prod.problem_solved or '—'}")
                st.markdown(f"**Target customer:** {prod.target_customer or '—'}  |  **Industry:** {prod.industry or '—'}")
                st.markdown(f"**Price:** {prod.price or '—'}")
                st.write(prod.description or "")

    with tab_add:
        with st.form("add_product_form"):
            name = st.text_input("Product name *")
            description = st.text_area("Description", height=100)
            problem = st.text_area("Problem solved", height=80)
            target = st.text_input("Target customer")
            industry = st.text_input("Industry")
            features = st.text_area("Features", height=80)
            benefits = st.text_area("Benefits", height=80)
            price = st.text_input("Price")
            demo_url = st.text_input("Demo URL")
            portfolio_url = st.text_input("Portfolio URL")
            integrations = st.text_input("Supported integrations")
            keywords = st.text_input("Keywords (comma separated)")
            icp = st.text_area("Ideal customer profile", height=80)
            do_submit = st.form_submit_button("Add Product")
            if do_submit:
                if not name:
                    st.error("Product name is required.")
                else:
                    s = SessionLocal()
                    try:
                        prod = Product(
                            name=name, description=description, problem_solved=problem,
                            target_customer=target, industry=industry, features=features,
                            benefits=benefits, price=price, demo_url=demo_url,
                            portfolio_url=portfolio_url, integrations=integrations,
                            keywords=keywords, ideal_customer_profile=icp,
                        )
                        s.add(prod)
                        s.commit()
                        audit.log("add_product", "human", name)
                        st.success(f"Product '{name}' added.")
                    finally:
                        s.close()


def page_settings():
    st.title("⚙️ Settings")
    t1, t2, t3, t4 = st.tabs(["👤 Profile", "🎯 Skills & Red Flags", "🤖 AI Provider", "🚧 Guardrails"])

    with t1:
        prof = get_profile_config()
        name = st.text_input("Name", prof.get("name", ""))
        position = st.text_input("Position", prof.get("position", ""))
        skills = st.text_input("Skills (comma separated)", ", ".join(prof.get("skills", [])))
        portfolio = st.text_input("Portfolio URL", prof.get("portfolio_url", ""))
        github = st.text_input("GitHub URL", prof.get("github_url", ""))
        if st.button("Save profile"):
            data = {
                "name": name,
                "position": position,
                "skills": [x.strip() for x in skills.split(",") if x.strip()],
                "portfolio_url": portfolio,
                "github_url": github,
                "case_studies": prof.get("case_studies", []),
            }
            (CONFIG_DIR / "profile.json").write_text(json.dumps(data, indent=2))
            _load_json.cache_clear()
            audit.log("update_settings", "human", "profile")
            st.success("Profile saved.")

    with t2:
        cats = get_categories_config()
        skills_text = st.text_area("Matching skills (one per line)", "\n".join(cats.get("skills", [])), height=250)
        redflags_text = st.text_area("Scam red flags (one per line)", "\n".join(cats.get("red_flags", [])), height=150)
        if st.button("Save skills & red flags"):
            data = {
                "priority_categories": cats.get("priority_categories", []),
                "skills": [l.strip() for l in skills_text.splitlines() if l.strip()],
                "red_flags": [l.strip() for l in redflags_text.splitlines() if l.strip()],
            }
            (CONFIG_DIR / "categories.json").write_text(json.dumps(data, indent=2))
            _load_json.cache_clear()
            audit.log("update_settings", "human", "categories")
            st.success("Saved.")

    with t3:
        current = os.getenv("AI_PROVIDER", "mock")
        provider = st.selectbox("AI provider", ["mock", "ollama"], index=["mock", "ollama"].index(current) if current in ["mock", "ollama"] else 0)
        model = st.text_input("Ollama model", value=os.getenv("OLLAMA_MODEL", "llama3"))
        if st.button("Save AI settings"):
            update_env_key("AI_PROVIDER", provider)
            update_env_key("OLLAMA_MODEL", model)
            audit.log("update_settings", "human", "ai_provider")
            st.success("Saved. Restart the dashboard to apply.")

    with t4:
        g = get_guardrails_config()
        daily_outreach = st.number_input("Max outreach messages per day", 1, 100, int(g.get("daily_outreach_limit", 10)))
        daily_apps = st.number_input("Max applications per day", 1, 100, int(g.get("daily_application_limit", 15)))
        followup_max = st.number_input("Max follow-ups per prospect", 0, 10, int(g.get("followup_max", 3)))
        cooldown = st.number_input("Cooldown days after no response", 1, 90, int(g.get("cooldown_days", 7)))
        if st.button("Save guardrails"):
            data = {
                "daily_outreach_limit": int(daily_outreach),
                "daily_application_limit": int(daily_apps),
                "followup_max": int(followup_max),
                "cooldown_days": int(cooldown),
            }
            (CONFIG_DIR / "guardrails.json").write_text(json.dumps(data, indent=2))
            _load_json.cache_clear()
            audit.log("update_settings", "human", "guardrails")
            st.success("Guardrails saved.")


def page_audit():
    st.title("📜 Audit Log")
    path = LOGS_DIR / "audit.log"
    if not path.exists():
        st.info("No audit entries yet.")
        return
    lines = [l for l in path.read_text().strip().splitlines() if l.strip()][-200:]
    rows = [json.loads(l) for l in lines]
    rows.reverse()
    st.dataframe(rows)


st.sidebar.image("website/assets/logo.png", width=64)
st.sidebar.title("RevenueForge")
st.sidebar.caption("Human-in-the-loop revenue automation")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Command Center", "💼 Job Agent", "🎯 Sales Agent", "📨 Outreach Engine", "📦 Products", "⚙️ Settings", "📜 Audit Log"],
)

if page == "📊 Command Center":
    page_overview()
elif page == "💼 Job Agent":
    page_jobs()
elif page == "🎯 Sales Agent":
    page_sales()
elif page == "📨 Outreach Engine":
    from app.ui import outreach_ui
    outreach_ui.page_outreach()
elif page == "📦 Products":
    page_products()
elif page == "⚙️ Settings":
    page_settings()
elif page == "📜 Audit Log":
    page_audit()
