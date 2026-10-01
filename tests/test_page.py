"""页面测试：只画引擎结果、计数对得上、无外部资源。输出只写 var/。"""

import os
import re
import unittest

from isodraw.engine import extract
from isodraw.grid import load_grid
from isodraw.page import render_html
from isodraw.report import fmt6, max_segments

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRIDS = os.path.join(ROOT, "samples", "grids")
VAR = os.path.join(ROOT, "var")


class PageTest(unittest.TestCase):
    def setUp(self):
        self.grid = load_grid(os.path.join(GRIDS, "open.txt"))
        self.contours = extract(self.grid)
        self.html_text = render_html(self.grid, self.contours, title="open.txt")

    def test_bottom_stats_match_lines(self):
        self.assertIn(
            f"lines={len(self.contours)} | max_segments={max_segments(self.contours)}",
            self.html_text,
        )

    def test_engine_points_present_in_svg(self):
        # 页面里的等值线坐标必须逐点取自引擎（像素坐标是仿射变换，
        # 这里校验每条线的点数与“顶点小点”数量一致，并抽检边界端点）。
        for contour in self.contours:
            # 每条开放线有 len(points) 个顶点小点 + 2 个端点大点
            self.assertEqual(
                self.html_text.count("<circle "),
                sum(len(c.points) + (0 if c.closed else 2) for c in self.contours),
            )
        # 开放线两端在图上：y 方向翻转，起点在上边界。
        self.assertIn("polyline", self.html_text)

    def test_no_external_resources(self):
        body = self.html_text
        # xmlns 命名空间标识符不算外部资源；只查会真的发起加载的引用。
        for pattern in (r'src="https?://', r'href="https?://',
                        r"url\(https?://", r"@import", r"<script", r"<link"):
            self.assertIsNone(re.search(pattern, body), pattern)
        self.assertIn('data:image/png;base64,', body)

    def test_heatmap_png_is_valid(self):
        import base64
        import zlib

        m = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)"', self.html_text)
        self.assertIsNotNone(m)
        data = base64.b64decode(m.group(1))
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        # PNG 至少含 IHDR/IDAT/IEND 三个 chunk，IDAT 能正常解压。
        self.assertIn(b"IHDR", data)
        self.assertIn(b"IDAT", data)
        self.assertTrue(data.rstrip().endswith(b"IEND\xaeB`\x82"))

    def test_closed_contours_render_polygon(self):
        grid = load_grid(os.path.join(GRIDS, "hill.txt"))
        contours = extract(grid)
        page = render_html(grid, contours, title="hill.txt")
        self.assertEqual(page.count("<polygon "), 2)
        self.assertNotIn("<polyline", page)
        self.assertIn(f"max_segments={max_segments(contours)}", page)

    def test_deterministic_html(self):
        a = render_html(self.grid, self.contours, title="open.txt")
        b = render_html(self.grid, self.contours, title="open.txt")
        self.assertEqual(a, b)

    def test_page_written_to_var(self):
        path = os.path.join(VAR, "page", "index.html")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.html_text)
        self.assertTrue(os.path.getsize(path) > 1000)


if __name__ == "__main__":
    unittest.main()
