"""港股采集 spider 单测：东财 clist/kline 行转写与新浪港股快照过滤。"""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.user import WatchlistItemCreate
from collector.spiders.eastmoney_hk_kline import EastmoneyHkKlineCollector
from collector.spiders.eastmoney_hk_stock_list import (
    EastmoneyHkStockListCollector,
)
from collector.spiders.sina_hk_quote import SinaHkQuoteCollector


async def _fake_run_in_thread(fn: Callable[..., object], *args: object, **kwargs: object):
    return fn(*args, **kwargs)

# 东财 clist 港股行（fltt=2 数值已缩放）
_CLIST_ROW = {"f12": "00700", "f14": "腾讯控股", "f100": "通信服务"}
_CLIST_ROW_SHORT_CODE = {"f12": "9988", "f14": "阿里巴巴-W", "f100": "电子商务"}

# push2his klines CSV（f51 日期 f52 开 f53 收 f54 高 f55 低 f56 量 f57 额
# f58 振幅 f59 涨跌幅 f60 换手率）
_KLINES = [
    "2026-10-16,415.0,417.8,419.2,413.6,12345600,5153000000.0,1.35,0.68,0.05",
    "2026-10-15,410.2,414.9,415.8,408.0,11000000,4560000000.0,1.90,1.15,0.04",
]


@pytest.mark.unit
class TestEastmoneyHkStockListCollector:
    async def test_collect_zfills_and_maps_market(self) -> None:
        collector = EastmoneyHkStockListCollector(config={"source": "eastmoney"})
        with patch.object(
            collector, "_fetch_all", return_value=[_CLIST_ROW, _CLIST_ROW_SHORT_CODE]
        ):
            items = await collector.collect()

        assert items[0]["stock_code"] == "00700"
        assert items[0]["market"] == "hk"
        assert items[0]["stock_name"] == "腾讯控股"
        assert items[0]["industry_level_1"] == "通信服务"
        # 4 位代码零填充为 5 位
        assert items[1]["stock_code"] == "09988"

    async def test_collect_filters_by_symbols(self) -> None:
        collector = EastmoneyHkStockListCollector(config={"source": "eastmoney"})
        with patch.object(
            collector, "_fetch_all", return_value=[_CLIST_ROW, _CLIST_ROW_SHORT_CODE]
        ):
            items = await collector.collect(symbols=["00700"])

        assert [i["stock_code"] for i in items] == ["00700"]

    async def test_pagination_follows_total(self) -> None:
        collector = EastmoneyHkStockListCollector(config={"source": "eastmoney"})
        full_page = [
            {"f12": f"{i:05d}", "f14": f"股{i}", "f100": "-"} for i in range(100)
        ]
        pages = [
            {"total": 150, "diff": full_page},
            {"total": 150, "diff": full_page[:50]},
        ]
        with patch.object(collector, "_request_page", side_effect=pages) as mock_page:
            rows = collector._fetch_all()

        assert len(rows) == 150
        assert mock_page.call_count == 2

    async def test_transform_validate(self) -> None:
        collector = EastmoneyHkStockListCollector(config={"source": "eastmoney"})
        transformed = await collector.transform(
            {
                "stock_code": "00700",
                "stock_name": "腾讯控股",
                "market": "hk",
                "industry_level_1": "通信服务",
            }
        )
        assert await collector.validate(transformed) is True
        assert transformed["market"] == "hk"


