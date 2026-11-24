import os
import secrets
from datetime import date, timedelta

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, session, jsonify, request, redirect, url_for, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

import data
import db
import job_store
import employer_auth
import seeker_auth
import seeker_portal
import chatbot
import excel_service
import security
import seeker_store as store
from employer_auth import current_company, current_employer, employer_required
from seeker_auth import current_seeker, seeker_required

app = Flask(__name__)

# --- Security / session config -------------------------------------------------
# Set SECRET_KEY in the environment for production. Without it a random key is used,
# which is fine locally but signs everyone out whenever the server restarts.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Set SESSION_COOKIE_SECURE=1 on any https deployment (render.yaml does this).
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
)
# Trust one proxy hop (Render, Heroku, nginx) so https URLs and client IPs are correct.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db.init_app(app)
security.install_security(app)

# First run: copy the sample job board into Supabase so job search has test data.
if app.config.get("SUPABASE_CONFIGURED"):
    with app.app_context():
        try:
            added = job_store.seed_demo_jobs(data.build_seed_jobs, data.DEMO_REPORTS)
            if added:
                app.logger.warning("Seeded %s sample jobs into Supabase.", added)
        except Exception as exc:  # table missing -> tell the developer what to run
            app.logger.error("Jobs table not ready (%s). Run supabase/migration_002_jobs.sql in Supabase.", exc)
app.register_blueprint(employer_auth.bp)
app.register_blueprint(seeker_auth.bp)
app.register_blueprint(seeker_portal.api_bp)
app.register_blueprint(chatbot.bp)


def current_role():
    return session.get("demo_role", "guest")


@app.context_processor
def inject_globals():
    employer = current_employer()
    seeker_row = None if employer else current_seeker()
    if employer:
        role = "employer"          # a real login always wins over the demo switcher
    elif seeker_row:
        role = "seeker"
    else:
        role = current_role()
        if role in ("employer", "seeker"):
            role = "guest"         # these views can no longer be faked
    return {
        "demo_role": role,
        "employer_user": employer,
        "employer_company": current_company(),
        "seeker_user": store.seeker_display(seeker_row) if seeker_row else None,
        "csrf_token": employer_auth.csrf_token,
        "saved_count": len(store.saved_job_ids(seeker_row["id"])) if seeker_row else 0,
    }


@app.template_filter("posted_label")
def posted_label(days):
    if days <= 0:
        return "Today"
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if request.path.startswith(("/employer", "/dashboard/employer", "/seeker", "/dashboard/seeker")):
        resp.headers["Cache-Control"] = "no-store"  # don't cache account pages (back button after logout)
    return resp


# -------------------------------------------------------- skip demo routes --
@app.route("/skip-seeker")
@app.route("/seeker/skip")
def skip_seeker():
    return redirect(url_for("seeker.skip"))


@app.route("/skip-employer")
@app.route("/employer/skip")
def skip_employer():
    return redirect(url_for("employer.skip"))


# ---------------------------------------------------------------- pages --
@app.route("/")
def index():
    live = data.live_jobs()
    featured_jobs = [j for j in live if j["featured"]][:6]
    categories = {}
    for j in live:
        categories.setdefault(j["industry"], 0)
        categories[j["industry"]] += 1
    return render_template("index.html", featured_jobs=featured_jobs, categories=categories,
                            salary_label=data.salary_label)


@app.route("/jobs")
def jobs():
    live_jobs = data.live_jobs()
    return render_template(
        "jobs.html",
        jobs_json=live_jobs,
        saved_ids=store.saved_job_ids(current_seeker()["id"]) if current_seeker() else [],
        applied_ids=list(store.applied_job_ids(current_seeker()["id"])) if current_seeker() else [],
        locations=data.LOCATIONS,
        industries=data.INDUSTRIES,
        job_types=data.JOB_TYPES,
        work_modes=data.WORK_MODES,
        experience_levels=data.EXPERIENCE_LEVELS,
        salary_label=data.salary_label,
    )


