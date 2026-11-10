"""Comprehensive End-to-End and Security Test Suite for NEXORA.

Validates:
1. Public Pages & Clean Rendering (No template leaks, no raw fences, no conflict markers)
2. Search, Filtering, and Sanitization (SQLi, XSS)
3. Auth Pages, CSRF Defense, and Inline Form Validation
4. Route Guards & Access Control Redirects (Seeker & Employer)
5. Job Seeker Lifecycle (Dashboard, Profile, Resume, Saved Roles, Applications, Matches, Upgrade)
6. Employer Hiring Lifecycle (Dashboard, Post Job, Checkout, Candidates, Stage Moves)
7. Admin Moderation & Reports (Dashboard, Suspend, Approve, Resolve)
8. Role Separation & Privilege Escalation Protections
"""
import os
import re
import unittest
from dotenv import load_dotenv

load_dotenv()

import app
import db
import job_store
import seeker_store
import data


class NexoraComprehensiveTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.app.config["TESTING"] = True

    # ----------------- SECTION 1: PUBLIC PAGES & DOM HEALTH -----------------
    def test_public_pages_and_dom_integrity(self):
        public_routes = [
            ('/', "Homepage"),
            ('/jobs', "Jobs Directory"),
            ('/jobs/1000', "Seed Job 1000 Details"),
            ('/companies', "Companies Directory"),
            ('/companies/northlane-digital', "Northlane Digital Company Page"),
            ('/pricing', "Employer Pricing"),
            ('/non-existent-page-xyz', "404 Page"),
        ]
        client = app.app.test_client()
        for url, name in public_routes:
            with self.subTest(route=url, name=name):
                res = client.get(url)
                expected_status = 404 if "non-existent" in url else 200
                self.assertEqual(res.status_code, expected_status, f"Route {url} returned {res.status_code}")
                if expected_status == 200:
                    html = res.get_data(as_text=True)
                    self.assertNotIn("```html", html, f"Raw markdown fence in {url}")
                    self.assertNotIn("<<<<<<<", html, f"Git conflict marker in {url}")
                    leaks = re.findall(r'(\{\{[^\}]+\}\}|\{%[^%]+%\})', html)
                    real_leaks = [l for l in leaks if not l.startswith('{{ jobs_json') and not l.startswith('{{ saved_ids')]
                    self.assertEqual(len(real_leaks), 0, f"Unrendered Jinja tag in {url}: {real_leaks[:2]}")

    # ----------------- SECTION 2: SEARCH, FILTERS & SANITIZATION -----------------
    def test_search_filtering_and_sanitization(self):
        client = app.app.test_client()
        filter_tests = [
            ('/jobs?q=Engineer', "Search by Keyword"),
            ('/jobs?location=Sydney%2C+NSW', "Filter by Location"),
            ('/jobs?industry=Technology', "Filter by Industry"),
            ('/jobs?mode=Remote', "Filter by Work Mode"),
            ('/jobs?type=Full-time', "Filter by Job Type"),
            ('/jobs?q=NonsensicalQueryStringThatMatchesNothing123', "Search No-Results Query"),
            ('/jobs?q=%27%20OR%201%3D1%20--', "SQL Injection Pattern in Search"),
            ('/jobs?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E', "XSS Pattern in Search"),
        ]
        for url, name in filter_tests:
            with self.subTest(test=name, url=url):
                res = client.get(url)
                self.assertEqual(res.status_code, 200)
                html = res.get_data(as_text=True)
                self.assertNotIn("<script>alert(1)</script>", html, "XSS reflected unescaped")

    # ----------------- SECTION 3: AUTH PAGES, CSRF & VALIDATION -----------------
    def test_auth_pages_csrf_and_validation(self):
        client = app.app.test_client()
        auth_pages = [
            '/employer/login', '/employer/register', '/employer/forgot',
            '/seeker/login', '/seeker/register', '/seeker/forgot',
        ]
        for url in auth_pages:
            with self.subTest(auth_page=url):
                res = client.get(url)
                self.assertEqual(res.status_code, 200)
                html = res.get_data(as_text=True)
                self.assertIn('name="csrf_token"', html, f"Missing CSRF token field in {url}")

        # CSRF Rejection check
        c_csrf = app.app.test_client()
        res_no_csrf = c_csrf.post('/seeker/register', data={"email": "hacker@test.com"})
        self.assertEqual(res_no_csrf.status_code, 302, "Request without CSRF must be redirected")

        # Inline validation check on empty submissions
        c_val = app.app.test_client()
        with c_val.session_transaction() as sess:
            sess["_csrf"] = "test-token"
        res_reg = c_val.post('/seeker/register', data={"csrf_token": "test-token"})
        self.assertEqual(res_reg.status_code, 200)
        self.assertIn(b'name="email"', res_reg.data)

        res_log = c_val.post('/seeker/login', data={"csrf_token": "test-token"})
        self.assertEqual(res_log.status_code, 200)
        self.assertIn(b'name="email"', res_log.data)

    # ----------------- SECTION 4: ROUTE GUARDS & ACCESS CONTROL -----------------
    def test_route_guards_and_redirects(self):
        seeker_protected = [
            ('/dashboard/seeker', "Seeker Dashboard"),
            ('/seeker/profile', "Seeker Profile"),
            ('/seeker/resume', "Seeker Resume"),
            ('/seeker/applications', "Seeker Applications"),
            ('/seeker/matches', "Seeker Matches"),
            ('/seeker/upgrade', "Seeker Upgrade"),
            ('/seeker/saved', "Seeker Saved Roles"),
            ('/seeker/interview-practice', "Seeker Interview Practice"),
            ('/seeker/alerts', "Seeker Job Alerts"),
        ]
        for url, name in seeker_protected:
            with self.subTest(guard=name):
                c = app.app.test_client()
                res = c.get(url, follow_redirects=False)
                self.assertEqual(res.status_code, 302)
                self.assertIn("/seeker/login", res.headers.get("Location", ""))

        employer_protected = [
            ('/dashboard/employer', "Employer Dashboard"),
            ('/post-job', "Post a Job"),
            ('/checkout', "Checkout Posting"),
            ('/applicants', "Applicants Pipeline"),
            ('/employer/setup', "Employer Setup"),
        ]
        for url, name in employer_protected:
            with self.subTest(guard=name):
                c = app.app.test_client()
                res = c.get(url, follow_redirects=False)
                self.assertEqual(res.status_code, 302)
                self.assertIn("/employer/login", res.headers.get("Location", ""))

    # ----------------- SECTION 5: JOB SEEKER LIFECYCLE -----------------
    def test_seeker_lifecycle_and_actions(self):
        c_seeker = app.app.test_client()
        with c_seeker.session_transaction() as sess:
            sess['seeker_id'] = 1

        seeker_pages = [
            '/dashboard/seeker', '/seeker/profile', '/seeker/resume',
            '/seeker/applications', '/seeker/matches', '/seeker/upgrade',
            '/seeker/saved', '/seeker/interview-practice', '/seeker/alerts'
        ]
        for url in seeker_pages:
            with self.subTest(seeker_page=url):
                res = c_seeker.get(url)
                self.assertEqual(res.status_code, 200)

        # Profile Section Updates
        sections = [
            ('basic', {"headline": "Lead Full-Stack Engineer", "phone": "0412345678", "location": "Sydney, NSW"}),
            ('skills', {"skills": "Python, React, TypeScript, PostgreSQL, Cloud"}),
            ('education', {"education_institution_0": "UNSW", "education_qualification_0": "B.Sc CS", "education_year_0": "2022"}),
            ('additional', {"work_rights": "Australian citizen", "pref_job_type": "Full-time", "pref_work_mode": "Hybrid", "pref_location": "Sydney, NSW", "linkedin": "https://linkedin.com/in/test", "portfolio": "https://example.com"}),
        ]
        for sec, payload in sections:
            with self.subTest(profile_section=sec):
                res = c_seeker.post(f'/seeker/profile/{sec}', data=payload, follow_redirects=True)
                self.assertEqual(res.status_code, 200)

        # Resume Builder Update
        res_resume = c_seeker.post('/seeker/resume', data={"template": "modern", "summary": "Senior engineer."}, follow_redirects=True)
        self.assertEqual(res_resume.status_code, 200)

        # Save/Bookmark Job
        res_save = c_seeker.post('/api/jobs/1000/save')
        self.assertEqual(res_save.status_code, 200)
        self.assertTrue(res_save.json.get("ok"))

        # Apply to Job
        res_apply = c_seeker.post('/api/jobs/1000/apply', json={"cover_note": "Automated test note."})
        self.assertEqual(res_apply.status_code, 200)
        self.assertTrue(res_apply.json.get("ok"))

        # Subscription Upgrade
        res_upg = c_seeker.post('/seeker/upgrade', data={"plan": "premium"}, follow_redirects=True)
        self.assertEqual(res_upg.status_code, 200)

    # ----------------- SECTION 6: EMPLOYER LIFECYCLE -----------------
    def test_employer_lifecycle_and_hiring(self):
        c_emp = app.app.test_client()
        with c_emp.session_transaction() as sess:
            sess['employer_id'] = 1

        employer_pages = ['/dashboard/employer', '/post-job', '/checkout', '/applicants', '/employer/setup']
        for url in employer_pages:
            with self.subTest(emp_page=url):
                res = c_emp.get(url)
                self.assertEqual(res.status_code, 200)

        # Create Draft Job
        job_payload = {
            "title": "Staff Reliability Engineer",
            "description": "Architecting resilient distributed systems.",
            "location": "Sydney, NSW",
            "industry": "Technology",
            "type": "Full-time",
            "mode": "Hybrid",
            "experience": "5+ years",
            "salary_min": 170000,
            "salary_max": 220000,
            "skills": "Python, Cloud, Architecture"
        }
        res_pjob = c_emp.post('/api/post-job', json=job_payload)
        self.assertEqual(res_pjob.status_code, 200)
        new_jid = res_pjob.json.get("job_id")
        self.assertIsNotNone(new_jid)

        # Publish via Checkout
        res_chk = c_emp.post('/api/checkout', json={"package": "urgent"})
        self.assertEqual(res_chk.status_code, 200)
        self.assertTrue(res_chk.json.get("ok"))

        # Verify job is active
        created_job = data.get_job(new_jid)
        self.assertIsNotNone(created_job)
        self.assertEqual(created_job.get("status"), "Approved")

        # Applicant stage management
        candidates = data.candidates_for_employer(db.get_employer(1))
        self.assertIsInstance(candidates, list)
        if candidates:
            first_id = candidates[0]["id"]
            res_stage = c_emp.post(f'/api/applicants/{first_id}/stage', json={"stage": "Shortlisted"})
            self.assertEqual(res_stage.status_code, 200)
            self.assertTrue(res_stage.json.get("ok"))

    # ----------------- SECTION 7: ADMIN OPERATIONS -----------------
    def test_admin_moderation_and_reports(self):
        c_admin = app.app.test_client()
        with c_admin.session_transaction() as sess:
            sess['demo_role'] = 'admin'

        res_adm = c_admin.get('/admin')
        self.assertEqual(res_adm.status_code, 200)

        # Moderate Job
        res_susp = c_admin.post('/api/admin/jobs/1000/moderate', json={"action": "suspend"})
        self.assertEqual(res_susp.status_code, 200)
        self.assertEqual(res_susp.json.get("status"), "Suspended")

        res_appr = c_admin.post('/api/admin/jobs/1000/moderate', json={"action": "approve"})
        self.assertEqual(res_appr.status_code, 200)
        self.assertEqual(res_appr.json.get("status"), "Approved")

        # Resolve Report
        reports = job_store.reports()
        if reports:
            rep_id = reports[0]["id"]
            res_rep = c_admin.post(f'/api/admin/reports/{rep_id}/resolve')
            self.assertEqual(res_rep.status_code, 200)
            self.assertTrue(res_rep.json.get("ok"))

    # ----------------- SECTION 8: ROLE SEPARATION & PRIVILEGE ESCALATION -----------------
    def test_role_separation_and_privilege_escalation(self):
        c_emp = app.app.test_client()
        with c_emp.session_transaction() as sess:
            sess['employer_id'] = 1

        c_seeker = app.app.test_client()
        with c_seeker.session_transaction() as sess:
            sess['seeker_id'] = 1

        # Employer cannot call Seeker APIs
        res1 = c_emp.post('/api/jobs/1000/save')
        self.assertIn(res1.status_code, (401, 403))

        res2 = c_emp.post('/api/jobs/1000/apply', json={"cover_note": "Denied"})
        self.assertIn(res2.status_code, (401, 403))

        # Seeker cannot post a job
        res3 = c_seeker.post('/api/post-job', json={"title": "Unauthorized"})
        self.assertIn(res3.status_code, (401, 403, 302))

        # Seeker cannot moderate jobs
        res4 = c_seeker.post('/api/admin/jobs/1000/moderate', json={"action": "suspend"})
        self.assertEqual(res4.status_code, 403)


if __name__ == "__main__":
    unittest.main()

