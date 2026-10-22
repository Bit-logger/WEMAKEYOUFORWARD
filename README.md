# NEXORA — Client Demo

A Flask/Jinja and vanilla-JavaScript NEXORA employment marketplace. Existing frontend templates and assets are preserved. Account/profile persistence uses Supabase; prototype job listings and some marketplace analytics remain in-memory demo data.

## Run it

```
pip install -r requirements.txt
# copy .env.example to .env and configure Supabase first
python app.py
```

Then open **http://127.0.0.1:5000**.

## Employer accounts (real authentication)

Employer registration, login, company-profile setup and the dashboard use Flask sessions:
accounts and company profiles are stored in Supabase, passwords are hashed,
forms are CSRF-protected, logins are rate-limited, and employer pages/APIs require a session.

| URL | Purpose |
|---|---|
| `/employer/register` | Create account (email + password, or Google) |
| `/employer/login` | Sign in · `/employer/forgot` password reset |
| `/employer/setup` | Company profile (first-time setup, and later edits via *Company Profile*) |
| `/dashboard/employer` | Dashboard (redirects to login / setup as needed) |

Quick start for a demo account matching the design mockup (2 jobs, 44 applications, 444 views):

```
flask --app app seed-demo      # prints demo@northlane.com.au + a password
```

Environment variables (all optional locally, see `render.yaml`):
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SECRET_KEY`, `SESSION_COOKIE_SECURE=1` (https), `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET` (Google redirect URI: `https://<your-domain>/employer/google/callback`),
`SMTP_HOST/PORT/USER/PASSWORD`, `MAIL_FROM`. Without SMTP, reset links are written to the server log.

Run the tests: `python -m unittest discover -s tests -v`

Still demo-only: jobs/applicants listings, admin metrics and checkout data are in memory; they reset on server restart. Supabase persists account/profile/application data. Menu items *Account settings, Payable invoices, Invoice history, Logos and brands,
Contact us* show "coming soon".

## Job seeker accounts (real authentication)

Job seekers have the same production-style auth as employers, using the same look and feel.

| URL | Purpose |
|---|---|
| `/seeker/register` · `/seeker/login` | Create account / sign in (email + password, or Google) · `/seeker/forgot` reset |
| `/dashboard/seeker` | Dashboard: profile completion, resume status, Top-3 recommended jobs, locked extra matches, quick access |
| `/jobs` | Find Jobs (Save and Apply need a seeker login; visitors are sent to log in and brought back) |
| `/seeker/profile` | My Profile: Basic info, Education, Skills & interests, Work experience, Additional details |
| `/seeker/applications` | My Applications: status (Applied / Shortlisted / Interview / Rejected), update progress, remove |
| `/seeker/resume` | Resume Builder: 3 templates, live preview, Download PDF (browser print → Save as PDF) |
| `/seeker/matches` · `/seeker/upgrade` | All matches (Premium) · Upgrade Plan |

How it works
- **Profile completion** is weighted: Basic 25, Education 20, Skills 25, Experience 20, Additional 10.
- **Matching engine** (`matching.py`) scores each live job 0-99 from skills (60), role/title fit (25),
  location (7), work mode (4) and job type (4), using the profile *and* resume text. Free plan shows the
  top 3; Premium shows everything above 40%.
- **Applying** stores the application per user and also adds the person to the employer's applicant
  board as "New" (in-memory, like the jobs).
- **Upgrade Plan** is a demo switch (no payment is taken). Set `NEXORA_DEMO_UPGRADE=0` to disable it
  until real payments exist.

`flask --app app seed-demo` now creates both demo accounts (employer + `jordan@nexora-demo.com.au`).

Google sign-in: add **both** redirect URIs in Google Cloud:
`https://<your-domain>/employer/google/callback` and `https://<your-domain>/seeker/google/callback`.

## Demo mode

Use the "Demo mode" control in the bottom-left corner to switch between **Visitor**,
**Admin** view (simulated). **Employer** and **Job Seeker** now require a real login.

## Suggested walkthrough

1. **Visitor** — Landing page → Find Jobs → filter/sort → open a Job Details page → Apply Now.
2. **Job Seeker** — Dashboard shows the application pipeline, saved jobs and recommended roles.
3. **Employer** — Dashboard → Post a Job (4-step wizard) → choose a package → simulated
   payment → job goes live → Applicants board to move candidates through the hiring pipeline.
