"""等值线提取引擎：正交均匀网格 + marching squares。

口径（见 README 第二节）：
- 格点值 v >= level 记「高」，等于 level 也算高；
- 格边一高一低时恰有一个交叉点，t = (level - a) / (b - a)，
  a == level 取 t=0、b == level 取 t=1，直接取格点坐标；
- 线段走向保证「高角在左、低角在右」，整条线绕高区逆时针；
- 鞍点按格心双线性插值定夺：c >= level 两高角连通，否则各自孤立；
- 两端点坐标相同（按 6 位小数口径）的线段丢弃；
- 交叉点落在网格外边界上就是线的端点，不沿边界绕行。
"""

from bisect import bisect_right
from collections import namedtuple

Contour = namedtuple("Contour", ["level", "points", "closed"])

# 角顺序：0=BL 1=BR 2=TR 3=TL；边顺序：0=B 1=R 2=T 3=L。
# 非鞍点情形的有向线段表（边 -> 边），走向保证高区在左。
# 方向用叉积核定：沿线行走，高角在左侧（cross(走向, 高角) > 0）。
_SEGMENTS = {
    0: (),
    1: ((0, 3),),       # 孤高 BL：B->L
    2: ((1, 0),),       # 孤高 BR：R->B
    3: ((1, 3),),       # 底边高：R->L
    4: ((2, 1),),       # 孤高 TR：T->R
    5: None,            # 鞍点：BL、TR 高
    6: ((2, 0),),       # 右边高：T->B
    7: ((2, 3),),       # 孤低 TL：T->L
    8: ((3, 2),),       # 孤高 TL：L->T
    9: ((0, 2),),       # 左边高：B->T
    10: None,           # 鞍点：BR、TL 高
    11: ((1, 2),),      # 孤低 TR：R->T
    12: ((3, 1),),      # 顶边高：L->R
    13: ((0, 1),),      # 孤低 BR：B->R
    14: ((3, 0),),      # 孤低 BL：L->B
    15: (),
}

# 鞍点两种连法：center_high 为 True 表示格心判高、两高角连通；
# 否则两高角各自孤立（对应两条单高角/单低角线段）。
_SADDLE = {
    (5, True): ((0, 1), (2, 3)),    # 低 BR 与低 TL 各自成圈
    (5, False): ((0, 3), (2, 1)),   # 高 BL、高 TR 各自成圈
    (10, True): ((3, 0), (1, 2)),   # 低 BL 与低 TR 各自成圈
    (10, False): ((1, 0), (3, 2)),  # 高 BR、高 TL 各自成圈
}


def _round6(value):
    """6 位小数四舍五入（round-half-even），-0.0 归一为 0.0。"""
    return round(value, 6) + 0.0


