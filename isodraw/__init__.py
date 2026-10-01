"""等值线提取库（标准库实现）。"""

from .engine import Contour, extract
from .grid import Grid, GridError, load_grid, parse_grid
from .report import fmt6, format_lines, max_segments, segment_count, stat_line
from .page import render_html

__all__ = [
    "Contour",
    "Grid",
    "GridError",
    "extract",
    "load_grid",
    "parse_grid",
    "fmt6",
    "format_lines",
    "max_segments",
    "segment_count",
    "stat_line",
    "render_html",
]
