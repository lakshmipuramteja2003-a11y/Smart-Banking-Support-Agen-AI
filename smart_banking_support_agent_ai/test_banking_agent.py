import os
import unittest
from unittest.mock import patch

from banking_agent import BankingSession, calculate_monthly_emi, resolve_ai_settings


class BankingAgentTests(unittest.TestCase):
    def test_resolve_ai_settings_prefers_openrouter(self):
        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "or-key",
                "OPENROUTER_MODEL": "openrouter/model:free",
                "OPENROUTER_BASE_URL": "https://example.test/v1",
                "OPENAI_API_KEY": "legacy-key",
            },
            clear=True,
        ):
            api_key, model_name, base_url = resolve_ai_settings()
            self.assertEqual(api_key, "or-key")
            self.assertEqual(model_name, "openrouter/model:free")
            self.assertEqual(base_url, "https://example.test/v1")

    def test_resolve_ai_settings_falls_back_to_legacy_openai_env(self):
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "legacy-key", "OPENAI_MODEL": "gpt-4o-mini"},
            clear=True,
        ):
            api_key, model_name, base_url = resolve_ai_settings()
            self.assertEqual(api_key, "legacy-key")
            self.assertEqual(model_name, "gpt-4o-mini")
            self.assertEqual(base_url, "https://openrouter.ai/api/v1")

    def test_example_emi(self):
        emi = calculate_monthly_emi(500_000, 10.5, 36)
        self.assertAlmostEqual(emi, 16_251.0, delta=2)

    def test_zero_interest_emi(self):
        self.assertEqual(calculate_monthly_emi(120_000, 0, 12), 10_000)

    def test_example_customer_qualifies(self):
        session = BankingSession()
        result = session.check_loan_eligibility(60_000, 5_000, 500_000, 36)
        self.assertTrue(result["eligible"])
        self.assertLess(result["debt_to_income_percent"], 50)

    def test_unknown_customer_id_is_rejected(self):
        with self.assertRaises(ValueError):
            BankingSession().get_account_details("UNKNOWN")

    def test_submission_requires_host_confirmation(self):
        session = BankingSession()
        session.get_account_details("CUST1001")
        session.check_loan_eligibility(60_000, 5_000, 500_000, 36)

        blocked = session.submit_loan_application("CUST1001", 500_000, 36)
        self.assertFalse(blocked["submitted"])
        self.assertIsNone(session.application)

        session.authorize_submission()
        submitted = session.submit_loan_application("CUST1001", 500_000, 36)
        self.assertTrue(submitted["submitted"])
        self.assertFalse(session.confirmation_authorized)

    def test_submission_rejects_changed_terms(self):
        session = BankingSession()
        session.get_account_details("CUST1001")
        session.check_loan_eligibility(60_000, 5_000, 500_000, 36)
        session.authorize_submission()

        result = session.submit_loan_application("CUST1001", 400_000, 36)
        self.assertFalse(result["submitted"])


if __name__ == "__main__":
    unittest.main()