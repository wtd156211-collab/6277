"""命令行入口：python -m isodraw extract --grid <网格文件> --out <输出目录>"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .engine import extract
from .grid import GridError, load_grid
from .page import render_html
from .report import format_lines, stat_line


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="isodraw", description="等值线提取（标准库实现）"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_extract = sub.add_parser("extract", help="从网格文件提取等值线")
    p_extract.add_argument("--grid", required=True, help="网格文件路径")
    p_extract.add_argument("--out", required=True, help="输出目录")
    args = parser.parse_args(argv)

    try:
        grid = load_grid(args.grid)
    except OSError as exc:
        print(f"error: 读不了网格文件: {exc}", file=sys.stderr)
        return 2
    except GridError as exc:
        print(f"error: 网格不合法: {exc}", file=sys.stderr)
        return 2

    contours = extract(grid)
    lines_text = format_lines(contours)
    page = render_html(grid, contours, title=Path(args.grid).name)

    out_dir = Path(args.out)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(out_dir / "lines.txt", lines_text)
        _atomic_write(out_dir / "index.html", page)
    except OSError as exc:
        print(f"error: 写输出失败: {exc}", file=sys.stderr)
        return 2

    print(stat_line(contours))
    return 0
