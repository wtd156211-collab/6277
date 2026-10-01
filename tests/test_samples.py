"""对 samples 下全部案例做验收口径测试（只读 samples/**）。"""

import math
import os
import time
import unittest

from isodraw.engine import extract
from isodraw.grid import load_grid
from isodraw.report import format_lines, stat_line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRIDS = os.path.join(ROOT, "samples", "grids")
EXPECTED = os.path.join(ROOT, "samples", "expected")
CASES = ["hill", "saddle", "onpoint", "plateau", "open", "scale"]


def parse_lines_text(text):
    """把 lines.txt 解析成 [(level, CLOSED|OPEN, [(x,y),...]), ...]。"""
    lines = text.splitlines()
    blocks = []
    k = 0
    while k < len(lines):
        tag, level, npts, closed = lines[k].split()
        assert tag == "LINE"
        npts = int(npts)
        points = []
        for _ in range(npts):
            k += 1
            x, y = lines[k].split()
            points.append((float(x), float(y)))
        blocks.append((float(level), closed, points))
        k += 1
    return blocks


class SampleCasesTest(unittest.TestCase):
    def test_byte_identical_to_expected(self):
        for name in CASES:
            with self.subTest(name=name):
                grid = load_grid(os.path.join(GRIDS, name + ".txt"))
                actual = format_lines(extract(grid))
                with open(os.path.join(EXPECTED, name + ".txt"), encoding="utf-8") as fh:
                    expected = fh.read()
                self.assertEqual(actual, expected)

    def test_tolerant_compare_roundtrip(self):
        # 容差 1e-6 的交叉校验：实际点与期望点逐点比。
        for name in CASES:
            with self.subTest(name=name):
                grid = load_grid(os.path.join(GRIDS, name + ".txt"))
                actual = parse_lines_text(format_lines(extract(grid)))
                with open(os.path.join(EXPECTED, name + ".txt"), encoding="utf-8") as fh:
                    expected = parse_lines_text(fh.read())
                self.assertEqual(len(actual), len(expected))
                for (lv1, tag1, p1), (lv2, tag2, p2) in zip(actual, expected):
                    self.assertAlmostEqual(lv1, lv2, delta=1e-6)
                    self.assertEqual(tag1, tag2)
                    self.assertEqual(len(p1), len(p2))
                    for (x1, y1), (x2, y2) in zip(p1, p2):
                        self.assertAlmostEqual(x1, x2, delta=1e-6)
                        self.assertAlmostEqual(y1, y2, delta=1e-6)

    def test_points_lie_on_grid_edges(self):
        # 每个点必须落在某条格边上：x 或 y 等于格线坐标，另一维在相邻格线之间。
        for name in CASES:
            with self.subTest(name=name):
                grid = load_grid(os.path.join(GRIDS, name + ".txt"))
                xs = [grid.x0 + i * grid.dx for i in range(grid.ncols)]
                ys = [grid.y0 + j * grid.dy for j in range(grid.nrows)]
                for contour in extract(grid):
                    for x, y in contour.points:
                        on_vertical = any(abs(x - xv) <= 1e-6 and
                                          ys[0] - 1e-6 <= y <= ys[-1] + 1e-6
                                          for xv in xs)
                        on_horizontal = any(abs(y - yv) <= 1e-6 and
                                            xs[0] - 1e-6 <= x <= xs[-1] + 1e-6
                                            for yv in ys)
                        self.assertTrue(
                            on_vertical or on_horizontal,
                            f"{name}: 点 ({x},{y}) 不在格边上",
                        )

    def test_open_endpoints_are_on_outer_boundary(self):
        grid = load_grid(os.path.join(GRIDS, "open.txt"))
        for contour in extract(grid):
            self.assertFalse(contour.closed)
            for x, y in (contour.points[0], contour.points[-1]):
                on_boundary = (
                    math.isclose(x, grid.xmin, abs_tol=1e-9)
                    or math.isclose(x, grid.xmax, abs_tol=1e-9)
                    or math.isclose(y, grid.ymin, abs_tol=1e-9)
                    or math.isclose(y, grid.ymax, abs_tol=1e-9)
                )
                self.assertTrue(on_boundary)

    def test_stat_counts_match_file(self):
        for name in CASES:
            with self.subTest(name=name):
                grid = load_grid(os.path.join(GRIDS, name + ".txt"))
                contours = extract(grid)
                expected_text = format_lines(contours)
                n_blocks = expected_text.count("LINE ")
                self.assertIn(f"lines={n_blocks}", stat_line(contours))

    def test_scale_within_time_budget(self):
        # 百万格：读网格 + 提取 + 写文本与页面在 10s 内。
        from isodraw.page import render_html

        start = time.perf_counter()
        grid = load_grid(os.path.join(GRIDS, "scale.txt"))
        contours = extract(grid)
        _ = format_lines(contours)
        _ = render_html(grid, contours, title="scale.txt")
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 10.0)
        self.assertEqual(len(contours), 3)
        for c in contours:
            self.assertEqual(len(c.points), 1000)
            self.assertFalse(c.closed)


if __name__ == "__main__":
    unittest.main()
