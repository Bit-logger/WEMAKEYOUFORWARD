"""Opt-in Supabase integration smoke test. Set NEXORA_RUN_SUPABASE_TESTS=1 to run."""
import os, unittest

@unittest.skipUnless(os.getenv("NEXORA_RUN_SUPABASE_TESTS") == "1", "requires configured Supabase test project")
class SupabaseSeekerIntegrationTests(unittest.TestCase):
    def test_supabase_configuration_is_present(self):
        self.assertTrue(os.getenv("SUPABASE_URL"))
        self.assertTrue(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY"))

if __name__ == "__main__": unittest.main()
