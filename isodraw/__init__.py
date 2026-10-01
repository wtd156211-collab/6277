"""isodraw：正交均匀网格的等值线提取（纯标准库）。

用法：
    from isodraw import load_grid, extract, stats
    grid = load_grid("samples/grids/hill.txt")
    contours = extract(grid)
    n_lines, max_segments = stats(contours)
"""

from .engine import Contour, extract, stats
from .gridio import Grid, GridFormatError, load_grid, render_lines, write_lines
from .page import render_page

__all__ = [
    "Contour",
    "Grid",
    "GridFormatError",
    "extract",
    "load_grid",
    "render_lines",
    "render_page",
    "stats",
    "write_lines",
]

__version__ = "1.0.0"
