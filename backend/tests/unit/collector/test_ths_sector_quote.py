"""THS 板块行情快照 spider 单测：一览表亿元→元换算、概念 K 线派生。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from collector.spiders.ths_sector_quote import (
    ThsSectorQuoteCollector,
    concept_row_from_bars,
    transform_summary_row,
)

# stock_board_industry_summary_ths 行：总成交额单位亿元，数值/带 % 字符串两种形态
_SUMMARY_ROW = {
    "板块": "银行",
    "涨跌幅": "1.23%",
    "总成交额": 114.5,
    "上涨家数": 40,
    "下跌家数": 2,
    "领涨股": "平安银行",
}
_SUMMARY_ROW_NUMERIC = {
    "板块": "汽车整车",
    "涨跌幅": -0.56,
    "总成交额": 88.0,
    "上涨家数": 5,
    "下跌家数": 15,
    "领涨股": "-",
}


def _bar(trade_date: date, close: float | None, sector_code: str = "881121") -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=trade_date,
        close=close,
        amount=1.1e9,
        sector_code=sector_code,
        sector_name="白酒",
    )


@pytest.mark.unit
class TestTransformSummaryRow:
    def test_string_pct_and_amount_unit(self) -> None:
        row = transform_summary_row(_SUMMARY_ROW, "881121", date(2026, 9, 28))

        assert row is not None
        assert row["sector_type"] == "industry"
        assert row["sector_code"] == "881121"
        assert row["sector_name"] == "银行"
        assert row["change_pct"] == 1.23
        assert row["amount"] == 114.5 * 100_000_000.0  # 亿元 → 元，对齐东财/K线口径
        assert row["up_count"] == 40
        assert row["down_count"] == 2
        assert row["leader_stock_name"] == "平安银行"
        assert row["close"] is None  # 一览表均价非指数点位，置空
        assert row["source"] == "ths"

    def test_numeric_pct_and_dash_leader(self) -> None:
        row = transform_summary_row(_SUMMARY_ROW_NUMERIC, None, date(2026, 9, 28))

        assert row is not None
        assert row["change_pct"] == -0.56
        assert row["leader_stock_name"] is None
        assert row["sector_code"] == "汽车整车"  # 代码清单缺失退化为板块名

    def test_missing_name_skipped(self) -> None:
        assert transform_summary_row({"板块": None}, None, date(2026, 9, 28)) is None


@pytest.mark.unit
class TestConceptRowFromBars:
    def test_change_pct_from_prev_bar(self) -> None:
        d0, d1 = date(2026, 9, 25), date(2026, 9, 28)
        prev = _bar(d0, 100.0)
        cur = _bar(d1, 103.0)

        row = concept_row_from_bars([prev, cur], d1)

        assert row is not None
        assert row["sector_type"] == "concept"
        assert row["sector_code"] == "881121"
        assert row["sector_name"] == "白酒"
        assert row["close"] == 103.0  # 概念取 K 线真实指数点位
        assert row["change_pct"] == pytest.approx(3.0)
        assert row["amount"] == 1.1e9
        assert row["up_count"] is None  # 齐动维由检测层按缺失跳过
        assert row["source"] == "ths"

    def test_missing_target_bar_returns_none(self) -> None:
        bars = [_bar(date(2026, 9, 25), 100.0)]
        assert concept_row_from_bars(bars, date(2026, 9, 28)) is None

    def test_no_prev_bar_change_pct_none(self) -> None:
        row = concept_row_from_bars([_bar(date(2026, 9, 28), 100.0)], date(2026, 9, 28))

        assert row is not None
        assert row["change_pct"] is None
        assert row["close"] == 100.0


@pytest.mark.unit
class TestThsSectorQuoteCollector:
    async def test_collect_merges_industry_and_concept(self) -> None:
        collector = ThsSectorQuoteCollector(config={"source": "ths"})
        with patch(
            "collector.spiders.ths_sector_quote.run_in_thread",
            side_effect=lambda fn, *a: fn(*a),
        ), patch(
            "collector.spiders.ths_sector_quote.ThsSectorQuoteCollector._industry_code_map",
            return_value={"银行": "881121"},
        ), patch(
            "akshare.stock_board_industry_summary_ths",
            return_value=pd.DataFrame([_SUMMARY_ROW]),
        ), patch.object(
            ThsSectorQuoteCollector,
            "_collect_concept_from_kline",
            return_value=[
                {
                    "sector_type": "concept",
                    "sector_code": "885738",
                    "sector_name": "全息技术",
                    "trade_date": date(2026, 9, 28),
                    "close": 1000.0,
                    "change_pct": 2.0,
                    "amount": 5e8,
                    "turnover_rate": None,
                    "up_count": None,
                    "down_count": None,
                    "leader_stock_name": None,
                    "source": "ths",
                }
            ],
        ):
            items = await collector.collect(trade_date=date(2026, 9, 28))

        assert [i["sector_type"] for i in items] == ["industry", "concept"]
        assert items[0]["sector_code"] == "881121"

    async def test_collect_empty_raises(self) -> None:
        collector = ThsSectorQuoteCollector(config={"source": "ths"})
        with patch(
            "collector.spiders.ths_sector_quote.run_in_thread",
            side_effect=lambda fn, *a: fn(*a),
        ), patch(
            "collector.spiders.ths_sector_quote.ThsSectorQuoteCollector._industry_code_map",
            return_value={},
        ), patch(
            "akshare.stock_board_industry_summary_ths",
            return_value=pd.DataFrame(),
        ), patch.object(
            ThsSectorQuoteCollector,
            "_collect_concept_from_kline",
            return_value=[],
        ):
            with pytest.raises(RuntimeError, match="行业一览表无数据"):
                await collector.collect(trade_date=date(2026, 9, 28))
