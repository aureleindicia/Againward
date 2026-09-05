from __future__ import annotations

import unittest

from energy_mvp.intake import assess_intake, intake_template


class IntakeTests(unittest.TestCase):
    def test_obvious_measurement_metadata_is_not_asked_again(self) -> None:
        payload = intake_template()
        assessment = assess_intake(payload, evidence={
            "measurement_kind": "power",
            "unit": "kw",
            "timestamp_position": "start",
            "timestamp_position_is_authoritative": False,
            "production_available_in_dataset": True,
        })

        critical_fields = {item["field"] for item in assessment.missing_critical}
        context_fields = {item["field"] for item in assessment.missing_context}
        self.assertNotIn("metering.measurement_kind", critical_fields)
        self.assertNotIn("metering.unit", critical_fields)
        self.assertIn("metering.timestamp_position", critical_fields)
        self.assertNotIn("production.available", context_fields)

    def test_empty_template_asks_precise_critical_questions(self) -> None:
        assessment = assess_intake(intake_template())
        self.assertFalse(assessment.valid)
        fields = {item["field"] for item in assessment.missing_critical}
        self.assertEqual(fields, {
            "site.timezone", "site.meter_scope", "metering.measurement_kind",
            "metering.unit", "metering.timestamp_position",
        })
        self.assertTrue(all(item["ask_client"] for item in assessment.missing_critical))
        self.assertTrue(all(item["why_useful"] for item in assessment.missing_critical))

    def test_minimal_scheduled_context_enables_only_supported_capabilities(self) -> None:
        payload = intake_template()
        payload["site"].update({"timezone": "Europe/Paris", "meter_scope": "atelier"})
        payload["metering"].update({
            "measurement_kind": "power", "unit": "kW", "timestamp_position": "start",
        })
        payload["operations"].update({
            "operating_mode": "scheduled", "weekly_schedule": {"monday": ["08:00", "17:00"]},
        })
        payload["production"]["available"] = False
        assessment = assess_intake(payload)
        self.assertTrue(assessment.valid)
        self.assertTrue(assessment.declared_capabilities["off_schedule_analysis"])
        self.assertFalse(assessment.declared_capabilities["production_efficiency_analysis"])

    def test_24_7_site_does_not_require_a_weekly_schedule(self) -> None:
        payload = intake_template()
        payload["site"].update({"timezone": "UTC", "meter_scope": "site"})
        payload["metering"].update({
            "measurement_kind": "energy_per_interval", "unit": "kWh",
            "timestamp_position": "end",
        })
        payload["operations"]["operating_mode"] = "24_7"
        assessment = assess_intake(payload)
        self.assertTrue(assessment.valid)
        self.assertTrue(assessment.declared_capabilities["continuous_operation_context"])
        self.assertNotIn(
            "operations.weekly_schedule",
            {item["field"] for item in assessment.missing_context},
        )


if __name__ == "__main__":
    unittest.main()
