"""K 线画线服务单测：上下文序列化 + 锚点校验（纯函数，零 mock）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import BadRequestError
from app.schemas.drawing import (
    AiKlineDrawingItemSchema,
    UserKlineDrawingResponse,
)
from app.services.market import kline_drawing_service
from app.services.market.kline_drawing_service import (
    _format_price,
    _validate_anchors,
    serialize_user_drawings_context,
)

pytestmark = pytest.mark.unit


def _anchor(date: str, price: float) -> dict:
    return {"date": date, "price": price}


def _drawing(
    drawing_type: str,
    anchors: list[dict],
    *,
    period: str = "daily",
    direction: str | None = None,
    text: str | None = None,
) -> UserKlineDrawingResponse:
    return UserKlineDrawingResponse(
        id="1",
        target_type="stock",
        target_code="600519",
        period=period,  # type: ignore[arg-type]
        drawing_type=drawing_type,  # type: ignore[arg-type]
        anchors=anchors,  # type: ignore[arg-type]
        direction=direction,  # type: ignore[arg-type]
        text=text,
        style={"color": "#f59e0b", "line_style": "solid", "width": 2},
    )


# ---------- _format_price ----------


def test_format_price_strips_trailing_zeros() -> None:
    assert _format_price(1520.0) == "1520"
    assert _format_price(10.50) == "10.5"
    assert _format_price(3.14) == "3.14"


# ---------- _validate_anchors ----------


def test_validate_anchors_accepts_trendline() -> None:
    _validate_anchors("trendline", [_anchor("2026-09-01", 10.0), _anchor("2026-09-10", 12.5)])


def test_validate_anchors_wrong_count() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("trendline", [_anchor("2026-09-01", 10.0)])
    with pytest.raises(BadRequestError):
        _validate_anchors("hline", [_anchor("", 10.0), _anchor("", 11.0)])


def test_validate_anchors_non_finite_price() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("hline", [{"date": "", "price": float("nan")}])


def test_validate_anchors_hline_rejects_date() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("hline", [_anchor("2026-09-01", 10.0)])


def test_validate_anchors_bad_date() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("box", [_anchor("2026/09/01", 10.0), _anchor("2026-09-10", 12.0)])
    with pytest.raises(BadRequestError):
        _validate_anchors("box", [_anchor("", 10.0), _anchor("2026-09-10", 12.0)])


# ---------- serialize_user_drawings_context（需求 4.4 读协议） ----------


def test_serialize_empty_returns_hint() -> None:
    assert serialize_user_drawings_context([]) == "（该标的暂无用户画线）"


def test_serialize_hline_with_text() -> None:
    context = serialize_user_drawings_context(
        [_drawing("hline", [{"date": "", "price": 1520.0}], text="强支撑")]
    )
    assert context == "[用户画线·日线]\n- 水平线：1520「强支撑」"


def test_serialize_box_body() -> None:
    context = serialize_user_drawings_context(
        [
            _drawing(
                "box",
                [_anchor("2026-08-01", 1450.0), _anchor("2026-09-01", 1520.0)],
                period="weekly",
            )
        ]
    )
    assert context == (
        "[用户画线·周线]\n- 箱体：1450~1520（2026-08-01 ~ 2026-09-01）"
    )


def test_serialize_text_annotation_is_first_class_line() -> None:
    context = serialize_user_drawings_context(
        [_drawing("text", [_anchor("2026-09-10", 88.5)], text="缺口回补")]
    )
    assert context == "[用户画线·日线]\n- 文字标注：「缺口回补」 @ 2026-09-10 88.5"


def test_serialize_ray_direction_word() -> None:
    base = [_anchor("2026-09-01", 10.0), _anchor("2026-09-10", 12.0)]
    assert (
        "→ 向右延伸" in serialize_user_drawings_context([_drawing("ray", base)])
    )
    assert (
        "→ 双向延伸"
        in serialize_user_drawings_context([_drawing("ray", base, direction="both")])
    )
    assert (
        "→ 向左延伸"
        in serialize_user_drawings_context([_drawing("ray", base, direction="left")])
    )


def test_serialize_trendline_segment() -> None:
    context = serialize_user_drawings_context(
        [_drawing("trendline", [_anchor("2026-09-01", 10.0), _anchor("2026-09-10", 12.0)])]
    )
    assert "- 线段：2026-09-01 10 → 2026-09-10 12" in context


def test_serialize_groups_by_period_in_order() -> None:
    drawings = [
        _drawing("hline", [{"date": "", "price": 20.0}], period="monthly"),
        _drawing("hline", [{"date": "", "price": 10.0}], period="daily"),
        _drawing("hline", [{"date": "", "price": 15.0}], period="weekly"),
    ]
    context = serialize_user_drawings_context(drawings)
    assert context.index("[用户画线·日线]") < context.index("[用户画线·周线]")
    assert context.index("[用户画线·周线]") < context.index("[用户画线·月线]")


# ---------- AI 画线 item schema 冒烟（payload camelCase 往返） ----------


def test_ai_item_schema_roundtrip() -> None:
    item = AiKlineDrawingItemSchema.model_validate(
        {
            "drawingType": "trendline",
            "anchors": [
                {"date": "2026-09-01", "price": 10.0},
                {"date": "2026-09-10", "price": 12.0},
            ],
            "label": "上升趋势线",
            "reason": "低点抬高",
        }
    )
    assert item.drawing_type == "trendline"
    assert item.anchors[1].price == 12.0


# ---------- 复盘注入上下文构建（读协议 4.4，repo 打桩） ----------


class _FakeUserRepo:
    """按 target_code 返回预设 payload 行（SimpleNamespace 模拟 ORM 行）。"""

    def __init__(self, rows_by_code: dict[str, list]):
        self._rows_by_code = rows_by_code

    async def list_by_target(self, target_type: str, target_code: str) -> list:
        return self._rows_by_code.get(target_code, [])


def _payload_row(
    drawing_id: int,
    target_code: str,
    drawing_type: str,
    anchors: list[dict],
    *,
    period: str = "daily",
    text: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=drawing_id,
        target_type="stock" if target_code.isdigit() else "index",
        target_code=target_code,
        period=period,
        drawing_type=drawing_type,
        payload={"anchors": anchors, "text": text, "style": {"color": "#f0b429", "lineStyle": "solid", "width": 2}},
    )


@pytest.mark.asyncio
async def test_build_target_drawings_context_serializes_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _payload_row(
        1,
        "600519",
        "hline",
        [{"date": "", "price": 1380.0}],
        text="前低支撑",
    )
    monkeypatch.setattr(
        kline_drawing_service,
        "UserKlineDrawingRepository",
        lambda _session: _FakeUserRepo({"600519": [row]}),
    )
    context = await kline_drawing_service.build_target_drawings_context(
        AsyncMock(), "stock", "600519"
    )
    assert "[用户画线·日线]" in context
    assert "水平线：1380" in context
    assert "「前低支撑」" in context


@pytest.mark.asyncio
async def test_build_target_drawings_context_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        kline_drawing_service,
        "UserKlineDrawingRepository",
        lambda _session: _FakeUserRepo({}),
    )
    context = await kline_drawing_service.build_target_drawings_context(
        AsyncMock(), "stock", "600519"
    )
    assert context == "（该标的暂无用户画线）"


@pytest.mark.asyncio
async def test_build_market_index_drawings_context_only_labeled_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _payload_row(
        2,
        "sh000001",
        "hline",
        [{"date": "", "price": 3050.0}],
        text="支撑",
    )
    monkeypatch.setattr(
        kline_drawing_service,
        "UserKlineDrawingRepository",
        lambda _session: _FakeUserRepo({"sh000001": [row]}),
    )
    context = await kline_drawing_service.build_market_index_drawings_context(
        AsyncMock(), {"sh000001": "沪指", "sz399006": "创业板"}
    )
    assert "[沪指]" in context
    assert "创业板" not in context
    assert "水平线：3050" in context


@pytest.mark.asyncio
async def test_build_market_index_drawings_context_all_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        kline_drawing_service,
        "UserKlineDrawingRepository",
        lambda _session: _FakeUserRepo({}),
    )
    context = await kline_drawing_service.build_market_index_drawings_context(
        AsyncMock(), {"sh000001": "沪指", "CN00Y": "富时A50"}
    )
    assert context == "（五大标的暂无用户画线）"