TOP_COMPANIES = [
    {"slug": "northlane-digital", "name": "Northlane Digital", "initials": "ND", "color": "#5D4FE0",
     "industry": "Technology", "location": "Melbourne, VIC", "employees": "250-500",
     "about": "A product engineering studio building web and mobile platforms for Australian brands."},
    {"slug": "harbourfield-health", "name": "Harbourfield Health", "initials": "HH", "color": "#2DD9B8",
     "industry": "Healthcare", "location": "Brisbane, QLD", "employees": "1,000+",
     "about": "A leading healthcare network delivering compassionate, community-focused patient care."},
    {"slug": "ferro-cole-construction", "name": "Ferro & Cole Construction", "initials": "FC", "color": "#0B1230",
     "industry": "Construction", "location": "Perth, WA", "employees": "500-1,000",
     "about": "Commercial and civil construction specialists delivering landmark projects nationwide."},
    {"slug": "bright-retail-co", "name": "Bright Retail Co.", "initials": "BR", "color": "#E0975D",
     "industry": "Retail", "location": "Adelaide, SA", "employees": "100-250",
     "about": "A fast-growing retail group with stores and online experiences across Australia."},
]


@app.route("/companies")
def companies():
    items = []
    for c in TOP_COMPANIES:
        count = sum(1 for j in data.live_jobs() if j["company"] == c["name"])
        items.append({**c, "open_roles": count})
    return render_template("companies.html", companies=items)


@app.route("/companies/<slug>")
def company_jobs(slug):
    company = next((c for c in TOP_COMPANIES if c["slug"] == slug), None)
    if not company:
        return render_template("404.html"), 404
    posted = [j for j in data.live_jobs() if j["company"] == company["name"]]
    return render_template("company_jobs.html", company=company, jobs=posted, salary_label=data.salary_label)


@app.route("/jobs/<int:job_id>")
def job_details(job_id):
    job = data.get_job(job_id)
    employer = current_employer()
    # Drafts / pending / rejected jobs are only visible to the employer who owns them.
    if not job or (job["status"] != "Approved" and not (employer and job_store._owns(employer, job))):
        return render_template("404.html"), 404
    if not (employer and job_store._owns(employer, job)):
        job_store.add_view(job_id)
    me = current_seeker()
    is_saved = has_applied = False
    percent, resume_info = 0, None
    if me:
        is_saved = job_id in store.saved_job_ids(me["id"])
        has_applied = job_id in store.applied_job_ids(me["id"])
        profile = store.get_profile(me["id"])
        percent = store.profile_completion(me, profile)[0]
        resume_info = store.get_resume(me["id"])
        if resume_info:
            resume_info["updated_label"] = store.format_date(resume_info["updated_at"])
    similar = [j for j in data.live_jobs() if j["industry"] == job["industry"] and j["id"] != job_id][:3]
    return render_template("job_details.html", job=job, is_saved=is_saved, has_applied=has_applied,
                           similar=similar, profile_percent=percent, resume_info=resume_info,
                           salary_label=data.salary_label)


@app.route("/dashboard/seeker")
@seeker_required
def seeker_dashboard():
    ctx = seeker_portal.portal_context()
    apps = seeker_portal._applications_view(ctx["row"]["id"])
    counts = {st: sum(1 for a in apps if a["status"] == st) for st in store.APPLICATION_STATUSES}
    saved = [j for j in (data.get_job(i) for i in store.saved_job_ids(ctx["row"]["id"])) if j]
    matching_alerts = seeker_portal.matching_alerts_for_seeker(ctx["row"]["id"])
    return render_template("seeker_dashboard.html", **ctx, applications=apps, status_counts=counts,
                           saved=saved, statuses=store.APPLICATION_STATUSES,
                           matching_alerts=matching_alerts,
                           resume_updated=store.format_date(ctx["resume"]["updated_at"]) if ctx["resume"] else "",
                           salary_label=data.salary_label)


@app.route("/dashboard/employer")
@employer_required
def employer_dashboard():
    employer = current_employer()
    my_jobs = sorted(data.jobs_for_employer(employer), key=lambda j: j["posted_days_ago"])
    live_jobs = [j for j in my_jobs if j["status"] == "Approved"]
    my_candidates = data.candidates_for_employer(employer)
    shortlisted = sum(1 for c in my_candidates if c["stage"] in ("Shortlisted", "Interview", "Hired"))
    recent_applicants = sorted(my_candidates, key=lambda c: c["applied_date"], reverse=True)[:5]
    return render_template(
        "employer_dashboard.html", company=current_company(), my_jobs=my_jobs,
        active_jobs=len(live_jobs),
        total_views=sum(j.get("views", 0) or 0 for j in my_jobs),
        total_apps=sum(j.get("applications_count", 0) or 0 for j in my_jobs),
        shortlisted=shortlisted, recent_applicants=recent_applicants)


