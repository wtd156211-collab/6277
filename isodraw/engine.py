"""等值线提取引擎（marching squares，口径见 README 第二节）。

- v >= level 记高，等于 level 的格点算高。
- 交叉点落在格边上：一端正好等于 level 时直接取格点坐标，不做浮点插值。
- 线段走向：高角在左、低角在右，整条线绕高区逆时针。
- 鞍点（对角两高）按格心双线性插值 c 判连法。
- 两端点坐标相同的零长线段直接丢弃。
"""

from __future__ import annotations

from dataclasses import dataclass

# 边编号：0=底 BL->BR，1=右 BR->TR，2=顶 TL->TR，3=左 BL->TL
# 掩码位：1=BL，2=BR，4=TR，8=TL。
# 每项给出该格胞内的有向线段（起边, 止边），高侧在左侧。
_CASES = {
    0x1: ((0, 3),),        # 仅 BL 高
    0x2: ((1, 0),),        # 仅 BR 高
    0x3: ((1, 3),),        # 底侧两角高
    0x4: ((2, 1),),        # 仅 TR 高
    0x6: ((2, 0),),        # 右侧两角高
    0x7: ((2, 3),),        # 缺 TL（低角在 TL）
    0x8: ((3, 2),),        # 仅 TL 高
    0x9: ((0, 2),),        # 左侧两角高
    0xB: ((1, 2),),        # 缺 TR
    0xC: ((3, 1),),        # 顶侧两角高
    0xD: ((0, 1),),        # 缺 BR
    0xE: ((3, 0),),        # 缺 BL
}

# 鞍点：键 0x5 = BL+TR 高，0xA = BR+TL 高。
# 值为 (c >= level 时的连法, c < level 时的连法)。
# c>=level：两个高角连通，两根线圈住两个低角；
# c< level：两个高角各自孤立，两根线圈住两个高角。
_SADDLES = {
    0x5: (((0, 1), (2, 3)), ((0, 3), (2, 1))),
    0xA: (((3, 0), (1, 2)), ((1, 0), (3, 2))),
}


@dataclass
class Contour:
    level: float
    points: list  # [(x, y), ...]
    closed: bool


def _crossing(edge, level, xa, xb, ya, yb, vbl, vbr, vtr, vtl):
    """格边上交叉点。A/B 为边的起终点（与边编号方向一致）。"""
    if edge == 0:  # 底：BL -> BR
        a, b = vbl, vbr
        if a == level:
            return (xa, ya)
        if b == level:
            return (xb, ya)
        t = (level - a) / (b - a)
        return (xa + t * (xb - xa), ya)
    if edge == 1:  # 右：BR -> TR
        a, b = vbr, vtr
        if a == level:
            return (xb, ya)
        if b == level:
            return (xb, yb)
        t = (level - a) / (b - a)
        return (xb, ya + t * (yb - ya))
    if edge == 2:  # 顶：TL -> TR
        a, b = vtl, vtr
        if a == level:
            return (xa, yb)
        if b == level:
            return (xb, yb)
        t = (level - a) / (b - a)
        return (xa + t * (xb - xa), yb)
    # 左：BL -> TL
    a, b = vbl, vtl
    if a == level:
        return (xa, ya)
    if b == level:
        return (xa, yb)
    t = (level - a) / (b - a)
    return (xa, ya + t * (yb - ya))


def _rounded(point):
    return (round(point[0], 6), round(point[1], 6))


def _join(level, segments):
    """按坐标把有向线段接成整条线；每个点至多一进一出。"""
    nxt = {}
    has_incoming = set()
    for start, end in segments:
        nxt[start] = end
        has_incoming.add(end)

    contours = []
    consumed = set()

    # 开放线：起点是没有入线段的点，终点没有出线段。
    for start, _end in segments:
        if start in has_incoming or start in consumed:
            continue
        points = [start]
        consumed.add(start)
        cur = start
        while cur in nxt:
            cur = nxt[cur]
            points.append(cur)
            if cur in consumed:
                break
            consumed.add(cur)
        contours.append(Contour(level, points, False))

    # 闭合线：剩下的线段首尾相接成环。
    for start, _end in segments:
        if start in consumed:
            continue
        points = [start]
        consumed.add(start)
        cur = start
        while True:
            cur = nxt[cur]
            if cur == start:
                break
            points.append(cur)
            consumed.add(cur)
        # 闭合线起点取字典序最小点，方向（绕高区逆时针）保持不变。
        best = 0
        best_key = _rounded(points[0])
        for m in range(1, len(points)):
            key = _rounded(points[m])
            if key < best_key:
                best = m
                best_key = key
        points = points[best:] + points[:best]
        contours.append(Contour(level, points, True))

    return contours


def extract(grid: Grid) -> list:
    ncols = grid.ncols
    nrows = grid.nrows
    levels = grid.levels
    nlev = len(levels)
    values = grid.values

    xs = [grid.x0 + i * grid.dx for i in range(ncols)]
    ys = [grid.y0 + j * grid.dy for j in range(nrows)]

    seg_lists = [[] for _ in range(nlev)]
    cases = _CASES
    saddles = _SADDLES
    crossing = _crossing

    for j in range(nrows - 1):
        row_lo = values[j]
        row_hi = values[j + 1]
        ya = ys[j]
        yb = ys[j + 1]
        for i in range(ncols - 1):
            vbl = row_lo[i]
            vbr = row_lo[i + 1]
            vtl = row_hi[i]
            vtr = row_hi[i + 1]

            mn = vbl
            if vbr < mn:
                mn = vbr
            if vtl < mn:
                mn = vtl
            if vtr < mn:
                mn = vtr
            mx = vbl
            if vbr > mx:
                mx = vbr
            if vtl > mx:
                mx = vtl
            if vtr > mx:
                mx = vtr
            if mn == mx:
                continue  # 四角同值，没有任何 level 满足 mn < level <= mx

            xa = xs[i]
            xb = xs[i + 1]
            for li in range(nlev):
                level = levels[li]
                if level > mx:
                    break
                if level <= mn:
                    continue

                mask = 0
                if vbl >= level:
                    mask |= 1
                if vbr >= level:
                    mask |= 2
                if vtr >= level:
                    mask |= 4
                if vtl >= level:
                    mask |= 8

                if mask == 0x5 or mask == 0xA:
                    center = (vbl + vbr + vtr + vtl) * 0.25
                    edges = saddles[mask][0 if center >= level else 1]
                else:
                    edges = cases.get(mask)
                    if edges is None:
                        continue

                out = seg_lists[li]
                for edge0, edge1 in edges:
                    p0 = crossing(edge0, level, xa, xb, ya, yb,
                                  vbl, vbr, vtr, vtl)
                    p1 = crossing(edge1, level, xa, xb, ya, yb,
                                  vbl, vbr, vtr, vtl)
                    if p0 != p1:  # 零长线段丢弃
                        out.append((p0, p1))

    contours = []
    for li, level in enumerate(levels):
        contours.extend(_join(level, seg_lists[li]))

    contours.sort(key=lambda c: (c.level, [_rounded(p) for p in c.points]))
    return contours
