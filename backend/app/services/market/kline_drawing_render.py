"""K 线画线服务端渲染器（pillow 自绘，交易 Agent 画线视觉验证批次 2）。

锚点几何与前端 ``web/src/components/charts/drawing/geometry.ts`` 同构：

- x = 交易日 category 下标：锚点 date 先精确命中，再「≤ 该日期的最后一根
  bar」二分对齐，早于首根吸附 index 0，空 date（hline）落最后一根；
- price→y = 可见区间 min(low)/max(high) ±5% padding 线性映射；
- trendline 两点线段（Liang-Barsky 裁剪到绘图区）；ray 按 direction 线性
  外插到绘图区边缘；box 两锚点对角矩形；hline 全宽水平线。

输入为升序 K 线 dict 列表与归一化 :class:`RenderableDrawing` 列表，输出
PNG bytes——纯函数无 IO，钉子单测直接喂构造数据。
"""

import io
import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

CANVAS_W = 1120
CANVAS_H = 640
MARGIN_LEFT = 16
MARGIN_TOP = 44
MARGIN_RIGHT = 76
MARGIN_BOTTOM = 34

#: 画布主题（与站点暗色令牌同源）；涨跌遵循国内习惯红涨绿跌
BG = "#0c0e12"
GRID = "#1a1e26"
BORDER = "#23262d"
TEXT_MUTED = "#8c8c8c"
RISE = "#f85149"
FALL = "#2ea043"

#: AI 画线固定配色轮盘（AI 项无 style 字段，契约如此）
AI_PALETTE: tuple[str, ...] = (
    "#22d3ee",
    "#a855f7",
    "#f59e0b",
    "#60a5fa",
    "#f472b6",
    "#34d399",
)

TYPE_LABELS = {
    "trendline": "趋势线",
    "ray": "射线",
    "hline": "水平线",
    "box": "箱体",
    "text": "标注",
}
PERIOD_LABELS = {"daily": "日K", "weekly": "周K", "monthly": "月K"}

_FONT_PATHS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)
_fonts: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


@dataclass(frozen=True)
class RenderableDrawing:
    """渲染器归一化画线（user 层带 style，ai 层由调用方配 palette 色）。"""

    layer: str
    drawing_type: str
    anchors: tuple[tuple[str, float], ...]
    direction: str = "right"
    label: str = ""
    color: str = "#22d3ee"
    line_style: str = "solid"
    width: int = 2
    text: str = ""


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if size not in _fonts:
        for path in _FONT_PATHS:
            try:
                _fonts[size] = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        else:
            _fonts[size] = ImageFont.load_default(size)
    return _fonts[size]


def anchor_index(anchor_date: str, dates: Sequence[str]) -> int:
    """锚点 date → bar 下标（先精确命中再 ≤ 对齐；空 date 落最后一根）。"""
    if not anchor_date:
        return len(dates) - 1
    idx = bisect_right(dates, anchor_date) - 1
    return idx if idx >= 0 else 0


def price_range(bars: Sequence[dict]) -> tuple[float, float]:
    """可见区间价格域：min(low)/max(high) ±5% padding（区间为 0 时取 ±1）。"""
    p_min = min(float(bar["low"]) for bar in bars)
    p_max = max(float(bar["high"]) for bar in bars)
    pad = (p_max - p_min) * 0.05 or 1
    return p_min - pad, p_max + pad


def x_of_index(i: int, n: int) -> float:
    """category 轴：bar i 的中点 x。"""
    return MARGIN_LEFT + (i + 0.5) * (CANVAS_W - MARGIN_LEFT - MARGIN_RIGHT) / n


def y_of_price(price: float, y_min: float, y_max: float) -> float:
    """价格域 → 像素 y（可见区间线性映射，顶=max、底=min）。"""
    plot_h = CANVAS_H - MARGIN_TOP - MARGIN_BOTTOM
    return MARGIN_TOP + (1 - (price - y_min) / (y_max - y_min)) * plot_h