@app.route("/post-job")
@employer_required
def post_job():
    return render_template("post_job.html", industries=data.INDUSTRIES, job_types=data.JOB_TYPES,
                            work_modes=data.WORK_MODES, experience_levels=data.EXPERIENCE_LEVELS,
                            locations=data.LOCATIONS)


@app.route("/pricing")
def pricing():
    return render_template("pricing.html", packages=data.PACKAGES)


@app.route("/checkout")
@employer_required
def checkout():
    package_id = request.args.get("package", "featured")
    package = next((p for p in data.PACKAGES if p["id"] == package_id), data.PACKAGES[1])
    latest = job_store.latest_draft(current_employer())
    draft = {"job_id": latest["id"], "title": latest["title"]} if latest else {}
    return render_template("checkout.html", package=package, draft=draft)


@app.route("/applicants")
@employer_required
def applicants():
    mine = data.candidates_for_employer(current_employer())
    grouped = {s: [c for c in mine if c["stage"] == s] for s in data.STAGES}
    return render_template("applicants.html", grouped=grouped, stages=data.STAGES)


@app.route("/admin")
def admin():
    every_job = [j for j in data.all_jobs() if j["status"] != "Draft"]
    live_jobs = [j for j in every_job if j["status"] == "Approved"]
    pending_jobs = [j for j in every_job if j["status"] == "Pending"]
    rejected_jobs = [j for j in every_job if j["status"] == "Rejected"]
    stats = job_store.platform_stats()
    seekers = []
    employers = []
    try:
        seekers = db.get_db().table("seekers").select("id, email, full_name, plan, created_at").order("created_at", desc=True).limit(20).execute().data or []
        employers = db.get_db().table("employers").select("id, email, created_at, companies(name, registered_name)").order("created_at", desc=True).limit(20).execute().data or []
    except Exception:
        pass
    return render_template("admin.html", stats=stats, live_jobs=live_jobs,
                            pending_jobs=pending_jobs, rejected_jobs=rejected_jobs,
                            all_jobs=every_job, reports=job_store.reports(), revenue=stats["revenue_month"],
                            seekers=seekers, employers=employers)


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Endpoint not found."}), 404
    return render_template("404.html"), 404


# --------------------------------------------------------------- API ----
@app.post("/api/demo-role")
def api_demo_role():
    role = (request.json or {}).get("role", "guest")
    if role not in ("guest", "seeker", "admin", "employer"):
        return jsonify({"ok": False}), 400
    # Testing phase: allow instant role switching without forcing login credentials
    if role == "seeker":
        row = store.get_seeker_by_email(seeker_auth.DEMO_EMAIL)
        if not row:
            sid = seeker_auth.seed_demo("SeekerDemo123!")
            row = store.get_seeker(sid)
        if row:
            session.clear()
            session["seeker_id"] = row["id"]
            session["demo_role"] = "seeker"
            session.permanent = True
            return jsonify({"ok": True, "role": "seeker", "redirect": url_for("seeker_dashboard")})

    elif role == "employer":
        emp = db.get_employer_by_email(employer_auth.DEMO_EMAIL)
        if not emp or not emp.get("onboarding_complete"):
            eid = employer_auth.seed_demo("EmployerDemo123!")
            emp = db.get_employer(eid)
        if emp:
            session.clear()
            session["employer_id"] = emp["id"]
            session["demo_role"] = "employer"
            session.permanent = True
            return jsonify({"ok": True, "role": "employer", "redirect": url_for("employer_dashboard")})

    elif role == "guest":
        session.clear()
        session["demo_role"] = "guest"
        return jsonify({"ok": True, "role": "guest", "redirect": url_for("index")})

    elif role == "admin":
        session["demo_role"] = "admin"
        return jsonify({"ok": True, "role": "admin", "redirect": url_for("admin")})
    return jsonify({"ok": True, "role": role})


