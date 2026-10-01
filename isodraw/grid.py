"""网格文件读取与校验。格式见 README 第四节。"""

from __future__ import annotations

from dataclasses import dataclass


class GridError(ValueError):
    """网格文件不合法。"""


@dataclass
class Grid:
    ncols: int
    nrows: int
    x0: float
    y0: float
    dx: float
    dy: float
    values: list  # values[j][i]，j 从 0 到 nrows-1
    levels: list

    @property
    def xmin(self) -> float:
        return self.x0

    @property
    def xmax(self) -> float:
        return self.x0 + (self.ncols - 1) * self.dx

    @property
    def ymin(self) -> float:
        return self.y0

    @property
    def ymax(self) -> float:
        return self.y0 + (self.nrows - 1) * self.dy


_HEADER_KEYS = ("ncols", "nrows", "x0", "y0", "dx", "dy", "levels")


def parse_grid(text: str, source: str = "<grid>") -> Grid:
    def fail(msg: str) -> GridError:
        return GridError(f"{source}: {msg}")

    rows = [ln.strip() for ln in text.splitlines()]
    while rows and not rows[-1]:
        rows.pop()
    if len(rows) < 8:
        raise fail("文件太短，至少需要 7 行头和 1 行数据")

    header = {}
    for ln in rows[:7]:
        parts = ln.split()
        if len(parts) < 2:
            raise fail(f"头部行缺字段: {ln!r}")
        header[parts[0]] = parts[1:]
    for key in _HEADER_KEYS:
        if key not in header:
            raise fail(f"头部缺少 {key!r} 行")

    try:
        ncols = int(header["ncols"][0])
        nrows = int(header["nrows"][0])
    except ValueError:
        raise fail("ncols/nrows 必须是整数")
    try:
        x0 = float(header["x0"][0])
        y0 = float(header["y0"][0])
        dx = float(header["dx"][0])
        dy = float(header["dy"][0])
    except ValueError:
        raise fail("x0/y0/dx/dy 必须是数值")
    try:
        levels = [float(tok) for tok in header["levels"]]
    except ValueError:
        raise fail("levels 必须是数值列表")

    if ncols < 2 or nrows < 2:
        raise fail("ncols 和 nrows 都必须 >= 2")
    if not (dx > 0.0 and dy > 0.0):
        raise fail("dx 和 dy 必须为正")
    if not (1 <= len(levels) <= 8):
        raise fail("levels 个数必须在 1..8 之间")
    for a, b in zip(levels, levels[1:]):
        if not a < b:
            raise fail("levels 必须严格递增")

    body = rows[7:]
    if len(body) != nrows:
        raise fail(f"数值行数 {len(body)} 与 nrows {nrows} 不符")
    values = []
    for j, ln in enumerate(body):
        parts = ln.split()
        if len(parts) != ncols:
            raise fail(f"第 {j} 行有 {len(parts)} 个数，应为 {ncols} 个")
        try:
            values.append([float(tok) for tok in parts])
        except ValueError:
            raise fail(f"第 {j} 行含非数值")

    return Grid(ncols, nrows, x0, y0, dx, dy, values, levels)


def load_grid(path) -> Grid:
    with open(path, "r", encoding="utf-8", newline=None) as fh:
        text = fh.read()
    return parse_grid(text, source=str(path))
