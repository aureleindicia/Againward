from __future__ import annotations

import binascii
import math
import struct
import zlib
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from .models import Reading


Color = tuple[int, int, int]
COLORS: tuple[Color, ...] = (
    (31, 119, 180),
    (214, 39, 40),
    (44, 160, 44),
    (255, 127, 14),
)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


class _Canvas:
    def __init__(self, width: int, height: int, background: Color = (255, 255, 255)):
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def point(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset:offset + 3] = bytes(color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            self.point(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy

    def circle(self, x: int, y: int, radius: int, color: Color) -> None:
        for offset_y in range(-radius, radius + 1):
            for offset_x in range(-radius, radius + 1):
                if offset_x * offset_x + offset_y * offset_y <= radius * radius:
                    self.point(x + offset_x, y + offset_y, color)

    def save(self, path: str | Path, *, title: str) -> None:
        raw = b"".join(
            b"\x00" + bytes(self.pixels[row * self.width * 3:(row + 1) * self.width * 3])
            for row in range(self.height)
        )
        png = b"\x89PNG\r\n\x1a\n"
        png += _chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
        png += _chunk(b"tEXt", b"Title\x00" + title.encode("latin-1", errors="replace"))
        png += _chunk(b"IDAT", zlib.compress(raw, level=6))
        png += _chunk(b"IEND", b"")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(png)


def _finite(values: Sequence[float | None]) -> list[float]:
    return [float(value) for value in values if value is not None and math.isfinite(value)]


def _downsample(values: Sequence[float | None], target: int) -> list[float | None]:
    if len(values) <= target:
        return list(values)
    result: list[float | None] = []
    for index in range(target):
        start = index * len(values) // target
        end = (index + 1) * len(values) // target
        bucket = _finite(values[start:end])
        result.append(mean(bucket) if bucket else None)
    return result


def write_line_chart(
    series: Mapping[str, Sequence[float | None]],
    path: str | Path,
    *,
    title: str,
    width: int = 900,
    height: int = 360,
    zero_floor: bool = False,
) -> None:
    if not series:
        raise ValueError("Un graphique exige au moins une serie.")
    margin_left, margin_right, margin_top, margin_bottom = 52, 18, 20, 36
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    sampled = {name: _downsample(values, plot_width) for name, values in series.items()}
    all_values = [value for values in sampled.values() for value in _finite(values)]
    if not all_values:
        raise ValueError("Les series ne contiennent aucune valeur finie.")
    minimum = min(0.0, min(all_values)) if zero_floor else min(all_values)
    maximum = max(all_values)
    if math.isclose(minimum, maximum):
        minimum -= 1.0
        maximum += 1.0
    padding = (maximum - minimum) * 0.05
    minimum -= padding
    maximum += padding

    def y_pixel(value: float) -> int:
        ratio = (value - minimum) / (maximum - minimum)
        return margin_top + plot_height - round(ratio * plot_height)

    canvas = _Canvas(width, height)
    axis = (95, 105, 115)
    grid = (225, 230, 235)
    for step in range(6):
        y = margin_top + round(plot_height * step / 5)
        canvas.line(margin_left, y, width - margin_right, y, grid)
    canvas.line(margin_left, margin_top, margin_left, margin_top + plot_height, axis)
    canvas.line(margin_left, margin_top + plot_height, width - margin_right, margin_top + plot_height, axis)
    for series_index, values in enumerate(sampled.values()):
        color = COLORS[series_index % len(COLORS)]
        previous: tuple[int, int] | None = None
        denominator = max(1, len(values) - 1)
        for index, value in enumerate(values):
            if value is None:
                previous = None
                continue
            x = margin_left + round(plot_width * index / denominator)
            y = y_pixel(float(value))
            if previous is not None:
                canvas.line(previous[0], previous[1], x, y, color)
            previous = (x, y)
    canvas.save(path, title=title)


def write_scatter_chart(
    points: Sequence[tuple[float, float]],
    path: str | Path,
    *,
    title: str,
    width: int = 720,
    height: int = 480,
) -> None:
    finite_points = [
        (float(x), float(y)) for x, y in points if math.isfinite(x) and math.isfinite(y)
    ]
    if not finite_points:
        raise ValueError("Un nuage exige au moins un point fini.")
    if len(finite_points) > 5000:
        step = math.ceil(len(finite_points) / 5000)
        finite_points = finite_points[::step]
    margin = 45
    xs = [point[0] for point in finite_points]
    ys = [point[1] for point in finite_points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if math.isclose(x_min, x_max):
        x_min, x_max = x_min - 1, x_max + 1
    if math.isclose(y_min, y_max):
        y_min, y_max = y_min - 1, y_max + 1
    canvas = _Canvas(width, height)
    canvas.line(margin, margin, margin, height - margin, (95, 105, 115))
    canvas.line(margin, height - margin, width - margin, height - margin, (95, 105, 115))
    for x, y in finite_points:
        px = margin + round((x - x_min) / (x_max - x_min) * (width - 2 * margin))
        py = height - margin - round((y - y_min) / (y_max - y_min) * (height - 2 * margin))
        canvas.circle(px, py, 1, COLORS[0])
    canvas.save(path, title=title)


def plot_power_timeseries(readings: Sequence[Reading], path: str | Path) -> None:
    write_line_chart(
        {"power_kw": [reading.power_kw for reading in readings]},
        path,
        title="Puissance dans le temps (kW)",
        zero_floor=True,
    )


def plot_observed_expected(residuals: Sequence[dict[str, Any]], path: str | Path) -> None:
    write_line_chart(
        {
            "observed_kw": [item["observed_kw"] for item in residuals],
            "expected_kw": [item["expected_kw"] for item in residuals],
        },
        path,
        title="Puissance observee et attendue (kW)",
        zero_floor=True,
    )


def plot_daily_residual(residuals: Sequence[dict[str, Any]], path: str | Path) -> None:
    buckets: dict[str, list[float]] = defaultdict(list)
    for item in residuals:
        buckets[item["timestamp"][:10]].append(item["residual_kw"])
    write_line_chart(
        {"daily_residual_kw": [mean(values) for _, values in sorted(buckets.items())]},
        path,
        title="Residu quotidien moyen (kW)",
    )


def plot_energy_production(readings: Sequence[Reading], path: str | Path) -> None:
    points = [
        (reading.production, reading.power_kw)
        for reading in readings
        if reading.production is not None and reading.power_kw is not None
    ]
    write_scatter_chart(points, path, title="Production et puissance")
