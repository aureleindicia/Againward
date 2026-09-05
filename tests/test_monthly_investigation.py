from __future__ import annotations

import unittest

from workspace.monthly_investigation import build_quantitative
from workspace.monthly_review import build_review


class MonthlyInvestigationTests(unittest.TestCase):
    def test_monthly_review_refuses_intraday_and_recoverable_saving_claims(self) -> None:
        quantitative = build_quantitative()
        review = build_review(quantitative)

        self.assertFalse(quantitative["dataset"]["intraday_analysis_allowed"])
        self.assertIsNone(
            quantitative["tests"]["M01_zero_production_months"]["recoverable_saving_kwh"]
        )
        self.assertEqual(review["final_review"]["confirmed"], [])
        self.assertFalse(review["final_review"]["intraday_claim_made"])
        decisions = {
            item["hypothesis_id"]: item["decision"] for item in review["hypotheses"]
        }
        self.assertEqual(decisions["M02"], "REJETE")
        self.assertEqual(decisions["M03"], "INSUFFISAMMENT_ETAYE")
        by_id = {item["hypothesis_id"]: item for item in review["hypotheses"]}
        self.assertEqual(by_id["M02"]["follow_up_requests"], [])
        for hypothesis_id in ("M01", "M03"):
            request = by_id[hypothesis_id]["follow_up_requests"][0]
            self.assertTrue(request["ask_client"])
            self.assertTrue(request["why_useful"])
            self.assertGreaterEqual(len(request["hypotheses_distinguished"]), 2)
            self.assertTrue(request["client_effort"])
            self.assertTrue(request["expected_if_true"])
            self.assertIn("non_etablie", by_id[hypothesis_id]["physical_cause_status"])


if __name__ == "__main__":
    unittest.main()
