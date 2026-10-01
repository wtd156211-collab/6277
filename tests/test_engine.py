"""引擎单元测试：插值、方向、鞍点、压格点、退化、排序、确定性。"""

import unittest

from isodraw.engine import Contour, extract
from isodraw.grid import Grid
from isodraw.report import fmt6, format_lines


def make_grid(values, levels, dx=1.0, dy=1.0, x0=0.0, y0=0.0):
    nrows = len(values)
    ncols = len(values[0])
    return Grid(ncols, nrows, x0, y0, dx, dy, [list(r) for r in values], list(levels))


class Fmt6Test(unittest.TestCase):
    def test_negative_zero(self):
        self.assertEqual(fmt6(-0.0), "0.000000")
        self.assertEqual(fmt6(-1e-9), "0.000000")
        self.assertEqual(fmt6(1.0), "1.000000")


class SingleCellTest(unittest.TestCase):
    def test_single_high_corner_is_open_segment(self):
        # 2x2 格点，仅 BL 高：线段从底边到左边，高在左，两端都在边界 -> OPEN。
        grid = make_grid([[2.0, 0.0], [0.0, 0.0]], [1.0])
        contours = extract(grid)
        self.assertEqual(len(contours), 1)
        c = contours[0]
        self.assertFalse(c.closed)
        self.assertEqual(len(c.points), 2)
        # B -> L：起点在底边 (0.5, 0)，终点在左边 (0, 0.5)
        self.assertEqual(c.points, [(0.5, 0.0), (0.0, 0.5)])

    def test_single_high_corner_other_corner_direction(self):
        # 仅 TR 高：T -> R，高角(右上)在左。
        grid = make_grid([[0.0, 0.0], [0.0, 2.0]], [1.0])
        contours = extract(grid)
        self.assertEqual(len(contours), 1)
        self.assertEqual(contours[0].points, [(0.5, 1.0), (1.0, 0.5)])

    def test_level_equals_value_is_high(self):
        # 三个 == level 的格点组成 L 形高区：若把等于当成低就一条线都出不来；
        # 按口径等于算高，得一条 2 点开放线，端点就是格点本身。
        grid = make_grid(
            [[1.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
            [1.0],
        )
        contours = extract(grid)
        self.assertEqual(len(contours), 1)
        self.assertEqual(contours[0].points, [(1.0, 0.0), (0.0, 1.0)])
        self.assertFalse(contours[0].closed)


class DegenerateTest(unittest.TestCase):
    def test_isolated_level_vertex_drops_zero_length(self):
        # 角值 == level 且四邻都低时，角胞的线段两端都是同一个格点，丢弃。
        # 3x3：中心 == level，外圈都低 -> 四个角胞各一条零长线段，无线条。
        grid = make_grid(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
            [1.0],
        )
        self.assertEqual(extract(grid), [])


class SaddleTest(unittest.TestCase):
    def _diag_high(self):
        # 3x3：BL 与 TR 角高（格胞对角两高）
        return make_grid([[2.0, 0.0], [0.0, 2.0]], [1.0])

    def test_saddle_center_high_joins_high_corners(self):
        # 四角 2,0,0,2，格心 c=1.0 >= level -> 高角连通，圈两个低角。
        grid = self._diag_high()
        contours = extract(grid)
        self.assertEqual(len(contours), 2)
        for c in contours:
            self.assertFalse(c.closed)  # 端点都落在外边界
            self.assertEqual(len(c.points), 2)
        # 圈 BR（低）：B -> R；圈 TL（低）：T -> L
        all_segs = {tuple(c.points) for c in contours}
        self.assertIn(((0.5, 0.0), (1.0, 0.5)), all_segs)
        self.assertIn(((0.5, 1.0), (0.0, 0.5)), all_segs)

    def test_saddle_center_low_separates(self):
        # 同布局 level 1.5：格心 1.0 < level -> 高角孤立，圈高角。
        grid = make_grid([[2.0, 0.0], [0.0, 2.0]], [1.5])
        contours = extract(grid)
        all_segs = {tuple(c.points) for c in contours}
        # 圈 BL（高）：B -> L；圈 TR（高）：T -> R
        self.assertIn(((0.25, 0.0), (0.0, 0.25)), all_segs)
        self.assertIn(((0.75, 1.0), (1.0, 0.75)), all_segs)


class ClosedLoopTest(unittest.TestCase):
    def test_closed_line_starts_at_lexicographic_minimum(self):
        # 5x5，中心高：出一条闭合线，起点必须是字典序最小点。
        grid = make_grid(
            [
                [0, 0, 0, 0, 0],
                [0, 1, 1, 1, 0],
                [0, 1, 3, 1, 0],
                [0, 1, 1, 1, 0],
                [0, 0, 0, 0, 0],
            ],
            [0.5],
        )
        contours = extract(grid)
        self.assertEqual(len(contours), 1)
        c = contours[0]
        self.assertTrue(c.closed)
        first = c.points[0]
        self.assertEqual(first, min(c.points, key=lambda p: (round(p[0], 6), round(p[1], 6))))


class SortingTest(unittest.TestCase):
    def test_levels_sorted_ascending(self):
        # 两个高丘，两个 level 各出 1 条：先 level 小的。
        values = [
            [0, 0, 0, 0, 0],
            [0, 3, 0, 0, 0],
            [0, 0, 0, 3, 0],
            [0, 0, 0, 0, 0],
        ]
        grid = make_grid(values, [1.0, 2.0])
        contours = extract(grid)
        self.assertEqual([c.level for c in contours], [1.0, 1.0, 2.0, 2.0])
        # 同 level 内按首点字典序：左丘首点 x 更小，排前面
        lv1 = [c for c in contours if c.level == 1.0]
        self.assertLess(lv1[0].points[0], lv1[1].points[0])


class DeterminismTest(unittest.TestCase):
    def test_twice_identical(self):
        grid = make_grid(
            [
                [0, 0, 2, 2],
                [0, 0, 2, 2],
                [2, 2, 0, 0],
                [2, 2, 0, 0],
            ],
            [0.5, 1.5],
        )
        text1 = format_lines(extract(grid))
        text2 = format_lines(extract(grid))
        self.assertEqual(text1, text2)
        self.assertTrue(text1.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
