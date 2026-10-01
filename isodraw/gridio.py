"""网格文件与结果文件的读写。

网格文件：固定 7 行头（ncols/nrows/x0/y0/dx/dy/levels）加 nrows 行数值，
UTF-8、LF；读入容错行尾空白、CRLF 与整数值。结果文件 lines.txt 的格式
见 README 4.2：一条线一块，字段之间一个空格，坐标 6 位小数。
"""

import os
from array import array
from dataclasses import dataclass

from .engine import Contour


class GridFormatError(ValueError):
    """网格文件内容不合法。"""


@dataclass(frozen=True)
class Grid:
    ncols: int
    nrows: int
    x0: float
    y0: float
    dx: float
    dy: float
    values: tuple  # 按行展开：values[j*ncols + i]
    levels: tuple


def _parse_int(text, what):
    try:
        value = int(text)
    except ValueError:
        raise GridFormatError(f"{what} 不是整数: {text!r}")
    return value


def _parse_float(text, what):
    try:
        value = float(text)
    except ValueError:
        raise GridFormatError(f"{what} 不是数值: {text!r}")
    return value


def load_grid(path):
    """读取网格文件，返回 Grid；内容不合法时抛 GridFormatError。"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        raise GridFormatError(f"读不了网格文件 {path}: {exc}")
    if len(lines) < 7:
        raise GridFormatError("网格文件不足 7 行头")

    header = {}
    for line in lines[:7]:
        parts = line.split()
        if len(parts) < 2:
            raise GridFormatError(f"头部行缺字段: {line!r}")
        header[parts[0]] = parts[1:]
    for key in ("ncols", "nrows", "x0", "y0", "dx", "dy", "levels"):
        if key not in header:
            raise GridFormatError(f"头部缺少字段: {key}")

    ncols = _parse_int(header["ncols"][0], "ncols")
    nrows = _parse_int(header["nrows"][0], "nrows")
    x0 = _parse_float(header["x0"][0], "x0")
    y0 = _parse_float(header["y0"][0], "y0")
    dx = _parse_float(header["dx"][0], "dx")
    dy = _parse_float(header["dy"][0], "dy")
    if ncols < 2 or nrows < 2:
        raise GridFormatError("ncols 与 nrows 都要 >= 2")
    if dx <= 0.0 or dy <= 0.0:
        raise GridFormatError("dx 与 dy 都要 > 0")

    level_fields = header["levels"]
    if not 1 <= len(level_fields) <= 8:
        raise GridFormatError("levels 需要 1..8 个等值面")
    levels = tuple(_parse_float(text, "levels") for text in level_fields)
    if any(levels[k] >= levels[k + 1] for k in range(len(levels) - 1)):
        raise GridFormatError("levels 必须严格递增")

    rows = lines[7:]
    if len(rows) != nrows:
        raise GridFormatError(f"数值行数 {len(rows)} 与 nrows {nrows} 不一致")
    values = array("d")
    for j, line in enumerate(rows):
        fields = line.split()
        if len(fields) != ncols:
            raise GridFormatError(
                f"第 {j} 行有 {len(fields)} 个值，应为 {ncols} 个")
        for text in fields:
            values.append(_parse_float(text, f"第 {j} 行的数值"))
    return Grid(ncols, nrows, x0, y0, dx, dy, values, levels)


def _fmt(value):
    """6 位小数，-0.000000 归一为 0.000000。"""
    text = f"{value:.6f}"
    return "0.000000" if text == "-0.000000" else text


def render_lines(contours):
    """把 Contour 列表渲染成 lines.txt 的文本。"""
    chunks = []
    for contour in contours:
        kind = "CLOSED" if contour.closed else "OPEN"
        chunks.append(
            f"LINE {_fmt(contour.level)} {len(contour.points)} {kind}\n")
        for x, y in contour.points:
            chunks.append(f"{_fmt(x)} {_fmt(y)}\n")
    return "".join(chunks)


def _atomic_write(path, text):
    """先写临时文件再替换，失败不留半成品。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def write_lines(contours, path):
    _atomic_write(path, render_lines(contours))


def write_page(html, path):
    _atomic_write(path, html)


__all__ = [
    "Contour",
    "Grid",
    "GridFormatError",
    "load_grid",
    "render_lines",
    "write_lines",
    "write_page",
]