4. **Admin** — Marketplace metrics, job moderation queue (Approve / Reject / Review / Suspend)
   and platform reports.

## Notes for engineering handoff

- All data lives in `data.py` as in-memory Python structures — swap this layer for real
  models/DB calls when moving to production.
- Interactive state changes (save job, apply, post job, checkout, stage moves, moderation)
  go through small JSON API endpoints in `app.py` (`/api/...`) so the same endpoints can be
  re-pointed at real persistence later.
- Employer auth is real; seeker/admin auth, payments, email or AI matching are implemented — all are simulated for
  demo purposes only, as noted inline in the UI (e.g. match percentages, checkout).

## Structure

```
nexora/
├── app.py                  Flask routes + mock-state API endpoints
├── employer_auth.py        Employer register/login/setup/reset/Google (blueprint)
├── seeker_auth.py          Seeker register/login/reset/Google (blueprint)
├── seeker_portal.py        Profile, applications, resume, matches, upgrade + JSON APIs
├── seeker_store.py         Seeker data access, profile completion, resume status
├── matching.py             Job Matching Engine (pure functions)
├── auth_common.py          Shared CSRF / rate-limit / reset-token / Google helpers
├── db.py, validators.py    SQLite layer; ABN/phone/password/email validation
├── tests/                  Automated tests
├── data.py                 Mock data (jobs, candidates, seeker/employer/admin state)
├── templates/               Jinja templates (one per screen) + base.html layout
└── static/
    ├── css/custom.css       NEXORA design tokens & shared component styles
    └── js/                  app.js (shared) + per-screen interaction scripts
```


## Run locally in VS Code (Windows Command Prompt)

1. Open the `nexora` folder in VS Code.
2. Open **Terminal → New Terminal**, and select **Command Prompt**.
3. Run:

```cmd
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

4. Open the local URL printed in the terminal (commonly `http://127.0.0.1:5000`).

Job seekers can register or log in at `/seeker/register` and `/seeker/login`. Successful registration/login redirects to `/dashboard/seeker`. The seeker dashboard includes profile completion, resume status, application overview, up to three recommended jobs, locked premium matches, quick links, recent applications, and saved jobs.

## Supabase-only database setup

This version no longer creates or uses a local SQLite `.db` file. Persistent account, company, seeker profile, resume, application and saved-job records are stored in Supabase through the Flask server.

1. Copy `.env.example` to `.env` and fill in `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and a strong `SECRET_KEY`.
2. In Supabase Dashboard, open **SQL Editor**, create a query, paste `supabase/schema.sql`, and run it.
3. Install dependencies: `pip install -r requirements.txt`.
4. Start the server with `python app.py` (or `flask --app app run` after environment setup).

The server-side Supabase client uses `SUPABASE_SERVICE_ROLE_KEY` (or a compatible server-side secret key) and must never be bundled into frontend JavaScript. `SUPABASE_ANON_KEY` is retained for public-client integrations but is not used by this server-side data layer. The job catalog and demonstration listings in `data.py` are still prototype seed data held in memory; account-related persistence is Supabase-backed. Move those listings to Supabase tables before treating job posting/catalog data as persistent production data.


## Supabase Auth role behavior

- Job seekers can register and log in with Supabase Auth email/password. If email confirmation is enabled, confirm the email before logging in.
- Employer self-registration is intentionally disabled. Visiting `/employer/register` redirects to employer login with a message to contact the NEXORA administrator.
- To enable an employer, create/invite the user in Supabase Dashboard -> Authentication -> Users, then insert a matching email into `public.employers` using the SQL notes at the end of `supabase/schema.sql`. The login is accepted only if both Supabase Auth succeeds and the email has an employer row.
- Password-reset requests are sent through Supabase Auth. Configure `SUPABASE_PASSWORD_RESET_REDIRECT_URL` to a URL allowed in Supabase Authentication URL Configuration and implement/configure the corresponding recovery page for production.
- Set `SUPABASE_URL`, `SUPABASE_ANON_KEY` (or publishable key supported by your installed Supabase client), and the server-only `SUPABASE_SERVICE_ROLE_KEY` in `.env`. Never expose the service-role/secret key to the browser.