@app.post("/api/post-job")
@employer_required
def api_post_job():
    payload = request.json or {}
    employer, company = current_employer(), current_company()
    def money(key, default):
        try:
            return max(0, min(10_000_000, int(float(payload.get(key) or default))))
        except (TypeError, ValueError):
            return default

    def pick(key, options):
        value = payload.get(key)
        return value if value in options else options[0]

    title = (str(payload.get("title") or "").strip() or "Untitled role")[:120]
    salary_min, salary_max = money("salary_min", 60000), money("salary_max", 90000)
    if salary_max < salary_min:
        salary_min, salary_max = salary_max, salary_min
    closing = str(payload.get("closing_date") or "")[:10]
    try:
        closing = date.fromisoformat(closing).isoformat()
    except ValueError:
        closing = (date.today() + timedelta(days=30)).isoformat()
    experience = pick("experience", data.EXPERIENCE_LEVELS)
    job_id = job_store.create_job({
        "employer_id": employer["id"],
        "is_demo": False,
        "title": title,
        "company": company["name"],
        "company_initials": company["initials"],
        "company_color": company["color"],
        "location": pick("location", data.LOCATIONS),
        "type": pick("type", data.JOB_TYPES),
        "mode": pick("mode", data.WORK_MODES),
        "experience": experience,
        "industry": pick("industry", data.INDUSTRIES),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "tags": [t.strip()[:40] for t in str(payload.get("skills", "")).split(",") if t.strip()][:6] or ["General"],
        "closing_date": closing,
        "featured": False,
        "urgent": False,
        "status": "Draft",
        "views": 0,
        "about_role": (str(payload.get("description") or "").strip() or "Description coming soon.")[:5000],
        "responsibilities": ["Deliver against role objectives", "Work closely with the team"],
        "requirements": [f"Experience level: {experience}"],
        "benefits": ["Flexible working arrangements"],
        "about_company": f"{company['name']} is hiring through JOBFLEX.",
    })
    return jsonify({"ok": True, "job_id": job_id})


@app.post("/api/checkout")
@employer_required
def api_checkout():
    payload = request.json or {}
    employer = current_employer()
    job = job_store.latest_draft(employer)
    package = next((p for p in data.PACKAGES if p["id"] == payload.get("package")), data.PACKAGES[1])
    if not job:
        return jsonify({"ok": False, "error": "No draft job to publish."}), 404
    job_store.update_job(job["id"], status="Approved", package=package["id"],
                         featured=package["id"] in ("featured", "premium"),
                         urgent=package["id"] in ("urgent", "premium"))
    job_store.record_order(employer["id"], job["id"], package)
    return jsonify({"ok": True, "job_id": job["id"]})


@app.post("/api/applicants/<int:candidate_id>/stage")
@employer_required
def api_move_stage(candidate_id):
    new_stage = (request.json or {}).get("stage")
    if job_store.move_stage(current_employer(), candidate_id, new_stage):
        return jsonify({"ok": True, "stage": new_stage})
    return jsonify({"ok": False}), 404


@app.post("/api/admin/jobs/<int:job_id>/moderate")
def api_moderate(job_id):
    if current_role() != "admin":
        return jsonify({"ok": False, "error": "Admins only."}), 403
    action = (request.json or {}).get("action")
    job = data.get_job(job_id)
    if not job:
        return jsonify({"ok": False}), 404
    mapping = {"approve": "Approved", "reject": "Rejected", "review": "Review", "suspend": "Suspended"}
    if action in mapping:
        job_store.update_job(job_id, status=mapping[action])
        return jsonify({"ok": True, "status": mapping[action]})
    return jsonify({"ok": False}), 400


@app.post("/api/admin/reports/<int:report_id>/resolve")
def api_resolve_report(report_id):
    if current_role() != "admin":
        return jsonify({"ok": False, "error": "Admins only."}), 403
    if job_store.resolve_report(report_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/interview")
@app.route("/interview-practice")
def top_interview_redirect():
    return redirect(url_for("seeker.interview_practice"))


@app.route("/resume")
def top_resume_redirect():
    return redirect(url_for("seeker.resume"))


@app.route("/alerts")
def top_alerts_redirect():
    return redirect(url_for("seeker.alerts"))


# --- Bulk Job Upload Through Excel --------------------------------------------
@app.get("/employer/jobs/template")
@employer_required
def download_job_template():
    """Download the official JOBFLEX job upload template in Excel (.xlsx) format."""
    buf = excel_service.generate_job_template()
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="JOBFLEX_Job_Upload_Template.xlsx"
    )


