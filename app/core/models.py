from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.core.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    title = Column(String, nullable=False)
    platform = Column(String, default="manual")
    source = Column(String, default="manual")
    url = Column(String, nullable=True)
    client = Column(String, nullable=True)

    description = Column(Text, nullable=False)
    budget_text = Column(String, nullable=True)
    deadline = Column(String, nullable=True)
    required_skills = Column(Text, nullable=True)

    status = Column(String, default="new")

    technical_fit = Column(Float, default=0.0)
    client_quality = Column(Float, default=0.0)
    budget_score = Column(Float, default=0.0)
    clarity_score = Column(Float, default=0.0)
    competition_score = Column(Float, default=0.0)
    urgency_score = Column(Float, default=0.0)
    long_term_score = Column(Float, default=0.0)
    recurring_score = Column(Float, default=0.0)
    scam_risk = Column(Float, default=0.0)

    opportunity_score = Column(Float, default=0.0)
    recommendation = Column(String, default="REVIEW")
    reason = Column(Text, nullable=True)
    proposal_strategy = Column(Text, nullable=True)
    proposal_draft = Column(Text, nullable=True)

    approved = Column(Boolean, default=False)
    submitted = Column(Boolean, default=False)
    matched_product_id = Column(Integer, nullable=True)
    product_fit_score = Column(Float, default=0.0)
    product_match_reason = Column(Text, nullable=True)
    sales_angle = Column(Text, nullable=True)
    submitted_url = Column(String, nullable=True)
    client_reply = Column(Text, nullable=True)
    next_followup_date = Column(String, nullable=True)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    problem_solved = Column(Text, nullable=True)
    target_customer = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    features = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    price = Column(String, nullable=True)
    demo_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    case_study = Column(Text, nullable=True)
    integrations = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    ideal_customer_profile = Column(Text, nullable=True)
    deliverables = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    technologies = Column(Text, nullable=True)
    use_cases = Column(Text, nullable=True)
    sales_arguments = Column(Text, nullable=True)
    objections = Column(Text, nullable=True)
    objection_responses = Column(Text, nullable=True)
    status = Column(String, default="active")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    country = Column(String, nullable=True)
    notes = Column(Text, nullable=True)


class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company_id = Column(Integer, nullable=True)
    name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    email = Column(String, nullable=True)
    source = Column(String, default="manual")

    status = Column(String, default="new")
    product_interest = Column(String, nullable=True)
    fit_score = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    opted_out = Column(Boolean, default=False)


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    prospect_id = Column(Integer, nullable=False)
    product_id = Column(Integer, nullable=True)
    channel = Column(String, default="email")

    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    fit_score = Column(Float, default=0.0)

    status = Column(String, default="draft")
    sent_at = Column(DateTime, nullable=True)


class FollowUp(Base):
    __tablename__ = "followups"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    prospect_id = Column(Integer, nullable=False)
    step = Column(Integer, default=1)
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="planned")
    draft = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)


class Deal(Base):
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    title = Column(String, nullable=False)
    value = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    stage = Column(String, default="lead")
    source_type = Column(String, nullable=True)
    source_id = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    won_at = Column(DateTime, nullable=True)
    payment_status = Column(String, default="UNPAID")
    paid_at = Column(DateTime, nullable=True)


class InviteCode(Base):
    __tablename__ = "invite_codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    used_by_email = Column(String, nullable=True)
    used_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)


class ClientProject(Base):
    __tablename__ = "client_projects"
    id = Column(Integer, primary_key=True, index=True)
    client_email = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    status = Column(String, default="planning")  # planning, in_progress, review, delivered
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    milestones = Column(Text, nullable=True)  # JSON array
    deliverables = Column(Text, nullable=True)  # JSON array


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    plan_label = Column(String, nullable=False)
    modules = Column(Text, nullable=True)
    volume = Column(String, nullable=True)
    price_monthly = Column(Float, default=0.0)
    status = Column(String, default="active")
    paystack_ref = Column(String, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    renews_at = Column(DateTime, nullable=True)

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    phone = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    verify_code = Column(String, nullable=True)
    role = Column(String, default="client")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AuditUse(Base):
    __tablename__ = "audit_uses"
    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, index=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SubscriberProduct(Base):
    __tablename__ = "subscriber_products"
    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True)
    name = Column(String)
    price = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
