from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from energy_mvp.models import AnalysisBundle, AnalysisEvent, AnalysisResult
from energy_mvp.report import render_markdown, write_bundle_json


class ReportTests(unittest.TestCase):
    def event(self, metric: float) -> AnalysisEvent:
        return AnalysisEvent(
            event_id="EV-H01",
            type="night_anomaly",
            start="2026-01-01T00:00:00",
            end="2026-01-01T01:00:00",
            duration_hours=1.0,
            evaluated_hours=1.0,
            observed_energy_kwh=metric + 10,
            expected_energy_kwh=10,
            excess_energy_kwh=metric,
            cost=None,
            potential_saving_kwh=None,
            recoverability="unknown",
            severity="moyenne",
            confidence={"observation": "elevee", "opportunity": "moyenne"},
            decision="A_CONSERVER_AVEC_RESERVES",
            supporting_methods=["baseline"],
            related_hypotheses=[],
        )

    def test_bundle_serialization_preserves_identical_metric_values(self) -> None:
        metric = 12.345678901234
        bundle = AnalysisBundle(
            automatic_analysis={"total_energy_kwh": metric},
            quantitative_results={"H01": {"excess_energy_kwh": metric}},
            investigation={"H01": {"result": metric}},
            events=[self.event(metric)],
            artifacts={"report": "report.md"},
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "analysis.json"
            write_bundle_json(bundle, target)
            payload = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(payload["automatic_analysis"]["total_energy_kwh"], metric)
        self.assertEqual(payload["quantitative_results"]["H01"]["excess_energy_kwh"], metric)
        self.assertEqual(payload["investigation"]["H01"]["result"], metric)
        self.assertEqual(payload["events"][0]["excess_energy_kwh"], metric)

    def test_event_schema_rejects_energy_or_duration_inconsistency(self) -> None:
        with self.assertRaisesRegex(ValueError, "surconsommation"):
            AnalysisEvent(
                event_id="EV-X",
                type="test",
                start="2026-01-01T00:00:00",
                end="2026-01-01T01:00:00",
                duration_hours=1,
                evaluated_hours=1,
                observed_energy_kwh=5,
                expected_energy_kwh=0,
                excess_energy_kwh=6,
                cost=None,
                potential_saving_kwh=None,
                recoverability="unknown",
                severity="faible",
                confidence={},
                decision="REJETE",
                supporting_methods=[],
                related_hypotheses=[],
            )

        with self.assertRaisesRegex(ValueError, "duree"):
            event = self.event(5)
            event.duration_hours = 2
            event.__post_init__()

    def test_report_uses_investigation_positioning_and_regulatory_boundary(self) -> None:
        result = AnalysisResult(
            source="test.csv", start=datetime(2026, 1, 1), end=datetime(2026, 1, 2),
            input_rows=1, valid_rows=1, discarded_rows=0, total_energy_kwh=10,
            total_cost=None, total_production=None, energy_intensity=None,
            off_production_kwh=None, off_production_share=None, peak_power_kw=None,
            average_power_kw=None, anomaly_count=0, monthly=[], findings=[], warnings=[],
            metadata={
                "energy_mode": "interval", "measurement_kind": "energy_per_interval",
                "data_quality": {}, "capabilities": {"intraday_analysis": False},
            },
        )
        markdown = render_markdown(result)

        self.assertIn("investigation énergétique sur données", markdown)
        self.assertIn("ne constitue pas un audit énergétique réglementaire", markdown)
        self.assertNotIn("pre-diagnostic", markdown.lower())


if __name__ == "__main__":
    unittest.main()
