from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from energy_mvp.charts import write_line_chart, write_scatter_chart


class ChartTests(unittest.TestCase):
    def assert_png(self, path: Path, width: int, height: int) -> None:
        payload = path.read_bytes()
        self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", payload[16:24]), (width, height))
        self.assertGreater(len(payload), 100)

    def test_line_chart_is_a_valid_png_without_gui_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "line.png"
            write_line_chart({"a": [1, 2, 3], "b": [3, 2, 1]}, path, title="test")

            self.assert_png(path, 900, 360)

    def test_scatter_chart_is_a_valid_png(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scatter.png"
            write_scatter_chart([(1, 2), (2, 4), (3, 6)], path, title="test")

            self.assert_png(path, 720, 480)


if __name__ == "__main__":
    unittest.main()
