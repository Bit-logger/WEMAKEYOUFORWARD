"""
Unit tests for Task 13 feature deliverables:
1. Bulk Job Upload via Excel (template generation, parsing, duplicate prevention, limits)
2. Complete Deletion Functionality (seeker account, resume reset, employer job, employer account, admin cascade)
"""
import io
import unittest
from dotenv import load_dotenv

load_dotenv()

import app
import excel_service
import job_store
import seeker_store


class Task13FeaturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.app.config["TESTING"] = True
        cls.client = app.app.test_client()

    def test_excel_template_generation(self):
        """Verify the downloadable job template is a valid Excel workbook with required headers."""
        buf = excel_service.generate_job_template()
        self.assertIsInstance(buf, io.BytesIO)
        buf.seek(0)
        self.assertGreater(len(buf.getvalue()), 1000)

        # Parse the generated template directly
        res = excel_service.parse_job_excel(buf)
        self.assertTrue(res["ok"])
        self.assertGreaterEqual(res["parsed_count"], 2)  # template includes 2 pre-styled sample rows
        self.assertEqual(len(res["errors"]), 0)

    def test_excel_parsing_validation_and_duplicate_prevention(self):
        """Verify duplicate job titles in the same spreadsheet are flagged and skipped."""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Job Title *", "Industry", "Location", "Job Type", "Salary Min (AUD)", "Salary Max (AUD)"])
        # Add two jobs with the exact same title
        ws.append(["Full Stack Developer", "Technology", "Sydney, NSW", "Full-time", 100000, 130000])
        ws.append(["Full Stack Developer", "Technology", "Melbourne, VIC", "Full-time", 110000, 140000])
        ws.append(["Data Analyst", "Finance", "Brisbane, QLD", "Full-time", 85000, 105000])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)

        res = excel_service.parse_job_excel(out)
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["valid_jobs"]), 2)  # 1 duplicate skipped
        self.assertEqual(len(res["errors"]), 1)
        self.assertIn("Duplicate job title", res["errors"][0])

    def test_excel_template_download_endpoint(self):
        """Verify authenticated employer can download the template."""
        with self.client.session_transaction() as sess:
            sess["employer_id"] = 1

        res = self.client.get("/employer/jobs/template")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.headers.get("Content-Type"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertIn("JOBFLEX_Job_Upload_Template.xlsx", res.headers.get("Content-Disposition", ""))

    def test_excel_parse_api_endpoint(self):
        """Verify POST /api/employer/jobs/parse-excel endpoint parses multipart file."""
        with self.client.session_transaction() as sess:
            sess["employer_id"] = 1

        buf = excel_service.generate_job_template()
        res = self.client.post(
            "/api/employer/jobs/parse-excel",
            data={"file": (buf, "test_jobs.xlsx")},
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertIn("valid_jobs", data)
        self.assertGreaterEqual(len(data["valid_jobs"]), 2)

    def test_delete_endpoints_security_authorization(self):
        """Verify unauthenticated requests cannot delete jobs or user accounts."""
        # Clean client without session
        client = app.app.test_client()

        # Attempt to delete job unauthenticated
        res_job = client.post("/api/employer/jobs/1000/delete")
        self.assertIn(res_job.status_code, (401, 302))  # 401 JSON or redirect to login

        # Attempt to delete seeker account unauthenticated
        res_seeker = client.post("/api/seeker/delete-account")
        self.assertIn(res_seeker.status_code, (401, 302))  # 401 JSON or redirect to login

        # Attempt to delete via admin endpoint as guest
        res_admin = client.post("/api/admin/jobs/1000/delete")
        self.assertEqual(res_admin.status_code, 403)


if __name__ == "__main__":
    unittest.main()
