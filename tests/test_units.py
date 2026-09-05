from __future__ import annotations

import unittest

from energy_mvp.units import convert_energy_to_kwh, convert_power_to_kw


class UnitConversionTests(unittest.TestCase):
    def test_energy_conversions(self) -> None:
        self.assertAlmostEqual(convert_energy_to_kwh(100_000, "wh"), 100)
        self.assertAlmostEqual(convert_energy_to_kwh(100, "kwh"), 100)
        self.assertAlmostEqual(convert_energy_to_kwh(0.1, "mwh"), 100)

    def test_power_conversions(self) -> None:
        self.assertAlmostEqual(convert_power_to_kw(100_000, "w"), 100)
        self.assertAlmostEqual(convert_power_to_kw(100, "kw"), 100)
        self.assertAlmostEqual(convert_power_to_kw(0.1, "mw"), 100)

    def test_unknown_unit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non prise en charge"):
            convert_energy_to_kwh(1, "joule")


if __name__ == "__main__":
    unittest.main()