def extract(grid):
    """从 Grid 提取全部等值线，返回 Contour 列表。

    排序口径：先按 level 升序，同一 level 内按点序列字典序升序；
    闭合线起点取字典序最小的点，开放线起点是唯一没有入线段的端点。
    """
    ncols = grid.ncols
    nrows = grid.nrows
    x0 = grid.x0
    y0 = grid.y0
    dx = grid.dx
    dy = grid.dy
    values = grid.values
    levels = sorted(grid.levels)
    nlevels = len(levels)

    # 每个等值面一套接线表：pred[succ] = pred，键是 6 位小数坐标元组。
    succ_of = [dict() for _ in levels]
    in_deg = [dict() for _ in levels]
    round6 = _round6

    for j in range(nrows - 1):
        row = j * ncols
        row_up = row + ncols
        yb = y0 + j * dy
        yt = yb + dy
        for i in range(ncols - 1):
            base = row + i
            v_bl = values[base]
            v_br = values[base + 1]
            v_tr = values[base + ncols + 1]
            v_tl = values[base + ncols]
            vmin = v_bl
            if v_br < vmin:
                vmin = v_br
            if v_tr < vmin:
                vmin = v_tr
            if v_tl < vmin:
                vmin = v_tl
            vmax = v_bl
            if v_br > vmax:
                vmax = v_br
            if v_tr > vmax:
                vmax = v_tr
            if v_tl > vmax:
                vmax = v_tl
            # 落在 (vmin, vmax] 内的等值面才需要处理；vmin == level
            # 时四角不会全高，也不会产生交叉点，可以跳过。
            start = bisect_right(levels, vmin)
            stop = bisect_right(levels, vmax)
            if start == stop:
                continue
            xl = x0 + i * dx
            xr = xl + dx
            for li in range(start, stop):
                level = levels[li]
                mask = 0
                if v_bl >= level:
                    mask |= 1
                if v_br >= level:
                    mask |= 2
                if v_tr >= level:
                    mask |= 4
                if v_tl >= level:
                    mask |= 8
                if mask == 0 or mask == 15:
                    continue
                if mask == 5 or mask == 10:
                    center = (v_bl + v_br + v_tr + v_tl) * 0.25
                    spans = _SADDLE[(mask, center >= level)]
                else:
                    spans = _SEGMENTS[mask]
                pts = [None, None, None, None]

                def edge_point(e, _xl=xl, _xr=xr, _yb=yb, _yt=yt,
                               _v=(v_bl, v_br, v_tr, v_tl), _lv=level):
                    if e == 0:
                        a, b = _v[0], _v[1]
                        if a == _lv:
                            t = 0.0
                        elif b == _lv:
                            t = 1.0
                        else:
                            t = (_lv - a) / (b - a)
                        return (round6(_xl + t * (_xr - _xl)), round6(_yb))
                    if e == 1:
                        a, b = _v[1], _v[2]
                        if a == _lv:
                            t = 0.0
                        elif b == _lv:
                            t = 1.0
                        else:
                            t = (_lv - a) / (b - a)
                        return (round6(_xr), round6(_yb + t * (_yt - _yb)))
                    if e == 2:
                        a, b = _v[3], _v[2]
                        if a == _lv:
                            t = 0.0
                        elif b == _lv:
                            t = 1.0
                        else:
                            t = (_lv - a) / (b - a)
                        return (round6(_xl + t * (_xr - _xl)), round6(_yt))
                    a, b = _v[0], _v[3]
                    if a == _lv:
                        t = 0.0
                    elif b == _lv:
                        t = 1.0
                    else:
                        t = (_lv - a) / (b - a)
                    return (round6(_xl), round6(_yb + t * (_yt - _yb)))

                succ_map = succ_of[li]
                indeg_map = in_deg[li]
                for e_from, e_to in spans:
                    p = pts[e_from]
                    if p is None:
                        p = pts[e_from] = edge_point(e_from)
                    q = pts[e_to]
                    if q is None:
                        q = pts[e_to] = edge_point(e_to)
                    if p == q:
                        continue  # 零长度线段，丢弃
                    succ_map[p] = q
                    indeg_map[q] = indeg_map.get(q, 0) + 1

    contours = []
    for li, level in enumerate(levels):
        succ_map = succ_of[li]
        indeg_map = in_deg[li]
        starts = sorted(p for p in succ_map if p not in indeg_map)
        for start in starts:
            if start not in succ_map:
                continue
            points = [start]
            node = succ_map.pop(start)
            while node in succ_map:
                points.append(node)
                node = succ_map.pop(node)
            points.append(node)
            contours.append(Contour(level, points, False))
        rest = sorted(succ_map)
        for start in rest:
            if start not in succ_map:
                continue
            points = [start]
            node = succ_map.pop(start)
            while node != start:
                points.append(node)
                node = succ_map.pop(node)
            contours.append(Contour(level, points, True))
    contours.sort(key=lambda c: (c.level, c.points))
    return contours


def stats(contours):
    """返回 (线条数, 最长线的段数)。闭合线段数等于点数，开放线减一。"""
    max_segments = 0
    for contour in contours:
        segments = len(contour.points) if contour.closed else len(contour.points) - 1
        if segments > max_segments:
            max_segments = segments
    return len(contours), max_segments
