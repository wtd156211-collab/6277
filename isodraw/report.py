"""文本结果（lines.txt）与统计行。"""

from __future__ import annotations


def fmt6(value: float) -> str:
    """6 位小数；-0.000000 统一写成 0.000000。"""
    text = f"{value:.6f}"
    return "0.000000" if text == "-0.000000" else text


def segment_count(contour) -> int:
    return len(contour.points) if contour.closed else len(contour.points) - 1


def max_segments(contours) -> int:
    if not contours:
        return 0
    return max(segment_count(c) for c in contours)


def format_lines(contours) -> str:
    """lines.txt 全文；末行带换行。"""
    parts = []
    for c in contours:
        tag = "CLOSED" if c.closed else "OPEN"
        parts.append(f"LINE {fmt6(c.level)} {len(c.points)} {tag}")
        parts.extend(f"{fmt6(x)} {fmt6(y)}" for x, y in c.points)
    return "".join(line + "\n" for line in parts)


def stat_line(contours) -> str:
    return f"STAT|lines={len(contours)}|max_segments={max_segments(contours)}"
