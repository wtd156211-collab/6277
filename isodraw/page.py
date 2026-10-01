"""等值线页面：原生 HTML + 内联 SVG，无外部资源。

网格按值铺底色（每格胞一个颜色，内联一张 PNG），等值线与端点逐点取自
引擎输出，页面只做绘制，不重新计算任何东西。
"""

import base64
import binascii
import struct
import zlib

# 几条线的配色（同一 level 同色）。
_PALETTE = ("#d62728", "#1f77b4", "#2ca02c", "#9467bd",
            "#ff7f0e", "#17becf", "#8c564b", "#e377c2")


def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    crc = binascii.crc32(tag + data) & 0xFFFFFFFF
    return out + struct.pack(">I", crc)


def _encode_png(width, height, rgb):
    """rgb 为逐行 RGB 三字节数据；返回整份 PNG 字节串。"""
    raw = bytearray()
    stride = width * 3
    for row in range(height):
        raw.append(0)  # 每行 filter type 0
        raw.extend(rgb[row * stride:(row + 1) * stride])
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR",
                  struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += _chunk(b"IEND", b"")
    return png


def _heatmap_rgb(grid):
    values = grid.values
    vmin = min(values)
    vmax = max(values)
    span = vmax - vmin
    # 渐变：深蓝 -> 米白 -> 暗红；常量场统一用米白。
    stops = ((0, (13, 52, 102)), (0.5, (245, 240, 225)), (1, (128, 24, 24)))

    def shade(u):
        u = 0.0 if u < 0.0 else 1.0 if u > 1.0 else u
        for k in range(2):
            u0, c0 = stops[k]
            u1, c1 = stops[k + 1]
            if u <= u1:
                f = (u - u0) / (u1 - u0)
                return tuple(c0[ch] + (c1[ch] - c0[ch]) * f for ch in range(3))
        return stops[2][1]

    lut = [shade(k / 255.0) for k in range(256)]
    ncols = grid.ncols
    nrows = grid.nrows
    rgb = bytearray((ncols - 1) * (nrows - 1) * 3)
    if span == 0.0:
        color = lut[128]
        rgb[::3] = bytes(int(color[0])) * (len(rgb) // 3)
        rgb[1::3] = bytes(int(color[1])) * (len(rgb) // 3)
        rgb[2::3] = bytes(int(color[2])) * (len(rgb) // 3)
    else:
        out = 0
        scale = 255.0 / span
        for j in range(nrows - 1):
            base = j * ncols
            for i in range(ncols - 1):
                v0 = values[base + i]
                v1 = values[base + i + 1]
                v2 = values[base + ncols + i]
                v3 = values[base + ncols + i + 1]
                u = ((v0 + v1 + v2 + v3) * 0.25 - vmin) * scale
                color = lut[0 if u <= 0.0 else 255 if u >= 255.0 else int(u)]
                rgb[out] = int(color[0])
                rgb[out + 1] = int(color[1])
                rgb[out + 2] = int(color[2])
                out += 3
    return _encode_png(ncols - 1, nrows - 1, rgb)


def render_page(grid, contours, line_count, max_segments):
    """生成自包含的 index.html 文本。"""
    width = grid.ncols - 1
    height = grid.nrows - 1

    margin_l, margin_r, margin_t, margin_b = 48, 24, 24, 56
    # 每格最多 4 像素，大图封顶；小网格保证可看。
    if width <= 400:
        cell = max(12.0, 900.0 / max(width, 1))
    else:
        cell = 4.0
    plot_w = width * cell
    plot_h = height * cell
    svg_w = margin_l + plot_w + margin_r
    svg_h = margin_t + plot_h + margin_b

    x_left = grid.x0
    x_right = grid.x0 + width * grid.dx
    y_bottom = grid.y0
    y_top = grid.y0 + height * grid.dy
    sx = plot_w / (grid.dx * width)
    sy = plot_h / (grid.dy * height)

    def px(x):
        return f"{margin_l + (x - x_left) * sx:.3f}"

    def py(y):
        return f"{margin_t + (y_top - y) * sy:.3f}"

    png_b64 = base64.b64encode(_heatmap_rgb(grid)).decode("ascii")
    parts = [
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n',
        "<title>isodraw 等值线</title>\n",
        "<style>body{font-family:Segoe UI,Helvetica,Arial,sans-serif;",
        "margin:20px;color:#222}svg{background:#fff;border:1px solid #bbb;",
        "max-width:100%;height:auto}.stat{font-size:16px;font-weight:600;",
        "margin:10px 2px}.legend{font-size:13px}.axis{font-size:12px;",
        "fill:#444}</style>\n</head>\n<body>\n",
        "<h2 style=\"margin:4px 0 12px\">等值线提取结果</h2>\n",
        f'<svg width="{svg_w:.0f}" height="{svg_h:.0f}" '
        f'viewBox="0 0 {svg_w:.0f} {svg_h:.0f}" role="img">\n',
        f'<image x="{margin_l}" y="{margin_t}" width="{plot_w:.3f}" '
        f'height="{plot_h:.3f}" preserveAspectRatio="none" '
        f'href="data:image/png;base64,{png_b64}"/>\n',
        f'<rect x="{margin_l}" y="{margin_t}" width="{plot_w:.3f}" '
        f'height="{plot_h:.3f}" fill="none" stroke="#333" stroke-width="1"/>\n',
    ]

    if width <= 60:
        for i in range(width + 1):
            gx = margin_l + i * cell
            parts.append(
                f'<line x1="{gx:.3f}" y1="{margin_t}" x2="{gx:.3f}" '
                f'y2="{margin_t + plot_h:.3f}" stroke="#00000022"/>\n')
        for j in range(height + 1):
            gy = margin_t + j * cell
            parts.append(
                f'<line x1="{margin_l}" y1="{gy:.3f}" '
                f'x2="{margin_l + plot_w:.3f}" y2="{gy:.3f}" '
                'stroke="#00000022"/>\n')
    parts.append(
        f'<text class="axis" x="{margin_l}" y="{svg_h - margin_b + 18}">'
        f"x: {x_left:g} … {x_right:g}</text>\n")
    parts.append(
        f'<text class="axis" x="{margin_l}" y="{margin_t - 8}">'
        f"y: {y_top:g} … {y_bottom:g}</text>\n")

    levels = sorted({c.level for c in contours})
    color_of = {lv: _PALETTE[k % len(_PALETTE)] for k, lv in enumerate(levels)}
    line_w = 2.2 if cell >= 10 else 1.4
    halo_w = line_w + 1.6

    for contour in contours:
        color = color_of[contour.level]
        points = " ".join(f"{px(x)},{py(y)}" for x, y in contour.points)
        if contour.closed:
            first = contour.points[0]
            points += f" {px(first[0])},{py(first[1])}"
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="#ffffff" '
            f'stroke-width="{halo_w}" stroke-linejoin="round" '
            'stroke-linecap="round" opacity="0.75"/>\n')
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="{line_w}" stroke-linejoin="round" '
            'stroke-linecap="round"/>\n')

    radius = 3.2 if cell >= 10 else 1.8
    for contour in contours:
        color = color_of[contour.level]
        for x, y in contour.points:
            parts.append(
                f'<circle cx="{px(x)}" cy="{py(y)}" r="{radius}" '
                f'fill="{color}" stroke="#fff" stroke-width="0.8"/>\n')

    legend_y = margin_t + plot_h + 30
    legend_x = margin_l
    for k, lv in enumerate(levels):
        color = color_of[lv]
        parts.append(
            f'<line x1="{legend_x + k * 110}" y1="{legend_y}" '
            f'x2="{legend_x + k * 110 + 26}" y2="{legend_y}" '
            f'stroke="{color}" stroke-width="3"/>\n')
        parts.append(
            f'<text class="legend" x="{legend_x + k * 110 + 30}" '
            f'y="{legend_y + 4}">level {lv:g}</text>\n')

    parts.append(
        f'<text class="stat" x="{margin_l}" y="{svg_h - 14}">'
        f"本次提取 {line_count} 条等值线，最长的线有 {max_segments} 段"
        "</text>\n")
    parts.append("</svg>\n</body>\n</html>\n")
    return "".join(parts)
