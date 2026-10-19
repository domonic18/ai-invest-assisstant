"""港股采集 spider 单测：东财 clist/kline 行转写与新浪港股快照/日K 备源。"""

from collections.abc import Callable
from datetime import date
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.schemas.user import WatchlistItemCreate
from collector.spiders.eastmoney_hk_kline import EastmoneyHkKlineCollector
from collector.spiders.eastmoney_hk_stock_list import (
    EastmoneyHkStockListCollector,
)
from collector.spiders.sina_hk_kline import SinaHkKlineCollector
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
        full_page = [{"f12": f"{i:05d}", "f14": f"股{i}", "f100": "-"} for i in range(100)]
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
        return EastmoneyHkKlineCollector(config={"source": "eastmoney", "period": "daily"})

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
class TestSinaHkKlineCollector:
    """新浪港股日 K 备源：解析/派生列/截取窗口/零填充。"""

    @staticmethod
    def _df() -> "pd.DataFrame":
        return pd.DataFrame(
            {
                "date": ["2026-10-14", "2026-10-15", "2026-10-16"],
                "open": [421.4, 415.0, 424.0],
                "high": [430.4, 422.6, 428.8],
                "low": [416.4, 414.0, 415.8],
                "close": [423.4, 417.8, 417.8],
                "volume": [19933548.0, 20676017.0, 18752869.0],
                "amount": [8.443191e09, 8.651708e09, 7.901199e09],
            }
        )

    async def _collect(
        self, cutoff: date, symbols: list[str] | None = None
    ) -> tuple[list[dict[str, object]], AsyncMock]:
        collector = SinaHkKlineCollector(config={"source": "sina", "period": "daily"})
        with (
            patch(
                "collector.spiders.sina_hk_kline._cutoff_date",
                return_value=cutoff,
            ),
            patch(
                "collector.spiders.sina_hk_kline._fetch_hk_codes",
                new=AsyncMock(return_value=["00700"]),
            ),
            patch("akshare.stock_hk_daily", return_value=self._df()) as mock_daily,
            patch(
                "collector.spiders.sina_hk_kline.run_in_thread",
                side_effect=_fake_run_in_thread,
            ),
        ):
            items = await collector.collect(symbols=symbols, lookback_days=5)
        assert mock_daily.call_args.kwargs["adjust"] == "qfq"
        return items, mock_daily

    async def test_collect_derives_change_pct_and_amplitude(self) -> None:
        items, mock_daily = await self._collect(cutoff=date(2026, 10, 15))

        # cutoff 之前的行不落库（2026-10-14 被截掉）
        assert [i["trade_date"] for i in items] == [
            date(2026, 10, 15),
            date(2026, 10, 16),
        ]
        assert items[0]["close"] == 417.8
        # 涨跌幅/振幅由相邻收盘价推算：(417.8-423.4)/423.4、(422.6-414.0)/423.4
        assert items[0]["change_pct"] == -1.3226
        assert items[0]["amplitude"] == 2.0312
        # 417.8 平收：涨跌幅 0；振幅 (428.8-415.8)/417.8
        assert items[1]["change_pct"] == 0.0
        assert items[1]["amplitude"] == 3.1115
        # 新浪源无换手率，置 None 交由 update_skip_null 保留东财原值
        assert items[0]["turnover_rate"] is None
        # 缺省 symbols 时 akshare 收到的代码零填充 5 位
        assert mock_daily.call_args.kwargs["symbol"] == "00700"

    async def test_collect_zfills_short_symbol(self) -> None:
        _, mock_daily = await self._collect(cutoff=date(2026, 10, 15), symbols=["700"])
        assert mock_daily.call_args.kwargs["symbol"] == "00700"

    async def test_collect_empty_df_returns_no_rows(self) -> None:
        collector = SinaHkKlineCollector(config={"source": "sina", "period": "daily"})
        with (
            patch(
                "collector.spiders.sina_hk_kline._cutoff_date",
                return_value=date(2026, 10, 15),
            ),
            patch("akshare.stock_hk_daily", return_value=pd.DataFrame()),
            patch(
                "collector.spiders.sina_hk_kline.run_in_thread",
                side_effect=_fake_run_in_thread,
            ),
        ):
            items = await collector.collect(symbols=["00700"], lookback_days=5)
        assert items == []

    async def test_collect_survives_single_stock_failure(self) -> None:
        collector = SinaHkKlineCollector(config={"source": "sina", "period": "daily"})
        with (
            patch(
                "collector.spiders.sina_hk_kline._cutoff_date",
                return_value=date(2026, 10, 15),
            ),
            patch(
                "akshare.stock_hk_daily",
                side_effect=[KeyError("date"), self._df()],
            ),
            patch(
                "collector.spiders.sina_hk_kline.run_in_thread",
                side_effect=_fake_run_in_thread,
            ),
        ):
            items = await collector.collect(symbols=["00700", "09988"], lookback_days=5)

        # 00700 抓取抛错被跳过，09988 正常产出且归属正确
        assert {i["stock_code"] for i in items} == {"09988"}

    async def test_collect_raises_when_all_stocks_fail(self) -> None:
        collector = SinaHkKlineCollector(config={"source": "sina", "period": "daily"})
        with (
            patch(
                "collector.spiders.sina_hk_kline._cutoff_date",
                return_value=date(2026, 10, 15),
            ),
            patch("akshare.stock_hk_daily", side_effect=KeyError("date")),
            patch(
                "collector.spiders.sina_hk_kline.run_in_thread",
                side_effect=_fake_run_in_thread,
            ),
            pytest.raises(RuntimeError, match="全量失败"),
        ):
            await collector.collect(symbols=["00700", "09988"], lookback_days=5)

    async def test_update_skip_null_and_transform_roundtrip(self) -> None:
        collector = SinaHkKlineCollector(config={"source": "sina", "period": "daily"})
        assert collector.update_skip_null is True
        transformed = await collector.transform(
            {
                "stock_code": "00700",
                "trade_date": date(2026, 10, 16),
                "open": 424.0,
                "high": 428.8,
                "low": 415.8,
                "close": 417.8,
                "volume": 18752869.0,
                "amount": 7.901199e09,
                "amplitude": 3.1125,
                "change_pct": 0.0,
                "turnover_rate": None,
            }
        )
        assert await collector.validate(transformed) is True
        assert transformed["volume"] == 18752869
        assert transformed["turnover_rate"] is None


@pytest.mark.unit
def test_watchlist_item_create_accepts_hk_code() -> None:
    data = WatchlistItemCreate(stock_code="00700", market="hk")
    assert data.stock_code == "00700"
    assert data.market == "hk"
