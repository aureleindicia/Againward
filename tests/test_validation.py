from __future__ import annotations

import unittest

from energy_mvp.validation import temporal_iou, validate_events


def event(identifier: str, event_type: str, start: str, end: str) -> dict[str, str]:
    return {
        "anomaly_id": identifier,
        "event_id": identifier,
        "type": event_type,
        "start": start,
        "end": end,
    }


class EventValidationTests(unittest.TestCase):
    def test_temporal_iou_uses_event_windows_not_rows(self) -> None:
        first = event("A", "drift", "2026-01-01", "2026-01-11")
        second = event("D", "drift", "2026-01-06", "2026-01-16")

        self.assertAlmostEqual(temporal_iou(first, second), 5 / 15)

    def test_events_are_matched_at_most_once(self) -> None:
        injected = [event("A", "spike", "2026-01-01T10:00", "2026-01-01T12:00")]
        detected = [
            event("D1", "spike", "2026-01-01T10:00", "2026-01-01T12:00"),
            event("D2", "spike", "2026-01-01T10:30", "2026-01-01T11:30"),
        ]

        result = validate_events(injected, detected)

        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["false_negatives"], 0)
        self.assertEqual(result["precision"], 0.5)

    def test_type_mismatch_is_not_a_true_positive(self) -> None:
        injected = [event("A", "drift", "2026-01-01", "2026-01-11")]
        detected = [event("D", "spike", "2026-01-01", "2026-01-11")]

        result = validate_events(injected, detected)

        self.assertEqual(result["true_positives"], 0)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["false_negatives"], 1)

    def test_no_injected_and_no_detected_events_is_perfect_empty_case(self) -> None:
        result = validate_events([], [])

        self.assertEqual(result["precision"], 1)
        self.assertEqual(result["recall"], 1)
        self.assertEqual(result["f1"], 1)


if __name__ == "__main__":
    unittest.main()
