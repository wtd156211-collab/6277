"""命令行入口：

    python -m isodraw extract --grid <网格文件> --out <输出目录>

写出 <输出目录>/lines.txt 与 <输出目录>/index.html，往 stdout 打一行
STAT|lines=<条数>|max_segments=<最长线的段数>；参数或网格不合法时
非 0 退出，不留半成品。
"""

import argparse
import os
import sys

from .engine import extract, stats
from .gridio import GridFormatError, load_grid, write_lines, write_page
from .page import render_page


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="isodraw", description="正交均匀网格的等值线提取")
    sub = parser.add_subparsers(dest="command", required=True)
    extract_parser = sub.add_parser("extract", help="提取等值线并写出结果")
    extract_parser.add_argument("--grid", required=True, help="网格文件路径")
    extract_parser.add_argument("--out", required=True, help="输出目录")
    return parser


def _run_extract(grid_path, out_dir):
    grid = load_grid(grid_path)
    contours = extract(grid)
    line_count, max_segments = stats(contours)
    html = render_page(grid, contours, line_count, max_segments)
    os.makedirs(out_dir, exist_ok=True)
    write_lines(contours, os.path.join(out_dir, "lines.txt"))
    write_page(html, os.path.join(out_dir, "index.html"))
    print(f"STAT|lines={line_count}|max_segments={max_segments}")
    return 0


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "extract":
        try:
            return _run_extract(args.grid, args.out)
        except GridFormatError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    parser.error("未知命令")
    return 2


if __name__ == "__main__":
    sys.exit(main())