def clip_segment(
    p1: tuple[float, float],
    p2: tuple[float, float],
    rect: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Liang-Barsky 线段裁剪（与前端 geometry.ts clipSegment 同构）；完全在外返回 None。"""
    x0, y0, x1, y1 = rect
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p1[0] - x0), (dx, x1 - p1[0]), (-dy, p1[1] - y0), (dy, y1 - p1[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return None
            if r > t0:
                t0 = r
        else:
            if r < t0:
                return None
            if r < t1:
                t1 = r
    return (
        (p1[0] + t0 * dx, p1[1] + t0 * dy),
        (p1[0] + t1 * dx, p1[1] + t1 * dy),
    )


def _draw_styled_segment(
    draw: ImageDraw.ImageDraw,
    p1: tuple[float, float],
    p2: tuple[float, float],
    rect: tuple[float, float, float, float],
    *,
    color: str,
    width: int,
    style: str,
) -> None:
    seg = clip_segment(p1, p2, rect)
    if seg is None:
        return
    a, b = seg
    if style not in ("dashed", "dotted"):
        draw.line([a, b], fill=color, width=width)
        return
    on, off = (2, 4) if style == "dotted" else (9, 6)
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1:
        return
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    t = 0.0
    while t < length:
        end = min(t + on, length)
        draw.line(
            [(a[0] + ux * t, a[1] + uy * t), (a[0] + ux * end, a[1] + uy * end)],
            fill=color,
            width=width,
        )
        t = end + off


def _ray_segments(
    a: tuple[float, float],
    b: tuple[float, float],
    direction: str,
    rect: tuple[float, float, float, float],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """a→b 定向射线：核心段 + 按 direction 的远端外插（大系数越界由裁剪兜底）。"""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if dx == 0 and dy == 0:
        return []
    big = 4.0 * ((rect[2] - rect[0]) + (rect[3] - rect[1]))
    segs = [(a, b)]
    if direction in ("right", "both"):
        segs.append((b, (b[0] + dx * big, b[1] + dy * big)))
    if direction in ("left", "both"):
        segs.append((a, (a[0] - dx * big, a[1] - dy * big)))
    return segs


def render_kline_png(
    bars: Sequence[dict],
    drawings: Sequence[RenderableDrawing],
    *,
    title_name: str = "",
    title_code: str = "",
    period_label: str = "日K",
) -> bytes:
    """渲染「K 线蜡烛 + 画线双图层」为 PNG bytes。

    bars 为升序日K dict（date/open/high/low/close 必填）；drawings 顺序即
    绘制顺序（调用方先 user 后 ai，AI 线叠在上层）。
    """
    n = len(bars)
    if n < 2:
        raise ValueError("K 线至少需要 2 根才能渲染")
    dates = [str(bar["date"])[:10] for bar in bars]
    y_min, y_max = price_range(bars)
    rect = (MARGIN_LEFT, MARGIN_TOP, CANVAS_W - MARGIN_RIGHT, CANVAS_H - MARGIN_BOTTOM)

    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(img)
    font_s, font_m, font_l = _font(12), _font(14), _font(16)

    # 网格与坐标轴（价格右轴 5 档 / 日期底轴 6 档）
    for k in range(5):
        price = y_min + (y_max - y_min) * k / 4
        y = y_of_price(price, y_min, y_max)
        draw.line([(rect[0], y), (rect[2], y)], fill=GRID, width=1)
        draw.text((rect[2] + 8, y - 7), f"{price:.2f}", fill=TEXT_MUTED, font=font_s)
    for k in range(6):
        idx = round(k * (n - 1) / 5)
        x = x_of_index(idx, n)
        draw.line([(x, rect[1]), (x, rect[3])], fill=GRID, width=1)
        draw.text((x - 20, rect[3] + 8), dates[idx][5:], fill=TEXT_MUTED, font=font_s)
    draw.rectangle(rect, outline=BORDER, width=1)

    # 蜡烛层（红涨绿跌）
    step = (rect[2] - rect[0]) / n
    half = max(1.0, min(step * 0.35, 7.0))
    for i, bar in enumerate(bars):
        cx = x_of_index(i, n)
        color = RISE if float(bar["close"]) >= float(bar["open"]) else FALL
        draw.line(
            [(cx, y_of_price(float(bar["high"]), y_min, y_max)), (cx, y_of_price(float(bar["low"]), y_min, y_max))],
            fill=color,
            width=1,
        )
        top, bottom = sorted((y_of_price(float(bar["open"]), y_min, y_max), y_of_price(float(bar["close"]), y_min, y_max)))
        if bottom - top < 1:
            bottom = top + 1
        draw.rectangle([cx - half, top, cx + half, bottom], fill=color)

    # 画线图层（按传入顺序叠绘；线旁直标 label）
    for d in drawings:
        pts = [(x_of_index(anchor_index(adate, dates), n), y_of_price(price, y_min, y_max)) for adate, price in d.anchors]

        def stroke(p1: tuple[float, float], p2: tuple[float, float]) -> None:
            _draw_styled_segment(draw, p1, p2, rect, color=d.color, width=d.width, style=d.line_style)

        if d.drawing_type == "trendline" and len(pts) == 2:
            stroke(pts[0], pts[1])
            anchor = pts[0]
        elif d.drawing_type == "ray" and len(pts) == 2:
            for seg in _ray_segments(pts[0], pts[1], d.direction, rect):
                stroke(seg[0], seg[1])
            anchor = pts[0]
        elif d.drawing_type == "hline" and pts:
            y = pts[0][1]
            stroke((rect[0], y), (rect[2], y))
            anchor = (rect[0] + 6, y)
        elif d.drawing_type == "box" and len(pts) == 2:
            bx0, bx1 = sorted((pts[0][0], pts[1][0]))
            by0, by1 = sorted((pts[0][1], pts[1][1]))
            for edge in (
                ((bx0, by0), (bx1, by0)),
                ((bx1, by0), (bx1, by1)),
                ((bx1, by1), (bx0, by1)),
                ((bx0, by1), (bx0, by0)),
            ):
                stroke(edge[0], edge[1])
            anchor = (bx0, by0)
        elif d.drawing_type == "text" and pts:
            draw.text((pts[0][0] + 4, pts[0][1] - 8), d.text or d.label, fill=d.color, font=font_m)
            continue
        else:
            continue
        if d.label:
            draw.text((anchor[0] + 6, anchor[1] - 16), d.label, fill=d.color, font=font_s)

    # 标题带
    user_ct = sum(1 for d in drawings if d.layer == "user")
    head = f"{title_name}（{title_code}）" if title_name else title_code
    draw.text(
        (MARGIN_LEFT, 14),
        f"{head} · {period_label} × {n} · 画线 {len(drawings)} 条（用户 {user_ct} / AI {len(drawings) - user_ct}）",
        fill=TEXT_MUTED,
        font=font_l,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
