"""全球指标 spider 单测：fixture 按探针真实响应转写。"""

import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.eastmoney_global_index import EastmoneyGlobalIndexCollector
from collector.spiders.tushare_us_yield import TushareUsYieldCollector


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


@pytest.mark.unit
class TestEastmoneyGlobalIndexRealtime:
    async def test_maps_ulist_diff(self) -> None:
        collector = EastmoneyGlobalIndexCollector(config={"source": "eastmoney"})
        payload = {
            "data": {
                "diff": [
                    {
                        "f2": 4363.6,  # COMEX 黄金最新价（fltt=2 已缩放）
                        "f3": -1.21,
                        "f12": "GC00Y",
                        "f13": 101,
                        "f15": 4510.5,
                        "f16": 4329.2,
                        "f17": 4498.7,
                        "f124": 1788235200,  # 2026-09-01 12:00 Asia/Shanghai
                    },
                    {
                        "f2": 99.75,
                        "f3": 0.09,
                        "f12": "UDI",
                        "f13": 100,
                        "f15": 99.81,
                        "f16": 99.35,
                        "f17": 99.68,
                        "f124": 1788235200,
                    },
                ]
            }
        }
        with patch(
            "collector.spiders.eastmoney_global_index.eastmoney_get_chrome",
            return_value=_response(payload),
        ):
            items = await collector.collect()

        assert [i["index_code"] for i in items] == ["GC00Y", "DXY"]
        gold = items[0]
        assert gold["close"] == 4363.6
        assert gold["change_pct"] == -1.21
        assert gold["open"] == 4498.7
        assert gold["high"] == 4510.5
        assert gold["low"] == 4329.2
        assert gold["source"] == "eastmoney"
        assert gold["trade_date"].isoformat() == "2026-09-01"

    async def test_skips_unknown_secid_and_missing_close(self) -> None:
        collector = EastmoneyGlobalIndexCollector(config={"source": "eastmoney"})
        payload = {
            "data": {
                "diff": [
                    {"f2": "-", "f12": "GC00Y", "f13": 101},
                    {"f2": 100.0, "f12": "OTHER", "f13": 100},
                ]
            }
        }
        with patch(
            "collector.spiders.eastmoney_global_index.eastmoney_get_chrome",
            return_value=_response(payload),
        ):
            items = await collector.collect()
        assert items == []

    async def test_symbols_filter(self) -> None:
        collector = EastmoneyGlobalIndexCollector(config={"source": "eastmoney"})
        payload = {"data": {"diff": []}}
        with patch(
            "collector.spiders.eastmoney_global_index.eastmoney_get_chrome",
            return_value=_response(payload),
        ) as mock_get:
            await collector.collect(symbols=["DXY"])
        secids = mock_get.call_args.kwargs["params"]["secids"]
        assert secids == "100.UDI"


@pytest.mark.unit
class TestEastmoneyGlobalIndexHistory:
    async def test_dxy_history_change_chain(self) -> None:
        collector = EastmoneyGlobalIndexCollector(config={"source": "eastmoney"})
        payload = {
            "data": {
                "klines": [
                    "2026-08-31,99.68,99.42,99.72,99.39,0",
                    "2026-09-01,99.41,99.66,99.72,99.35,0",
                    "2026-09-02,99.68,99.75,99.81,99.64,0",
                ]
            }
        }
        with patch(
            "collector.spiders.eastmoney_global_index.eastmoney_get_chrome",
            return_value=_response(payload),
        ):
            items = await collector.collect(symbols=["DXY"], history_days=3)

        assert len(items) == 3
        assert items[0]["change_pct"] is None
        assert items[1]["change_pct"] == pytest.approx(0.2414, rel=1e-3)
        assert items[2]["change_pct"] == pytest.approx(0.0903, rel=1e-3)
        assert [i["trade_date"].isoformat() for i in items] == [
            "2026-08-31",
            "2026-09-01",
            "2026-09-02",
        ]

    async def test_gold_history_via_akshare(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_akshare = types.ModuleType("akshare")

        def fake_hist(symbol: str) -> pd.DataFrame:
            assert symbol == "GC"
            return pd.DataFrame(
                {
                    "date": ["2026-08-31", "2026-09-01"],
                    "open": [4490.0, 4498.7],
                    "high": [4500.0, 4510.5],
                    "low": [4400.0, 4369.7],
                    "close": [4490.2, 4375.7],
                    "volume": [12345, 0],
                }
            )

        fake_akshare.futures_foreign_hist = fake_hist
        monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

        collector = EastmoneyGlobalIndexCollector(config={"source": "eastmoney"})
        items = await collector.collect(symbols=["GC00Y"], history_days=2)

        assert len(items) == 2
        assert items[0]["close"] == 4490.2
        assert items[0]["change_pct"] is None
        assert items[1]["close"] == 4375.7
        assert items[1]["change_pct"] == pytest.approx(-2.55, rel=1e-2)
        assert items[1]["index_code"] == "GC00Y"


@pytest.mark.unit
class TestTushareUsYield:
    async def test_maps_y2_y10_with_bp_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        df = pd.DataFrame(
            {
                "date": ["2026-08-29", "2026-09-01", "2026-09-02"],
                "y2": [4.39, None, 4.42],
                "y10": [4.79, 4.81, 4.80],
            }
        )
        fake_ts = types.ModuleType("tushare")
        fake_ts.pro_api = lambda token: types.SimpleNamespace(us_tycr=lambda: df)
        monkeypatch.setitem(sys.modules, "tushare", fake_ts)

        collector = TushareUsYieldCollector(config={"api_key": "token"})
        items = await collector.collect()

        us2y = [i for i in items if i["index_code"] == "US2Y"]
        # NaN 日跳过并断开 bp 连差基准
        assert [i["trade_date"].isoformat() for i in us2y] == [
            "2026-08-29",
            "2026-09-02",
        ]
        assert us2y[0]["change_pct"] is None
        assert us2y[1]["change_pct"] is None  # 前一有效值隔了缺失日，不连差
        assert us2y[1]["close"] == 4.42

        us10y = [i for i in items if i["index_code"] == "US10Y"]
        assert us10y[1]["change_pct"] == pytest.approx(2.0)  # +2bp
        assert us10y[2]["change_pct"] == pytest.approx(-1.0)  # -1bp
        assert all(i["source"] == "tushare" for i in items)

    async def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        collector = TushareUsYieldCollector(config={})
        with pytest.raises(ValueError, match="api_key"):
            await collector.collect()

    async def test_symbols_filter_empty(self) -> None:
        collector = TushareUsYieldCollector(config={"api_key": "token"})
        items = await collector.collect(symbols=["GC00Y"])  # 非 tushare 源
        assert items == []
