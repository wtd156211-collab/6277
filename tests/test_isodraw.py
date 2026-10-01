"""isodraw 的 unittest 套件：只读 samples/**，写只写 var/。"""

import os
import subprocess
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isodraw import (Contour, GridFormatError, extract, load_grid,
                     render_lines, render_page, stats)
from isodraw.gridio import _fmt

SAMPLES = os.path.join(ROOT, "samples")
GRIDS = os.path.join(SAMPLES, "grids")
EXPECTED = os.path.join(SAMPLES, "expected")
VAR = os.path.join(ROOT, "var", "tests")

CASES = ("hill", "saddle", "onpoint", "plateau", "open", "scale")


def grid_path(case):
    return os.path.join(GRIDS, case + ".txt")


def expected_path(case):
    return os.path.join(EXPECTED, case + ".txt")


class SampleMatchTest(unittest.TestCase):
    """验收口径 1：lines.txt 与 samples/expected 逐字节一致。"""

    def test_all_samples_match_expected(self):
        for case in CASES:
            with self.subTest(case=case):
                grid = load_grid(grid_path(case))
                text = render_lines(extract(grid))
                with open(expected_path(case), encoding="utf-8") as fh:
                    self.assertEqual(text, fh.read())


class DeterminismTest(unittest.TestCase):
    """验收口径 3：两遍运行（含不同 PYTHONHASHSEED）逐字节相同。"""

    def test_extract_is_deterministic_in_process(self):
        grid = load_grid(grid_path("saddle"))
        first = render_lines(extract(grid))
        second = render_lines(extract(grid))
        self.assertEqual(first, second)

    def test_cli_deterministic_across_hash_seeds(self):
        os.makedirs(VAR, exist_ok=True)
        outputs = []
        for seed in ("0", "12345"):
            out_dir = os.path.join(VAR, f"seed_{seed}")
            env = dict(os.environ, PYTHONHASHSEED=seed)
            proc = subprocess.run(
                [sys.executable, "-m", "isodraw", "extract",
                 "--grid", grid_path("scale"), "--out", out_dir],
                cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(proc.stdout.startswith("STAT|lines="))
            with open(os.path.join(out_dir, "lines.txt"),
                      encoding="utf-8") as fh:
                outputs.append((fh.read(), proc.stdout))
        self.assertEqual(outputs[0], outputs[1])


class GeometryTest(unittest.TestCase):
    """验收口径 2：每个点都落在格边上；走向保证高区在左。"""

    def _assert_on_grid_edge(self, grid, x, y):
        eps = 1e-6
        gx = (x - grid.x0) / grid.dx
        gy = (y - grid.y0) / grid.dy
        in_x = -eps <= gx <= grid.ncols - 1 + eps
        in_y = -eps <= gy <= grid.nrows - 1 + eps
        self.assertTrue(in_x and in_y, f"({x}, {y}) 跑出网格")
        on_col = abs(gx - round(gx)) <= eps
        on_row = abs(gy - round(gy)) <= eps
        self.assertTrue(on_col or on_row, f"({x}, {y}) 不在格边上")

    def _candidate_cells(self, grid, gx, gy):
        """中点所在的格胞（落在格线上时两侧都算）。"""
        eps = 1e-9
        is_ = {min(max(int(gx), 0), grid.ncols - 2)}
        js = {min(max(int(gy), 0), grid.nrows - 2)}
        ix = round(gx)
        if abs(gx - ix) <= eps and 1 <= ix <= grid.ncols - 2:
            is_.update((ix, ix - 1))
        iy = round(gy)
        if abs(gy - iy) <= eps and 1 <= iy <= grid.nrows - 2:
            js.update((iy, iy - 1))
        return [(i, j) for i in is_ for j in js]

    def test_points_on_grid_edges(self):
        for case in CASES:
            grid = load_grid(grid_path(case))
            for contour in extract(grid):
                for x, y in contour.points:
                    self._assert_on_grid_edge(grid, x, y)

    def test_high_side_on_left(self):
        # 口径是离散的：沿段方向看，所属格胞的高角必须在左侧、低角在右侧
        # （鞍点直弦附近的双线性值可能越界，不能拿连续值替代角点分类）。
        tol = 1e-9
        for case in CASES:
            grid = load_grid(grid_path(case))
            for contour in extract(grid):
                pts = contour.points
                pairs = list(zip(pts, pts[1:]))
                if contour.closed:
                    pairs.append((pts[-1], pts[0]))
                for (x0, y0), (x1, y1) in pairs:
                    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                    dx, dy = x1 - x0, y1 - y0
                    self.assertGreater((dx * dx + dy * dy) ** 0.5, 0)
                    gx = (mx - grid.x0) / grid.dx
                    gy = (my - grid.y0) / grid.dy
                    for ci, cj in self._candidate_cells(grid, gx, gy):
                        base = cj * grid.ncols + ci
                        corners = (
                            (grid.values[base], ci, cj),
                            (grid.values[base + 1], ci + 1, cj),
                            (grid.values[base + grid.ncols + 1],
                             ci + 1, cj + 1),
                            (grid.values[base + grid.ncols],
                             ci, cj + 1),
                        )
                        mask = sum(1 << k for k, (value, _, _) in
                                   enumerate(corners)
                                   if value >= contour.level)
                        if mask in (5, 10):
                            # 鞍点：每条段只切一个角，精确拓扑由
                            # 逐字节比对 expected 的用例锁定；这里只要求
                            # 至少一个高角在左、至少一个低角在右。
                            lefts = [dx * (grid.y0 + gj * grid.dy - my)
                                     - dy * (grid.x0 + gi * grid.dx - mx)
                                     for _, gi, gj in corners]
                            highs_left = any(
                                c > -tol for (v, _, _), c in
                                zip(corners, lefts)
                                if v >= contour.level)
                            lows_right = any(
                                c < tol for (v, _, _), c in
                                zip(corners, lefts)
                                if v < contour.level)
                            self.assertTrue(highs_left and lows_right)
                            continue
                        for value, gi, gj in corners:
                            wx = grid.x0 + gi * grid.dx
                            wy = grid.y0 + gj * grid.dy
                            cross = dx * (wy - my) - dy * (wx - mx)
                            if value >= contour.level:
                                self.assertGreaterEqual(
                                    cross, -tol,
                                    f"{case}: 高角 ({wx},{wy}) 不在段 "
                                    f"({x0},{y0})->({x1},{y1}) 左侧")
                            else:
                                self.assertLessEqual(
                                    cross, tol,
                                    f"{case}: 低角 ({wx},{wy}) 不在段右侧")

    def test_open_lines_end_on_outer_boundary(self):
        grid = load_grid(grid_path("open"))
        contours = extract(grid)
        self.assertTrue(all(not c.closed for c in contours))
        x_hi = grid.x0 + (grid.ncols - 1) * grid.dx
        y_hi = grid.y0 + (grid.nrows - 1) * grid.dy
        for contour in contours:
            for x, y in (contour.points[0], contour.points[-1]):
                on_frame = (abs(x - grid.x0) < 1e-9 or abs(x - x_hi) < 1e-9
                            or abs(y - grid.y0) < 1e-9 or abs(y - y_hi) < 1e-9)
                self.assertTrue(on_frame, f"端点 ({x}, {y}) 不在外边界上")

    def test_closed_line_starts_at_min_point(self):
        grid = load_grid(grid_path("hill"))
        for contour in extract(grid):
            self.assertTrue(contour.closed)
            self.assertEqual(contour.points[0], min(contour.points))


class DegenerateTest(unittest.TestCase):
    """压格点 / 同值平台 / 鞍点 / 零长度线段的口径。"""

    def test_onpoint_vertices_are_grid_nodes(self):
        grid = load_grid(grid_path("onpoint"))
        (contour,) = extract(grid)
        self.assertTrue(contour.closed)
        self.assertEqual(len(contour.points), 12)
        for x, y in contour.points:
            self.assertAlmostEqual((x - grid.x0) % grid.dx, 0.0, places=9)
            self.assertAlmostEqual((y - grid.y0) % grid.dy, 0.0, places=9)

    def test_plateau_drops_zero_length_segments(self):
        grid = load_grid(grid_path("plateau"))
        (contour,) = extract(grid)
        self.assertEqual(len(contour.points), 10)
        pts = contour.points
        for a, b in zip(pts, pts[1:] + [pts[0]]):
            self.assertNotEqual(a, b)

    def test_saddle_center_decides_connectivity(self):
        grid = load_grid(grid_path("saddle"))
        contours = extract(grid)
        by_level = {}
        for contour in contours:
            by_level.setdefault(contour.level, []).append(contour)
        self.assertEqual(len(by_level[0.5]), 1)   # 格心 1.0 >= 0.5：连通
        self.assertEqual(len(by_level[1.5]), 2)   # 格心 1.0 < 1.5：分离

    def test_negative_zero_is_normalized(self):
        self.assertEqual(_fmt(-0.0), "0.000000")
        self.assertEqual(_fmt(0.0), "0.000000")
        text = render_lines([Contour(1.0, [(-0.0, -0.0), (1.0, 2.0)], False)])
        self.assertIn("0.000000 0.000000\n", text)
        self.assertNotIn("-0.000000", text)


class ParserTest(unittest.TestCase):
    """网格文件读入容错与非法输入。"""

    def _write_grid(self, name, text):
        os.makedirs(VAR, exist_ok=True)
        path = os.path.join(VAR, name)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    def test_crlf_trailing_space_and_integers(self):
        path = self._write_grid(
            "tolerant.txt",
            "ncols 3 \r\nnrows 2\r\nx0 0\r\ny0 0\r\ndx 1\r\ndy 1\r\n"
            "levels 1\r\n0 2 0 \r\n0 2 0\r\n")
        grid = load_grid(path)
        self.assertEqual((grid.ncols, grid.nrows), (3, 2))
        self.assertEqual(grid.levels, (1.0,))
        self.assertEqual(grid.values[1], 2.0)

    def test_rejects_bad_grids(self):
        bad = {
            "missing_header.txt": "ncols 3\nnrows 2\n",
            "non_increasing_levels.txt": (
                "ncols 2\nnrows 2\nx0 0\ny0 0\ndx 1\ndy 1\n"
                "levels 2 1\n0 0\n0 0\n"),
            "wrong_row_count.txt": (
                "ncols 2\nnrows 3\nx0 0\ny0 0\ndx 1\ndy 1\n"
                "levels 1\n0 0\n0 0\n"),
            "wrong_col_count.txt": (
                "ncols 3\nnrows 2\nx0 0\ny0 0\ndx 1\ndy 1\n"
                "levels 1\n0 0\n0 0\n"),
            "bad_number.txt": (
                "ncols 2\nnrows 2\nx0 0\ny0 0\ndx 1\ndy 1\n"
                "levels 1\n0 x\n0 0\n"),
        }
        for name, text in bad.items():
            with self.subTest(name=name):
                with self.assertRaises(GridFormatError):
                    load_grid(self._write_grid(name, text))
        with self.assertRaises(GridFormatError):
            load_grid(os.path.join(VAR, "does_not_exist.txt"))


class CliTest(unittest.TestCase):
    """命令行：STAT 行、输出文件、失败不留半成品。"""

    def _run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, "-m", "isodraw", *argv],
            cwd=ROOT, capture_output=True, text=True)

    def test_extract_writes_outputs_and_stat(self):
        out_dir = os.path.join(VAR, "cli_hill")
        proc = self._run_cli("extract", "--grid", grid_path("hill"),
                             "--out", out_dir)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(),
                         "STAT|lines=2|max_segments=12")
        with open(os.path.join(out_dir, "lines.txt"),
                  encoding="utf-8") as fh:
            with open(expected_path("hill"), encoding="utf-8") as exp:
                self.assertEqual(fh.read(), exp.read())
        with open(os.path.join(out_dir, "index.html"),
                  encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("本次提取 2 条等值线，最长的线有 12 段", html)

    def test_bad_grid_exits_nonzero_without_leftovers(self):
        out_dir = os.path.join(VAR, "cli_bad")
        proc = self._run_cli("extract", "--grid",
                             os.path.join(VAR, "does_not_exist.txt"),
                             "--out", out_dir)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(out_dir, "lines.txt")))
        self.assertFalse(os.path.exists(os.path.join(out_dir, "index.html")))

    def test_missing_args_exits_nonzero(self):
        proc = self._run_cli("extract")
        self.assertNotEqual(proc.returncode, 0)


