from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from energy_mvp.models import AnalysisBundle, AnalysisEvent
from energy_mvp.report import write_bundle_json


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


if __name__ == "__main__":
    unittest.main()