@app.post("/api/employer/jobs/parse-excel")
@employer_required
def api_parse_job_excel():
    """Parse an uploaded Excel spreadsheet and return extracted job listings for review."""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded."}), 400
    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"ok": False, "error": "Please upload a valid Excel file (.xlsx or .xls)."}), 400
    res = excel_service.parse_job_excel(f.stream)
    return jsonify(res)


@app.post("/api/employer/jobs/bulk-upload")
@employer_required
def api_bulk_upload_jobs():
    """Confirm and batch upload reviewed jobs."""
    payload = request.json or {}
    jobs_list = payload.get("jobs") or []
    if not jobs_list:
        return jsonify({"ok": False, "error": "No jobs provided for upload."}), 400
    emp, comp = current_employer(), current_company()
    res = job_store.bulk_create_jobs(emp, comp, jobs_list, default_status="Approved")
    return jsonify(res)


# --- Complete Deletion Endpoints ----------------------------------------------
@app.post("/api/employer/jobs/<int:job_id>/delete")
@employer_required
def api_delete_employer_job(job_id):
    """Delete an employer's job posting and cascade associated applications."""
    ok, msg = job_store.delete_job(job_id, employer=current_employer())
    if not ok:
        return jsonify({"ok": False, "error": msg}), 403 if "permission" in msg.lower() else 404
    return jsonify({"ok": True, "message": msg})


@app.post("/api/employer/delete-account")
@employer_required
def api_delete_employer_account():
    """Permanently delete employer account, company, and all jobs."""
    emp = current_employer()
    ok, msg = job_store.delete_employer_account(emp["id"])
    if not ok:
        return jsonify({"ok": False, "error": msg}), 500
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("home")})


@app.post("/api/seeker/delete-account")
@seeker_required
def api_delete_seeker_account():
    """Permanently delete seeker account, profile, resumes, and applications."""
    seeker = current_seeker()
    ok = store.delete_seeker_account(seeker["id"])
    if not ok:
        return jsonify({"ok": False, "error": "Failed to delete account."}), 500
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("home")})


@app.post("/api/seeker/resume/reset")
@seeker_required
def api_reset_seeker_resume():
    """Clear seeker resume text and reset resume builder."""
    seeker = current_seeker()
    ok = store.reset_resume(seeker["id"])
    return jsonify({"ok": ok})


@app.post("/api/admin/jobs/<int:job_id>/delete")
def api_admin_delete_job(job_id):
    """Admin endpoint to permanently delete any job posting."""
    if current_role() != "admin":
        return jsonify({"ok": False, "error": "Admins only."}), 403
    ok, msg = job_store.delete_job(job_id)
    return jsonify({"ok": ok, "message": msg}), 200 if ok else 404


@app.post("/api/admin/users/<user_type>/<int:user_id>/delete")
def api_admin_delete_user(user_type, user_id):
    """Admin endpoint to delete any seeker or employer account."""
    if current_role() != "admin":
        return jsonify({"ok": False, "error": "Admins only."}), 403
    ok, msg = job_store.admin_delete_user(user_type, user_id)
    return jsonify({"ok": ok, "message": msg}), 200 if ok else 400


# ------------------------------------------------------------------ CLI --
@app.cli.command("seed-demo")
def seed_demo_command():
    """Create the demo employer (Northlane Digital) and demo job seeker (Jordan Reyes)."""
    import click
    password = os.environ.get("DEMO_EMPLOYER_PASSWORD") or secrets.token_urlsafe(9) + "7"
    employer_auth.seed_demo(password)
    seeker_auth.seed_demo(password)
    click.echo(f"Demo employer ready:   {employer_auth.DEMO_EMAIL} / {password}")
    click.echo(f"Demo job seeker ready: {seeker_auth.DEMO_EMAIL} / {password}")


# Optional: auto-create the demo employer on boot (handy on hosts with an ephemeral database).
if (os.environ.get("JOBFLEX_SEED_DEMO") == "1" or os.environ.get("NEXORA_SEED_DEMO") == "1") and os.environ.get("DEMO_EMPLOYER_PASSWORD"):
    with app.app_context():
        employer_auth.seed_demo(os.environ["DEMO_EMPLOYER_PASSWORD"])
        seeker_auth.seed_demo(os.environ["DEMO_EMPLOYER_PASSWORD"])


if __name__ == "__main__":
    app.run(debug=True, port=5000)
