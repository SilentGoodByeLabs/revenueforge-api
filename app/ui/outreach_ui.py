import urllib.parse

import streamlit as st

from app.core.db import SessionLocal
from app.core.models import OutreachMessage, Prospect
from app.core.config import get_guardrails_config
from app.agents.sales_agent.outreach import draft_for_prospect, today_outreach_count
from app.core import audit


def page_outreach():
    st.title("📨 Outreach Engine")
    st.caption("Human-voice outreach. Nothing is sent automatically - you approve, then send manually.")

    g = get_guardrails_config()
    limit = int(g.get("daily_outreach_limit", 10))
    used = today_outreach_count()
    st.metric("Outreach today", f"{used} / {limit}")

    tab_draft, tab_outbox = st.tabs(["✍️ Draft New", "📥 Approval Outbox"])

    with tab_draft:
        session = SessionLocal()
        try:
            prospects = session.query(Prospect).order_by(Prospect.id.desc()).all()
        finally:
            session.close()

        active = [p for p in prospects if not p.opted_out and p.status != "do_not_contact"]

        if not active:
            st.info("No active prospects. Add prospects in the Sales Agent page first.")
        else:
            options = {f"#{p.id} {p.name or 'Unknown'} (company #{p.company_id})": p.id for p in active}
            choice = st.selectbox("Prospect", list(options.keys()))
            if st.button("🔍 Analyze & Draft Outreach"):
                result = draft_for_prospect(options[choice])
                if result["ok"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.warning(result["message"])

    with tab_outbox:
        session = SessionLocal()
        try:
            msgs = session.query(OutreachMessage).order_by(OutreachMessage.id.desc()).all()
        finally:
            session.close()

        if not msgs:
            st.info("No outreach drafts yet.")

        for m in msgs:
            with st.expander(f"#{m.id} · prospect #{m.prospect_id} · fit {m.fit_score:.0f} · {m.status}"):
                st.markdown(f"**Subject:** {m.subject}")
                st.text_area("Body", value=m.body or "", height=220, key=f"ob_{m.id}")

                if m.status == "draft":
                    b1, b2 = st.columns(2)
                    if b1.button("✅ Approve", key=f"oa_{m.id}"):
                        s = SessionLocal()
                        try:
                            mm = s.get(OutreachMessage, m.id)
                            mm.status = "approved"
                            s.commit()
                            audit.log("approve_outreach", "human", f"msg#{m.id}", approval="approved")
                        finally:
                            s.close()
                        st.rerun()
                    if b2.button("❌ Reject", key=f"orj_{m.id}"):
                        s = SessionLocal()
                        try:
                            mm = s.get(OutreachMessage, m.id)
                            mm.status = "rejected"
                            s.commit()
                            audit.log("reject_outreach", "human", f"msg#{m.id}", approval="rejected")
                        finally:
                            s.close()
                        st.rerun()

                elif m.status == "approved":
                    s = SessionLocal()
                    try:
                        p = s.get(Prospect, m.prospect_id)
                        email = p.email if p else ""
                    finally:
                        s.close()

                    if email:
                        href = "mailto:" + email + "?subject=" + urllib.parse.quote(m.subject or "") + "&body=" + urllib.parse.quote(m.body or "")
                        st.markdown(f"[📧 Open in your email app and send]({href})")
                    else:
                        st.warning("No email on record. Copy the body and contact via their official site.")

                    if st.button("📤 Mark Sent", key=f"os_{m.id}"):
                        s = SessionLocal()
                        try:
                            mm = s.get(OutreachMessage, m.id)
                            mm.status = "sent"
                            mm.sent_at = datetime.now(timezone.utc)
                            s.commit()
                            audit.log("mark_outreach_sent", "human", f"msg#{m.id}")
                        finally:
                            s.close()
                        st.rerun()
