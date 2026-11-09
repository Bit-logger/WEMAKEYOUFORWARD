"""Supabase-backed jobs, employer applicant pipeline, admin reports and job orders.

Replaces the old in-memory lists in data.py. Run supabase/migration_002_jobs.sql once in the
Supabase SQL editor before starting the app (fresh installs: supabase/schema.sql has everything).
"""
import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from flask import g, has_app_context

from db import get_db

log = logging.getLogger(__name__)

STAGES = ["New", "Shortlisted", "Interview", "Hired"]
# Employer pipeline stage -> what the job seeker sees in "My Applications"
STAGE_TO_STATUS = {"New": "Applied", "Shortlisted": "Shortlisted", "Interview": "Interview"}
DEMO_COMPANY = "Northlane Digital"   # seeded demo jobs from this company belong to the demo employer

JOB_COLUMNS = ("employer_id", "is_demo", "title", "company", "company_initials", "company_color", "location",
               "type", "mode", "experience", "industry", "salary_min", "salary_max", "tags", "closing_date",
               "featured", "urgent", "status", "views", "about_role", "responsibilities", "requirements",
               "benefits", "about_company", "package")


def _now():
    return datetime.now(timezone.utc)


def _parse_ts(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return _now()


def _as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        import json
        try:
            return json.loads(value)
        except ValueError:
            return []
    return []


# ------------------------------------------------------------------ jobs --
def _shape(row, counts):
    job = dict(row)
    for key in ("tags", "responsibilities", "requirements", "benefits"):
        job[key] = _as_list(job.get(key))
    job["posted_days_ago"] = max(0, (_now() - _parse_ts(job.get("created_at"))).days)
    job["applications_count"] = counts.get(job["id"], 0)
    job["views"] = job.get("views") or 0
    job["salary_min"] = int(job.get("salary_min") or 0)
    job["salary_max"] = int(job.get("salary_max") or 0)
    job["closing_date"] = str(job.get("closing_date") or "")
    job["featured"] = bool(job.get("featured"))
    job["urgent"] = bool(job.get("urgent"))
    return job


def _application_counts():
    rows = get_db().table("applications").select("job_id").execute().data or []
    return Counter(r["job_id"] for r in rows)


def all_jobs():
    """Every job (all statuses), newest first. Cached for the current request."""
    if has_app_context() and "nx_jobs" in g:
        return g.nx_jobs
    try:
        rows = get_db().table("jobs").select("*").order("created_at", desc=True).execute().data or []
        counts = _application_counts()
        jobs = [_shape(r, counts) for r in rows]
    except Exception as exc:
        log.warning("Supabase jobs table query failed (%s); falling back to seed jobs.", exc)
        import data
        jobs = data.build_seed_jobs()
    if has_app_context():
        g.nx_jobs = jobs
    return jobs


def _invalidate():
    if has_app_context():
        g.pop("nx_jobs", None)


def live_jobs():
    return [j for j in all_jobs() if j["status"] == "Approved"]


def get_job(job_id):
    try:
        job_id = int(job_id)
    except (TypeError, ValueError):
        return None
    return next((j for j in all_jobs() if j["id"] == job_id), None)


def _owns(employer, job):
    if job.get("employer_id") == employer["id"]:
        return True
    return bool(employer.get("is_demo") and job.get("is_demo") and job.get("company") == DEMO_COMPANY)


def jobs_for_employer(employer):
    return [j for j in all_jobs() if _owns(employer, j)]


def create_job(fields):
    values = {k: v for k, v in fields.items() if k in JOB_COLUMNS}
    row = get_db().table("jobs").insert(values).execute().data[0]
    _invalidate()
    return row["id"]


def update_job(job_id, **fields):
    values = {k: v for k, v in fields.items() if k in JOB_COLUMNS}
    if values:
        values["updated_at"] = _now().isoformat()
        get_db().table("jobs").update(values).eq("id", job_id).execute()
        _invalidate()


def add_view(job_id):
    job = get_job(job_id)
    if job:
        job["views"] = (job.get("views") or 0) + 1
        try:
            get_db().table("jobs").update({"views": job["views"]}).eq("id", job["id"]).execute()
        except Exception:
            pass


def latest_draft(employer):
    drafts = [j for j in all_jobs() if j.get("employer_id") == employer["id"] and j["status"] == "Draft"]
    return drafts[0] if drafts else None


# ------------------------------------------------- employer applicants --
def candidates_for_employer(employer):
    """Real applications to this employer's jobs, shaped for the applicant board."""
    try:
        my_jobs = {j["id"]: j for j in jobs_for_employer(employer)}
        if not my_jobs:
            return []
        apps = (get_db().table("applications").select("*").in_("job_id", list(my_jobs))
                .order("applied_at", desc=True).execute().data or [])
        seeker_ids = list({a["seeker_id"] for a in apps})
        seekers, profiles = {}, {}
        if seeker_ids:
            for r in get_db().table("seekers").select("id,email,full_name").in_("id", seeker_ids).execute().data or []:
                seekers[r["id"]] = r
            for r in get_db().table("seeker_profiles").select("*").in_("seeker_id", seeker_ids).execute().data or []:
                profiles[r["seeker_id"]] = r
        out = []
        for a in apps:
            job, person, prof = my_jobs[a["job_id"]], seekers.get(a["seeker_id"], {}), profiles.get(a["seeker_id"], {})
            name = (person.get("full_name") or "").strip() or (person.get("email") or "Candidate").split("@")[0]
            skills = _as_list(prof.get("skills"))
            exp_rows = _as_list(prof.get("experience"))
            out.append({
                "id": a["id"],
                "job_id": job["id"],
                "job_title": job["title"],
                "name": name,
                "email": person.get("email", ""),
                "title": prof.get("headline") or job["title"],
                "location": prof.get("location", ""),
                "experience": f"{len(exp_rows)} role{'s' if len(exp_rows) != 1 else ''} listed" if exp_rows
                              else ("No experience yet" if prof.get("no_experience") else job["experience"]),
                "skills": skills[:6] or job["tags"][:3],
                "applied_date": str(a.get("applied_at") or "")[:10],
                "stage": a.get("stage") or "New",
                "cover_note": a.get("cover_note", ""),
                "avatar_initials": "".join(p[0] for p in name.split()[:2]).upper() or "?",
            })
        return out
    except Exception as exc:
        log.warning("candidates_for_employer failed (%s); returning empty list.", exc)
        return []


def move_stage(employer, application_id, new_stage):
    if new_stage not in STAGES:
        return False
    rows = get_db().table("applications").select("*").eq("id", application_id).limit(1).execute().data or []
    if not rows:
        return False
    job = get_job(rows[0]["job_id"])
    if not job or not _owns(employer, job):
        return False
    values = {"stage": new_stage, "updated_at": _now().isoformat()}
    if new_stage in STAGE_TO_STATUS:
        values["status"] = STAGE_TO_STATUS[new_stage]
    get_db().table("applications").update(values).eq("id", application_id).execute()
    return True


# --------------------------------------------------------------- orders --
def record_order(employer_id, job_id, package):
    get_db().table("job_orders").insert({"employer_id": employer_id, "job_id": job_id, "package": package["id"],
                                         "amount": package["price"]}).execute()


# -------------------------------------------------------- admin / stats --
def platform_stats():
    try:
        db = get_db()
        seekers = len(db.table("seekers").select("id").execute().data or [])
        employers = len(db.table("employers").select("id").execute().data or [])
        month_start = date.today().replace(day=1).isoformat()
        orders = db.table("job_orders").select("amount,created_at").gte("created_at", month_start).execute().data or []
        return {"total_users": seekers + employers, "employers": employers,
                "revenue_month": int(sum(float(o.get("amount") or 0) for o in orders))}
    except Exception as exc:
        log.warning("platform_stats query failed (%s); using default values.", exc)
        return {"total_users": 4, "employers": 2, "revenue_month": 0}


def reports():
    try:
        return get_db().table("admin_reports").select("*").order("id").execute().data or []
    except Exception as exc:
        log.warning("admin_reports query failed (%s); using seed reports.", exc)
        import data
        return data.DEMO_REPORTS


def resolve_report(report_id):
    rows = get_db().table("admin_reports").update({"status": "Resolved"}).eq("id", report_id).execute().data
    return bool(rows)


# --------------------------------------------------------------- seeding --
def seed_demo_jobs(build_jobs, demo_reports):
    """First run only: copy the sample job board into Supabase so job search has test data."""
    db = get_db()
    if db.table("jobs").select("id").eq("is_demo", True).limit(1).execute().data:
        return 0
    rows = []
    for job in build_jobs():
        row = {k: job[k] for k in JOB_COLUMNS if k in job}
        row["id"] = job["id"]                      # keep the old ids so existing saved jobs / applications still match
        row["is_demo"] = True
        row["employer_id"] = None
        row["views"] = job.get("views", 0)
        row["created_at"] = (_now() - timedelta(days=job["posted_days_ago"])).isoformat()
        rows.append(row)
    db.table("jobs").insert(rows).execute()
    if not db.table("admin_reports").select("id").limit(1).execute().data:
        db.table("admin_reports").insert(demo_reports).execute()
    _invalidate()
    return len(rows)
