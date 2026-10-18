"""K 线画线渲染器单测（锚点几何与前端 geometry.ts 同构性钉死，纯函数无 IO）。"""

import pytest

from app.services.market.kline_drawing_render import (
    CANVAS_W,
    MARGIN_LEFT,
    MARGIN_TOP,
    RenderableDrawing,
    _ray_segments,
    anchor_index,
    clip_segment,
    price_range,
    render_kline_png,
    x_of_index,
    y_of_price,
)


def _bars(n: int = 10) -> list[dict]:
    return [
        {
            "date": f"2026-09-{i + 1:02d}",
            "open": 10.0 + i * 0.1,
            "high": 10.5 + i * 0.1,
            "low": 9.8 + i * 0.1,
            "close": 10.2 + i * 0.1,
        }
        for i in range(n)
    ]


def _dates(n: int = 10) -> list[str]:
    return [f"2026-09-{i + 1:02d}" for i in range(n)]


class TestAnchorIndex:
    def test_exact_hit(self) -> None:
        assert anchor_index("2026-09-03", _dates()) == 2

    def test_missing_aligns_to_previous_bar(self) -> None:
        """锚点 date 不在交易日序列时吸附到「≤ 该日期的最后一根 bar」。"""
        assert anchor_index("2026-09-03", _dates()) == 2
        assert anchor_index("2026-09-25", _dates()) == 9

    def test_earlier_than_first_clamps_to_zero(self) -> None:
        assert anchor_index("2026-01-01", _dates()) == 0

    def test_empty_date_lands_on_last_bar(self) -> None:
        assert anchor_index("", _dates()) == 9


class TestPriceRange:
    def test_pads_five_percent(self) -> None:
        y_min, y_max = price_range(_bars())
        # min low 9.8 / max high 11.4，pad = 1.6 × 5% = 0.08
        assert y_min == pytest.approx(9.72)
        assert y_max == pytest.approx(11.48)

    def test_flat_series_pads_one(self) -> None:
        bars = [{"date": "2026-09-01", "open": 10, "high": 10, "low": 10, "close": 10}] * 3
        y_min, y_max = price_range(bars)
        assert (y_min, y_max) == (9.0, 11.0)


class TestClipSegment:
    RECT = (MARGIN_LEFT, MARGIN_TOP, CANVAS_W - 76, 606)

    def test_fully_inside_unchanged(self) -> None:
        seg = clip_segment((100, 100), (200, 150), self.RECT)
        assert seg == ((100.0, 100.0), (200.0, 150.0))

    def test_fully_outside_returns_none(self) -> None:
        assert clip_segment((0, 0), (5, 5), self.RECT) is None

    def test_crossing_clipped_to_rect(self) -> None:
        x0, y0, x1, y1 = self.RECT
        seg = clip_segment((0, 300), (x0 + 50, 300), self.RECT)
        assert seg is not None
        assert seg[0][0] == pytest.approx(x0)


class TestRaySegments:
    RECT = (MARGIN_LEFT, MARGIN_TOP, CANVAS_W - 76, 606)

    def test_direction_right_extends_forward(self) -> None:
        segs = _ray_segments((100, 100), (200, 120), "right", self.RECT)
        assert len(segs) == 2
        assert segs[0] == ((100.0, 100.0), (200.0, 120.0))
        end = segs[1][1]
        assert end[0] > self.RECT[2]

    def test_direction_both_extends_both_ways(self) -> None:
        segs = _ray_segments((100, 100), (200, 120), "both", self.RECT)
        assert len(segs) == 3
        assert segs[2][1][0] < self.RECT[0]

    def test_degenerate_returns_empty(self) -> None:
        assert _ray_segments((100, 100), (100, 100), "right", self.RECT) == []


class TestRenderKlinePng:
    def test_renders_png_with_mixed_layers(self) -> None:
        drawings = [
            RenderableDrawing(
                layer="user",
                drawing_type="trendline",
                anchors=(("2026-09-02", 10.0), ("2026-09-08", 10.8)),
                label="支撑",
                color="#f59e0b",
                line_style="dashed",
                width=2,
            ),
            RenderableDrawing(layer="ai", drawing_type="hline", anchors=(("", 10.5),), label="压力位"),
            RenderableDrawing(
                layer="ai",
                drawing_type="box",
                anchors=(("2026-09-01", 10.2), ("2026-09-06", 10.9)),
                label="箱体",
            ),
            RenderableDrawing(
                layer="ai",
                drawing_type="ray",
                anchors=(("2026-09-03", 9.9), ("2026-09-07", 10.6)),
                direction="right",
                label="上攻射线",
            ),
        ]
        png = render_kline_png(_bars(), drawings, title_name="贵州茅台", title_code="600519")
        assert png.startswith(b"\x89PNG")
        assert len(png) > 1000

    def test_renders_without_drawings(self) -> None:
        png = render_kline_png(_bars(), [], title_code="600519")
        assert png.startswith(b"\x89PNG")

    def test_requires_at_least_two_bars(self) -> None:
        with pytest.raises(ValueError, match="2 根"):
            render_kline_png(_bars(1), [])

    def test_geometry_roundtrip_top_bottom(self) -> None:
        """最高价映射在绘图区顶部、最低价在底部（±5% padding 之内）。"""
        bars = _bars()
        y_min, y_max = price_range(bars)
        assert y_of_price(y_max, y_min, y_max) == pytest.approx(MARGIN_TOP)
        assert y_of_price(y_min, y_min, y_max) == pytest.approx(606)
        assert x_of_index(0, 10) > MARGIN_LEFT
