import argparse
import sys

from app.core.db import Base, engine, SessionLocal
from app.core.models import Job
from app.core.scoring import analyze_job
from app.core.proposals import generate_proposal


def init_db(args):
    Base.metadata.create_all(bind=engine)
    print("Database initialized at data/agent.db")


def _read_description(args) -> str:
    if getattr(args, "description", None):
        return args.description

    if getattr(args, "description_file", None):
        with open(args.description_file, "r", encoding="utf-8") as handle:
            return handle.read()

    if not sys.stdin.isatty():
        return sys.stdin.read()

    raise SystemExit("Provide --description or --description-file, or pipe text via stdin.")


def add_job(args):
    description = _read_description(args)

    job = Job(
        title=args.title,
        platform=args.platform,
        source=args.source,
        url=args.url,
        client=args.client,
        description=description,
        budget_text=args.budget,
        deadline=args.deadline,
        required_skills=args.required_skills,
    )

    session = SessionLocal()

    try:
        session.add(job)
        session.commit()
        session.refresh(job)
        print(f"Added job id={job.id}: {job.title}")
    finally:
        session.close()


def print_score(job: Job):
    print("=" * 80)
    print(f"ID: {job.id}")
    print(f"Title: {job.title}")
    print(f"Platform: {job.platform}")
    print(f"Source: {job.source}")
    print(f"URL: {job.url or 'No URL'}")
    print(f"Recommendation: {job.recommendation}")
    print(f"Opportunity score: {job.opportunity_score:.1f}/100")
    print(f"Technical fit: {job.technical_fit:.1f}")
    print(f"Budget score: {job.budget_score:.1f}")
    print(f"Clarity score: {job.clarity_score:.1f}")
    print(f"Client quality: {job.client_quality:.1f}")
    print(f"Competition score: {job.competition_score:.1f}")
    print(f"Urgency score: {job.urgency_score:.1f}")
    print(f"Long-term score: {job.long_term_score:.1f}")
    print(f"Recurring score: {job.recurring_score:.1f}")
    print(f"Scam risk: {job.scam_risk:.1f}")
    print("-" * 80)
    print("Reason:")
    print(job.reason)
    print("-" * 80)
    print("Proposal strategy:")
    print(job.proposal_strategy)
    print("=" * 80)


def score_job(args):
    session = SessionLocal()

    try:
        job = session.get(Job, args.job_id)

        if not job:
            raise SystemExit(f"Job id {args.job_id} not found.")

        analysis = analyze_job(job)

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

        job.proposal_draft = generate_proposal(job, analysis)
        job.status = "scored"

        session.commit()

        print_score(job)
    finally:
        session.close()


def list_jobs(args):
    session = SessionLocal()

    try:
        jobs = session.query(Job).order_by(Job.id.desc()).all()

        if not jobs:
            print("No jobs found.")
            return

        print("ID\tSCORE\tRECOMMENDATION\tTITLE")
        print("-" * 80)

        for job in jobs:
            print(
                f"{job.id}\t"
                f"{job.opportunity_score:.1f}\t"
                f"{job.recommendation}\t"
                f"{job.title[:60]}"
            )
    finally:
        session.close()


def show_job(args):
    session = SessionLocal()

    try:
        job = session.get(Job, args.job_id)

        if not job:
            raise SystemExit(f"Job id {args.job_id} not found.")

        print("=" * 80)
        print(f"ID: {job.id}")
        print(f"Created at: {job.created_at}")
        print(f"Title: {job.title}")
        print(f"Platform: {job.platform}")
        print(f"Source: {job.source}")
        print(f"URL: {job.url or 'No URL'}")
        print(f"Client: {job.client or 'Unknown'}")
        print(f"Budget: {job.budget_text or 'Unknown'}")
        print(f"Deadline: {job.deadline or 'Unknown'}")
        print(f"Status: {job.status}")
        print(f"Approved: {job.approved}")
        print(f"Submitted: {job.submitted}")
        print("-" * 80)
        print("Description:")
        print(job.description)
        print("-" * 80)
        print("Required skills:")
        print(job.required_skills or "Unknown")
        print("-" * 80)
        print_score(job)
        print("-" * 80)
        print("Proposal draft:")
        print(job.proposal_draft or "No proposal draft yet. Run score-job first.")
        print("=" * 80)
    finally:
        session.close()


def approve_job(args):
    session = SessionLocal()

    try:
        job = session.get(Job, args.job_id)

        if not job:
            raise SystemExit(f"Job id {args.job_id} not found.")

        if not job.proposal_draft:
            raise SystemExit("Run score-job first to generate a proposal.")

        job.approved = True
        job.status = "approved"

        session.commit()

        print("=" * 80)
        print("APPROVED")
        print("If the platform prohibits automation, submit manually through the official UI/API.")
        print(f"URL: {job.url or 'No URL stored'}")
        print("=" * 80)
        print(job.proposal_draft)
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        prog="revenue_forge",
        description="RevenueForge CLI",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Initialize SQLite database")
    init_parser.set_defaults(func=init_db)

    add_parser = subparsers.add_parser("add-job", help="Add a job opportunity")
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--platform", default="manual")
    add_parser.add_argument("--source", default="manual")
    add_parser.add_argument("--url", default="")
    add_parser.add_argument("--client", default="")
    add_parser.add_argument("--description", default="")
    add_parser.add_argument("--description-file", default="")
    add_parser.add_argument("--budget", default="")
    add_parser.add_argument("--deadline", default="")
    add_parser.add_argument("--required-skills", default="")
    add_parser.set_defaults(func=add_job)

    score_parser = subparsers.add_parser("score-job", help="Score a job")
    score_parser.add_argument("job_id", type=int)
    score_parser.set_defaults(func=score_job)

    list_parser = subparsers.add_parser("list-jobs", help="List jobs")
    list_parser.set_defaults(func=list_jobs)

    show_parser = subparsers.add_parser("show-job", help="Show job details")
    show_parser.add_argument("job_id", type=int)
    show_parser.set_defaults(func=show_job)

    approve_parser = subparsers.add_parser("approve-job", help="Approve job application")
    approve_parser.add_argument("job_id", type=int)
    approve_parser.set_defaults(func=approve_job)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
