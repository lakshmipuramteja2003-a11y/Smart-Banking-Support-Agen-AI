import unittest

from banking_agent import BankingSession, calculate_monthly_emi


class BankingAgentTests(unittest.TestCase):
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