@pytest.mark.unit
class TestEastmoneyHkKlineCollector:
    def _collector(self) -> EastmoneyHkKlineCollector:
        return EastmoneyHkKlineCollector(
            config={"source": "eastmoney", "period": "daily"}
        )

    async def test_collect_parses_klines_csv(self) -> None:
        collector = self._collector()
        response = type("R", (), {"json": lambda self: {"data": {"klines": _KLINES}}})()
        with (
            patch(
                "collector.spiders.eastmoney_hk_kline._fetch_hk_codes",
                new=AsyncMock(return_value=["00700"]),
            ),
            patch(
                "collector.spiders.eastmoney_hk_kline.eastmoney_get_chrome",
                return_value=response,
            ) as mock_get,
            patch(
                "collector.spiders.eastmoney_hk_kline.run_in_thread",
                side_effect=_fake_run_in_thread,
            ),
        ):
            items = await collector.collect(lookback_days=5)

        assert len(items) == 2
        assert items[0]["stock_code"] == "00700"
        assert str(items[0]["trade_date"]) == "2026-10-16"
        assert items[0]["close"] == "417.8"
        assert items[0]["change_pct"] == "0.68"
        secid = mock_get.call_args.kwargs["params"]["secid"]
        assert secid == "116.00700"
        # 前复权固定 fqt=1、日线 klt=101
        assert mock_get.call_args.kwargs["params"]["fqt"] == 1
        assert mock_get.call_args.kwargs["params"]["klt"] == 101

    async def test_transform_validate_roundtrip(self) -> None:
        collector = self._collector()
        transformed = await collector.transform(
            {
                "stock_code": "00700",
                "trade_date": "2026-10-16",
                "open": "415.0",
                "high": "419.2",
                "low": "413.6",
                "close": "417.8",
                "volume": "12345600",
                "amount": "5153000000.0",
                "amplitude": "1.35",
                "change_pct": "0.68",
                "turnover_rate": "0.05",
            }
        )
        assert await collector.validate(transformed) is True
        assert transformed["close"] == 417.8
        assert transformed["volume"] == 12345600


@pytest.mark.unit
class TestSinaHkQuoteCollector:
    async def test_collect_filters_requested_codes(self) -> None:
        collector = SinaHkQuoteCollector(config={"source": "sina"})
        df = type(
            "DF",
            (),
            {
                "empty": False,
                "iterrows": lambda self: iter(
                    [
                        (
                            None,
                            {
                                "日期时间": "2026/10/16 16:08:22",
                                "代码": "00700",
                                "中文名称": "腾讯控股",
                                "最新价": 417.8,
                                "涨跌额": 2.8,
                                "涨跌幅": 0.68,
                                "昨收": 415.0,
                                "今开": 415.0,
                                "最高": 419.2,
                                "最低": 413.6,
                                "成交量": 12345600,
                                "成交额": 5153000000.0,
                                "买一": 417.6,
                                "卖一": 417.8,
                            },
                        ),
                        (
                            None,
                            {"代码": "09988", "中文名称": "阿里巴巴-W", "最新价": 102.4},
                        ),
                    ]
                ),
            },
        )()
        with (
            patch("akshare.stock_hk_spot", return_value=df),
            patch(
                "collector.spiders.sina_hk_quote.run_in_thread",
                side_effect=_fake_run_in_thread,
            ),
        ):
            items = await collector.collect(symbols=["00700"])

        assert [i["stock_code"] for i in items] == ["00700"]
        assert items[0]["stock_name"] == "腾讯控股"
        assert items[0]["price"] == 417.8
        assert items[0]["bid"] == 417.6
        assert items[0]["timestamp"] == "2026/10/16 16:08:22"

    async def test_collect_skips_fetch_when_no_requested(self) -> None:
        collector = SinaHkQuoteCollector(config={"source": "sina"})
        with (
            patch("akshare.stock_hk_spot") as mock_spot,
            patch(
                "collector.spiders.sina_hk_quote._fetch_watchlist_hk_codes",
                new=AsyncMock(return_value=[]),
            ),
        ):
            items = await collector.collect()

        assert items == []
        mock_spot.assert_not_called()

    async def test_validate_requires_positive_price(self) -> None:
        collector = SinaHkQuoteCollector(config={"source": "sina"})
        assert await collector.validate({"stock_code": "00700", "price": 417.8}) is True
        assert await collector.validate({"stock_code": "00700", "price": None}) is False


@pytest.mark.unit
def test_watchlist_item_create_accepts_hk_code() -> None:
    data = WatchlistItemCreate(stock_code="00700", market="hk")
    assert data.stock_code == "00700"
    assert data.market == "hk"
