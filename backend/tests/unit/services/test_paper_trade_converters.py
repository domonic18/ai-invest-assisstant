"""paper_trade_converters 表驱动单测（柜台宽松报文 → 强类型）。

钉住：epoch 秒/毫秒/ISO 容错解析、float32 尾噪 quantize、多候选键提取、
方向词表 side_to_action、counter 中文业务日；异常输入一律 None/空而非抛错
（柜台字段缺失是常态而非异常）。
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.core.clock import CN_TZ
from app.services.trading.paper_trade_converters import (
    SIDE_BUY,
    SIDE_SELL,
    bare_stock_code,
    counter_cn_trade_date,
    first_present,
    parse_counter_datetime,
    quantize_2dp,
    quantize_4dp,
    row_stock_code,
    side_to_action,
    to_decimal,
    to_int,
    unwrap_rows,
)

UTC = timezone.utc


@pytest.mark.unit
class TestUnwrapRows:
    def test_empty_object_becomes_empty_list(self) -> None:
        """柜台空结果返回 {}（非 list），收敛为空列表。"""
        assert unwrap_rows({}) == []

    def test_none_becomes_empty_list(self) -> None:
        assert unwrap_rows(None) == []

    def test_non_dict_rows_dropped(self) -> None:
        assert unwrap_rows([{"a": 1}, "junk", 3, {"b": 2}]) == [{"a": 1}, {"b": 2}]


@pytest.mark.unit
class TestBareStockCode:
    def test_counter_prefix_stripped(self) -> None:
        assert bare_stock_code("SHSE.600000") == "600000"
        assert bare_stock_code("SZSE.000037") == "000037"

    def test_bare_code_passthrough(self) -> None:
        assert bare_stock_code("600000") == "600000"

    def test_row_stock_code_reads_symbol(self) -> None:
        assert row_stock_code({"symbol": "BJSE.832000"}) == "832000"
        assert row_stock_code({}) == ""


@pytest.mark.unit
class TestParseCounterDatetime:
    def test_epoch_seconds(self) -> None:
        assert parse_counter_datetime(1_789_632_000) == datetime(2026, 9, 17, 8, tzinfo=UTC)

    def test_epoch_millis_divided(self) -> None:
        assert parse_counter_datetime(1_789_632_000_000) == datetime(2026, 9, 17, 8, tzinfo=UTC)

    def test_iso_z_string(self) -> None:
        assert parse_counter_datetime("2026-09-15T08:00:00Z") == datetime(2026, 9, 15, 8, tzinfo=UTC)

    def test_naive_iso_assumed_utc(self) -> None:
        assert parse_counter_datetime("2026-09-15T08:00:00") == datetime(2026, 9, 15, 8, tzinfo=UTC)

    @pytest.mark.parametrize(
        ("value",),
        [
            (None,),
            (True,),  # bool 是 int 子类，须显式排除
            ("",),
            ("  ",),
            ("not-a-date",),
            ([1, 2],),
        ],
    )
    def test_invalid_inputs_return_none(self, value: object) -> None:
        assert parse_counter_datetime(value) is None  # type: ignore[arg-type]


@pytest.mark.unit
class TestCounterCnTradeDate:
    def test_utc_evening_is_next_cn_day(self) -> None:
        """16:00 UTC = 次日 00:00 北京——业务日归次日的边界。"""
        dt = datetime(2026, 9, 15, 16, 0, tzinfo=UTC)
        assert counter_cn_trade_date(dt, date(2026, 9, 15)) == date(2026, 9, 16)

    def test_none_falls_back_to_sync_date(self) -> None:
        fallback = date(2026, 9, 15)
        assert counter_cn_trade_date(None, fallback) == fallback

    def test_cn_noon_keeps_same_day(self) -> None:
        dt = datetime(2026, 9, 15, 4, 0, tzinfo=UTC).astimezone(CN_TZ)
        assert counter_cn_trade_date(dt, date(2026, 1, 1)) == date(2026, 9, 15)


@pytest.mark.unit
class TestScalarCoercion:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("6.46999979019165", Decimal("6.46999979019165")),
            (6.47, Decimal("6.47")),
            (None, None),
            (True, None),  # bool 排除，防 True→1
            ("abc", None),
            ("", None),
        ],
    )
    def test_to_decimal(self, value: object, expected: Decimal | None) -> None:
        assert to_decimal(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("1200", 1200),
            (1200.0, 1200),
            (True, None),
            (None, None),
            ("x", None),
        ],
    )
    def test_to_int(self, value: object, expected: int | None) -> None:
        assert to_int(value) == expected

    def test_quantize_float32_noise(self) -> None:
        """柜台 float32 尾噪 quantize 到分 / 万分之一价格。"""
        noisy = Decimal("6.46999979019165")
        assert quantize_2dp(noisy) == Decimal("6.47")
        assert quantize_4dp(Decimal("9.54995")) == Decimal("9.5500")  # ROUND_HALF_UP

    def test_quantize_none_passthrough(self) -> None:
        assert quantize_2dp(None) is None
        assert quantize_4dp(None) is None

    def test_first_present_skips_none_and_blank(self) -> None:
        row = {"a": None, "b": "", "c": 0, "d": "x"}
        assert first_present(row, "a", "b", "c", "d") == 0  # 0 是有效值
        assert first_present(row, "a", "b") is None


@pytest.mark.unit
class TestSideVocabulary:
    def test_known_sides(self) -> None:
        assert (SIDE_BUY, SIDE_SELL) == (1, 2)
        assert side_to_action(SIDE_BUY) == "buy"
        assert side_to_action(SIDE_SELL) == "sell"

    @pytest.mark.parametrize("value", [0, 3, None, "1"])
    def test_unknown_side_returns_none(self, value: object) -> None:
        assert side_to_action(value) is None  # type: ignore[arg-type]
