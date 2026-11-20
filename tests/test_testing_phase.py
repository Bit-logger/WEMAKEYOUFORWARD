"""Test suite verifying client testing phase features:
- Skip login options for Seeker and Employer dashboards
- Unified theme on Discover Jobs and My Applications pages
- Test data availability on Discover and My Applications
- Job Market consistency for Employer
- Production backend security headers
"""
import unittest
from dotenv import load_dotenv

load_dotenv()
import app


class TestingPhaseValidationTests(unittest.TestCase):
    def setUp(self):
        app.app.config["TESTING"] = True
        self.client = app.app.test_client()

    def test_seeker_skip_login(self):
        """Visiting /seeker/skip directly logs in as demo seeker without credentials."""
        res = self.client.get("/seeker/skip", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Testing Phase Active", res.data)
        self.assertIn(b"Job Seeker Dashboard", res.data)
        self.assertIn(b"Switch to Employer Dashboard", res.data)

    def test_employer_skip_login(self):
        """Visiting /employer/skip directly logs in as demo employer without credentials."""
        res = self.client.get("/employer/skip", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Testing Phase Active", res.data)
        self.assertIn(b"Employer Dashboard", res.data)
        self.assertIn(b"Switch to Job Seeker Dashboard", res.data)

    def test_api_demo_role_switching(self):
        """API demo-role endpoint sets proper session and returns destination."""
        # Test switching to Seeker
        res_s = self.client.post("/api/demo-role", json={"role": "seeker"})
        self.assertEqual(res_s.status_code, 200)
        data_s = res_s.get_json()
        self.assertTrue(data_s["ok"])
        self.assertIn("/dashboard/seeker", data_s["redirect"])

        # Test switching to Employer
        res_e = self.client.post("/api/demo-role", json={"role": "employer"})
        self.assertEqual(res_e.status_code, 200)
        data_e = res_e.get_json()
        self.assertTrue(data_e["ok"])
        self.assertIn("/dashboard/employer", data_e["redirect"])

    def test_discover_page_theme_and_data(self):
        """Discover jobs page displays test data and unified JobFlex theme."""
        res = self.client.get("/jobs", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"jobflex-bootstrap-data", res.data)
        self.assertIn(b"discover-jobs-reference.css", res.data)
        self.assertIn(b"applications-reference.css", res.data)

    def test_applications_page_test_data(self):
        """My Applications page shows rich test data for testing."""
        # Enter as seeker
        self.client.get("/seeker/skip", follow_redirects=True)
        res = self.client.get("/seeker/applications", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"My Applications", res.data)
        self.assertIn(b"Total Applications", res.data)
        self.assertIn(b"nx-app-row", res.data)

    def test_employer_job_market_view(self):
        """Employer viewing /jobs sees Job Market with employer context preserved."""
        # Enter as employer
        self.client.get("/employer/skip", follow_redirects=True)
        res = self.client.get("/jobs", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Job Market", res.data)

    def test_security_headers(self):
        """All responses carry hardened production security headers."""
        res = self.client.get("/")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")


if __name__ == "__main__":
    unittest.main()
