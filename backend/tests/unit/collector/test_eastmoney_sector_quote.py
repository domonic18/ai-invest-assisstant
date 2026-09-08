"""东财板块行情快照 spider 单测：clist 行转写按 fltt=2 真实口径。"""

from datetime import date
from unittest.mock import patch

import pytest

from collector.spiders.eastmoney_sector_quote import (
    EastmoneySectorQuoteCollector,
    fetch_sector_rows,
    transform_sector_row,
)

# fltt=2 数值已缩放；`-` 为停牌/缺失占位（行情 15 分钟延迟镜像常见）
_INDUSTRY_ROW = {
    "f12": "BK0475",
    "f14": "银行",
    "f2": 2450.25,
    "f3": 1.23,
    "f6": 12345678900.0,
    "f8": 0.85,
    "f104": 40,
    "f105": 2,
    "f128": "平安银行",
}
_CONCEPT_ROW = {
    "f12": "BK0655",
    "f14": "全息技术",
    "f2": "-",
    "f3": "-",
    "f6": "-",
    "f8": "-",
    "f104": "-",
    "f105": "-",
    "f128": "-",
}


@pytest.mark.unit
class TestTransformSectorRow:
    def test_numeric_row(self) -> None:
        row = transform_sector_row(_INDUSTRY_ROW, "industry", date(2026, 9, 8))

        assert row is not None
        assert row["sector_code"] == "BK0475"
        assert row["sector_name"] == "银行"
        assert row["close"] == 2450.25
        assert row["change_pct"] == 1.23
        assert row["amount"] == 12345678900.0
        assert row["turnover_rate"] == 0.85
        assert row["up_count"] == 40
        assert row["down_count"] == 2
        assert row["leader_stock_name"] == "平安银行"
        assert row["source"] == "eastmoney"

    def test_dash_placeholders_become_none(self) -> None:
        row = transform_sector_row(_CONCEPT_ROW, "concept", date(2026, 9, 8))

        assert row is not None
        assert row["close"] is None
        assert row["change_pct"] is None
        assert row["up_count"] is None
        assert row["leader_stock_name"] is None

    def test_missing_code_skipped(self) -> None:
        assert transform_sector_row({"f12": None, "f14": "无名"}, "industry", date(2026, 9, 8)) is None


@pytest.mark.unit
class TestEastmoneySectorQuoteCollector:
    async def test_collect_merges_both_sector_types(self) -> None:
        collector = EastmoneySectorQuoteCollector(config={"source": "eastmoney"})
        with patch(
            "collector.spiders.eastmoney_sector_quote.fetch_sector_rows",
            side_effect=[[_INDUSTRY_ROW], [_CONCEPT_ROW, {"f12": None, "f14": "缺代码"}]],
        ) as mock_fetch:
            items = await collector.collect(trade_date=date(2026, 9, 8))

        # 缺代码行跳过，两种 sector_type 各留有效行
        assert [i["sector_type"] for i in items] == ["industry", "concept"]
        assert {i["sector_code"] for i in items} == {"BK0475", "BK0655"}
        assert all(i["trade_date"] == date(2026, 9, 8) for i in items)
        assert mock_fetch.call_count == 2

    async def test_collect_defaults_to_latest_trading_day(self) -> None:
        collector = EastmoneySectorQuoteCollector(config={"source": "eastmoney"})
        with patch(
            "collector.spiders.eastmoney_sector_quote.fetch_sector_rows",
            return_value=[_INDUSTRY_ROW],
        ), patch(
            "collector.spiders.eastmoney_sector_quote.latest_trading_day",
            return_value=date(2026, 9, 7),
        ):
            items = await collector.collect()

        assert items and items[0]["trade_date"] == date(2026, 9, 7)

    async def test_pagination_follows_total(self) -> None:
        # 满页(100)继续翻，短页即停：total=150 → 两页 150 行
        full_page = [{"f12": f"BK{i:04d}", "f14": f"板块{i}"} for i in range(100)]
        pages = [
            {"total": 150, "diff": full_page},
            {"total": 150, "diff": full_page[:50]},
        ]
        with patch(
            "collector.spiders.eastmoney_sector_quote.fetch_sector_page",
            side_effect=pages,
        ) as mock_fetch:
            rows = fetch_sector_rows("m:90+t:2")

        assert len(rows) == 150
        assert mock_fetch.call_count == 2

    async def test_pagination_stops_when_total_covered(self) -> None:
        # 第二页虽满页但已覆盖 total，立即停（防服务端 total 与实收不一致时死循环）
        full_page = [{"f12": f"BK{i:04d}", "f14": f"板块{i}"} for i in range(100)]
        pages = [
            {"total": 150, "diff": full_page},
            {"total": 150, "diff": full_page},
        ]
        with patch(
            "collector.spiders.eastmoney_sector_quote.fetch_sector_page",
            side_effect=pages,
        ) as mock_fetch:
            rows = fetch_sector_rows("m:90+t:3")

        assert len(rows) == 200 >= 150
        assert mock_fetch.call_count == 2