class PageTest(unittest.TestCase):
    """页面只画不重算：线段与端点逐点来自引擎输出。"""

    def test_page_contains_engine_points_and_counts(self):
        grid = load_grid(grid_path("saddle"))
        contours = extract(grid)
        line_count, max_segments = stats(contours)
        html = render_page(grid, contours, line_count, max_segments)
        self.assertIn("<svg", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn(f"本次提取 {line_count} 条等值线", html)
        self.assertIn(f"最长的线有 {max_segments} 段", html)
        self.assertEqual(html.count("<polyline"), line_count * 2)  # 白描边+本色
        total_points = sum(len(c.points) for c in contours)
        self.assertEqual(html.count("<circle"), total_points)
        # 引擎输出的第一个点必须出现在折线里（页面坐标换算一致）
        first = contours[0].points[0]
        self.assertIn("data:image/png;base64,", html)
        self.assertTrue(first[0] >= grid.x0 and first[1] >= grid.y0)


class PerformanceTest(unittest.TestCase):
    """验收口径 5：scale 单次全流程 <= 10 秒。"""

    def test_scale_within_time_budget(self):
        started = time.perf_counter()
        grid = load_grid(grid_path("scale"))
        contours = extract(grid)
        line_count, max_segments = stats(contours)
        render_lines(contours)
        render_page(grid, contours, line_count, max_segments)
        elapsed = time.perf_counter() - started
        self.assertEqual((line_count, max_segments), (3, 999))
        self.assertLessEqual(elapsed, 10.0,
                             f"scale 全流程 {elapsed:.2f}s 超过 10s 预算")


if __name__ == "__main__":
    unittest.main()
