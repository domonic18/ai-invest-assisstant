"""persist_ai_kline_drawings 画线项校验单测（锚点即契约：幻觉日期拦截）。"""

import pytest

from app.agent.tools.drawing_tools import _validate_items

TRADE_DATES = {"2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"}


def trendline_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "drawing_type": "trendline",
        "anchors": [{"date": "2026-09-01", "price": 10.5}, {"date": "2026-09-03", "price": 11.2}],
        "label": "上升趋势线",
        "reason": "两次低点连线",
    }
    item.update(overrides)
    return item


@pytest.mark.unit
class TestValidateItems:
    def test_valid_items_pass(self) -> None:
        assert _validate_items([trendline_item()], TRADE_DATES) is None

    def test_empty_trade_dates_rejected(self) -> None:
        assert "无 K 线数据" in (_validate_items([trendline_item()], set()) or "")

    def test_hallucinated_date_rejected(self) -> None:
        item = trendline_item(
            anchors=[{"date": "2030-01-01", "price": 10.0}, {"date": "2026-09-03", "price": 11.0}]
        )
        assert "不是该标的真实交易日" in (_validate_items([item], TRADE_DATES) or "")

    def test_wrong_anchor_count_rejected(self) -> None:
        item = trendline_item(anchors=[{"date": "2026-09-01", "price": 10.0}])
        assert "2 个锚点" in (_validate_items([item], TRADE_DATES) or "")

    def test_hline_requires_no_date(self) -> None:
        item = trendline_item(
            drawing_type="hline", anchors=[{"date": "2026-09-01", "price": 10.0}]
        )
        assert "不需要 date" in (_validate_items([item], TRADE_DATES) or "")

    def test_hline_price_only_accepted(self) -> None:
        item = trendline_item(drawing_type="hline", anchors=[{"date": "", "price": 10.0}])
        assert _validate_items([item], TRADE_DATES) is None

    def test_duplicate_label_rejected(self) -> None:
        error = _validate_items([trendline_item(), trendline_item()], TRADE_DATES)
        assert error is not None and "重复" in error

    def test_label_and_reason_length_enforced(self) -> None:
        assert _validate_items([trendline_item(label="")], TRADE_DATES) is not None
        assert _validate_items([trendline_item(reason="")], TRADE_DATES) is not None

    def test_invalid_drawing_type_rejected(self) -> None:
        item = trendline_item(drawing_type="circle")
        assert "drawing_type 非法" in (_validate_items([item], TRADE_DATES) or "")

    def test_invalid_direction_rejected(self) -> None:
        item = trendline_item(direction="up")
        assert "direction 非法" in (_validate_items([item], TRADE_DATES) or "")

    def test_non_finite_price_rejected(self) -> None:
        item = trendline_item(
            anchors=[{"date": "2026-09-01", "price": "abc"}, {"date": "2026-09-03", "price": 1.0}]
        )
        assert "有限数值" in (_validate_items([item], TRADE_DATES) or "")
