"""等值线图页面：原生 HTML + 内联 SVG，无外部资源，file:// 直接打开。

网格按值铺底色（一格点一像素的 PNG，base64 内嵌），等值线叠在上面，
每个顶点画小点、开放线端点画大点；底部标注线条数与最长线的段数。
页面只画不重算：所有线段与端点逐点取自引擎结果。
"""

from __future__ import annotations

import base64
import html
import struct
import zlib

from .report import fmt6, max_segments

# 每个等值面一种描边色（levels 至多 8 个）。
_PALETTE = (
    "#c22f2f", "#1f6fb4", "#2c8c46", "#7a4fa3",
    "#d9822b", "#1299a8", "#8c5a46", "#c24b9a",
)

# 底色色带：低值深蓝 -> 高值深红。
_STOPS = (
    (0.00, (43, 70, 137)),
    (0.25, (45, 134, 171)),
    (0.50, (83, 168, 105)),
    (0.75, (231, 199, 95)),
    (1.00, (201, 58, 50)),
)


def _heat_color(value, vmin, vmax):
    if vmax > vmin:
        t = (value - vmin) / (vmax - vmin)
    else:
        t = 0.5
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    for k in range(1, len(_STOPS)):
        t1, c1 = _STOPS[k]
        if t <= t1:
            t0, c0 = _STOPS[k - 1]
            f = (t - t0) / (t1 - t0)
            return tuple(round(a + f * (b - a)) for a, b in zip(c0, c1))
    return _STOPS[-1][1]


def _png_rgb(width, height, rows):
    """rows：height 行、每行 width*3 字节的 RGB。标准库手写 PNG。"""
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter: None
        raw.extend(row)

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _heatmap_uri(grid):
    ncols, nrows = grid.ncols, grid.nrows
    vmin = min(min(row) for row in grid.values)
    vmax = max(max(row) for row in grid.values)
    rows = []
    for j in range(nrows - 1, -1, -1):  # PNG 首行在上，对应最大的 j
        row = bytearray()
        for value in grid.values[j]:
            row.extend(_heat_color(value, vmin, vmax))
        rows.append(bytes(row))
    png = _png_rgb(ncols, nrows, rows)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii"), vmin, vmax


def render_html(grid, contours, title="isodraw") -> str:
    xmin, xmax = grid.xmin, grid.xmax
    ymin, ymax = grid.ymin, grid.ymax
    uri, vmin, vmax = _heatmap_uri(grid)

    margin = 56
    plot_w = 848
    plot_h = max(1, round(plot_w * (ymax - ymin) / (xmax - xmin)))
    if plot_h > 640:
        plot_h = 640
        plot_w = max(1, round(plot_h * (xmax - xmin) / (ymax - ymin)))
    width = plot_w + 2 * margin
    height = plot_h + 2 * margin

    def px(x):
        return margin + (x - xmin) / (xmax - xmin) * plot_w

    def py(y):
        return margin + (ymax - y) / (ymax - ymin) * plot_h

    def num(v):
        return f"{v:.2f}"

    level_color = {}
    for idx, level in enumerate(grid.levels):
        level_color[level] = _PALETTE[idx % len(_PALETTE)]

    shapes = []
    for c in contours:
        color = level_color[c.level]
        coords = [(px(x), py(y)) for x, y in c.points]
        pts = " ".join(f"{num(a)},{num(b)}" for a, b in coords)
        if c.closed:
            shapes.append(
                f'<polygon points="{pts}" fill="none" stroke="{color}" '
                f'stroke-width="1.6" stroke-linejoin="round"/>'
            )
        else:
            shapes.append(
                f'<polyline points="{pts}" fill="none" stroke="{color}" '
                f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        # 顶点小点
        for a, b in coords:
            shapes.append(
                f'<circle cx="{num(a)}" cy="{num(b)}" r="2.2" '
                f'fill="#ffffff" stroke="{color}" stroke-width="1.1"/>'
            )
        # 开放线的两个端点画大点
        if not c.closed:
            for a, b in (coords[0], coords[-1]):
                shapes.append(
                    f'<circle cx="{num(a)}" cy="{num(b)}" r="4.2" '
                    f'fill="{color}" stroke="#1a1a1a" stroke-width="1.2"/>'
                )

    legend_items = []
    for level in grid.levels:
        color = level_color[level]
        count = sum(1 for c in contours if c.level == level)
        legend_items.append(
            f'<span class="legend-item"><span class="swatch" '
            f'style="background:{color}"></span>level {fmt6(level)}'
            f'（{count} 条）</span>'
        )

    stat = f"lines={len(contours)} | max_segments={max_segments(contours)}"
    esc_title = html.escape(title)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>等值线提取 - {esc_title}</title>
<style>
  body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; margin: 24px;
         background: #f5f6f8; color: #222; }}
  h1 {{ font-size: 20px; margin: 0 0 6px; }}
  .meta {{ color: #555; font-size: 13px; margin: 2px 0; }}
  .plot {{ background: #fff; border: 1px solid #d8dbe0; border-radius: 6px;
           display: inline-block; padding: 12px; margin-top: 10px; }}
  .legend {{ margin-top: 8px; font-size: 13px; }}
  .legend-item {{ margin-right: 16px; white-space: nowrap; }}
  .swatch {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px;
             margin-right: 4px; vertical-align: -1px; }}
  .stat {{ margin-top: 10px; font-size: 15px; font-weight: 600;
           font-family: Consolas, monospace; }}
</style>
</head>
<body>
<h1>等值线提取结果</h1>
<p class="meta">网格 {esc_title}：{grid.ncols}×{grid.nrows} 格点，
x ∈ [{fmt6(xmin)}, {fmt6(xmax)}]，y ∈ [{fmt6(ymin)}, {fmt6(ymax)}]，
取值 ∈ [{fmt6(vmin)}, {fmt6(vmax)}]</p>
<div class="plot">
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="等值线图">
<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
<image href="{uri}" x="{margin}" y="{margin}" width="{plot_w}" height="{plot_h}"
       style="image-rendering:pixelated"/>
<rect x="{margin}" y="{margin}" width="{plot_w}" height="{plot_h}"
      fill="none" stroke="#888" stroke-width="1"/>
{chr(10).join(shapes)}
</svg>
<div class="legend">{''.join(legend_items)}</div>
</div>
<p class="stat">{stat}</p>
</body>
</html>
"""
