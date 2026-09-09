"""Yahoo 全球指数历史回填 spider 单测。"""

from unittest.mock import patch

import pytest
from curl_cffi.requests import exceptions as cffi_exceptions

from app.core.constants import GLOBAL_INDEX_CODES
from collector.spiders.yahoo_global_index import YAHOO_SYMBOLS, YahooGlobalIndexCollector


def _chart_result(rows: list[tuple[int, float | None, float | None, float]]) -> dict:
    """构造 chart.result[0]：rows = (timestamp, open, close, volume)。"""
    return {
        "timestamp": [r[0] for r in rows],
        "indicators": {
            "quote": [
                {
                    "open": [r[1] for r in rows],
                    "high": [(r[2] or 0) + 10 for r in rows],
                    "low": [(r[2] or 0) - 10 if r[2] else None for r in rows],
                    "close": [r[2] for r in rows],
                    "volume": [r[3] for r in rows],
                }
            ]
        },
    }


# 2026-09-01 ~ 09-03（UTC 午间时间戳，不跨日）
_TS = [1788271200, 1788357600, 1788444000]
_DATES = ["2026-09-01", "2026-09-02", "2026-09-03"]


@pytest.mark.unit
class TestYahooGlobalIndex:
    async def test_transform_chart_chain(self) -> None:
        result = _chart_result(
            [
                (_TS[0], 24500.0, 24600.1, 1_000_000),
                (_TS[1], None, 24800.5, 1_100_000),  # open 缺失但 close 有效
                (_TS[2], 24700.0, 24500.0, 900_000),
            ]
        )
        rows = YahooGlobalIndexCollector._transform_chart("HSI", result)

        assert [r["trade_date"].isoformat() for r in rows] == _DATES
        assert rows[0]["close"] == 24600.1
        assert rows[0]["change_pct"] is None
        assert rows[1]["open"] is None
        assert rows[1]["change_pct"] == pytest.approx(0.8148, rel=1e-3)
        assert rows[2]["change_pct"] == pytest.approx(-1.2117, rel=1e-3)
        assert rows[2]["volume"] == 900_000
        assert all(r["index_code"] == "HSI" and r["source"] == "yahoo" for r in rows)

    async def test_skips_null_close(self) -> None:
        result = _chart_result(
            [
                (_TS[0], 100.0, 101.0, 10),
                (_TS[1], 101.0, None, 10),  # 停牌/缺失日跳过
                (_TS[2], 101.0, 102.0, 10),
            ]
        )
        rows = YahooGlobalIndexCollector._transform_chart("N225", result)
        # 缺失日跳过后，涨跌幅基于前一有效 close 顺算
        assert [r["trade_date"].isoformat() for r in rows] == [_DATES[0], _DATES[2]]
        assert rows[1]["change_pct"] == pytest.approx(0.9901, rel=1e-3)

    async def test_collect_maps_all_symbols(self) -> None:
        collector = YahooGlobalIndexCollector(config={"source": "yahoo"})

        def fake_fetch(symbol: str, proxies=None) -> dict:
            return _chart_result([(_TS[0], 100.0, 101.0, 1)])

        with patch(
            "collector.spiders.yahoo_global_index._fetch_chart",
            side_effect=fake_fetch,
        ):
            items = await collector.collect()

        assert {i["index_code"] for i in items} == set(YAHOO_SYMBOLS)

    async def test_collect_symbols_filter(self) -> None:
        collector = YahooGlobalIndexCollector(config={"source": "yahoo"})
        with patch("collector.spiders.yahoo_global_index._fetch_chart") as mock_fetch:
            mock_fetch.return_value = _chart_result([(_TS[0], 100.0, 101.0, 1)])
            items = await collector.collect(symbols=["SPX"])
        assert [i["index_code"] for i in items] == ["SPX"]
        mock_fetch.assert_called_once_with("^GSPC", None)

    async def test_symbols_registry_subset(self) -> None:
        """回填清单必须都登记在 GLOBAL_INDEX_CODES，避免落库孤儿 code。"""
        assert set(YAHOO_SYMBOLS) <= set(GLOBAL_INDEX_CODES)
        # 且只覆盖非 tushare/mof 源的指标（GC00Y/DXY 东财有历史、美债走 tushare；
        # USDCNH Yahoo 仅当日 1 bar 无历史，不回填）
        assert "GC00Y" not in YAHOO_SYMBOLS
        assert "US10Y" not in YAHOO_SYMBOLS
        assert "US30Y" not in YAHOO_SYMBOLS
        assert "USDCNH" not in YAHOO_SYMBOLS
        assert YAHOO_SYMBOLS["SPX"] == "^GSPC"
        assert YAHOO_SYMBOLS["USDCNY"] == "USDCNY=X"
        assert YAHOO_SYMBOLS["B00Y"] == "BZ=F"

    async def test_collect_empty_result_skips(self) -> None:
        collector = YahooGlobalIndexCollector(config={"source": "yahoo"})
        with patch(
            "collector.spiders.yahoo_global_index._fetch_chart", return_value=None
        ):
            items = await collector.collect(symbols=["DJIA"])
        assert items == []

    async def test_collect_tolerates_single_symbol_failure(self) -> None:
        """单 symbol 限流(429)不拖垮整批：其余 code 正常回填。"""
        collector = YahooGlobalIndexCollector(config={"source": "yahoo"})

        def fake_fetch(symbol: str, proxies=None) -> dict:
            if symbol == "^HSTECH":
                raise cffi_exceptions.ConnectionError("connection reset")
            return _chart_result([(_TS[0], 100.0, 101.0, 1)])

        with patch(
            "collector.spiders.yahoo_global_index._fetch_chart",
            side_effect=fake_fetch,
        ):
            items = await collector.collect(symbols=["HSI", "HSTECH", "SPX"])

        assert {i["index_code"] for i in items} == {"HSI", "SPX"}

    async def test_collect_raises_when_all_symbols_fail(self) -> None:
        """全部失败向上抛错，走渠道 fallback 语义。"""
        collector = YahooGlobalIndexCollector(config={"source": "yahoo"})
        with patch(
            "collector.spiders.yahoo_global_index._fetch_chart",
            side_effect=cffi_exceptions.ConnectionError("connection reset"),
        ):
            with pytest.raises(cffi_exceptions.ConnectionError):
                await collector.collect(symbols=["HSI", "SPX"])

    async def test_collect_passes_channel_proxy_to_fetch(self) -> None:
        """渠道注入的 proxy_url 组为 http/https 双协议 dict 下传。"""
        collector = YahooGlobalIndexCollector(
            config={"source": "yahoo", "proxy_url": "http://u:p@1.2.3.4:17890"}
        )
        with patch("collector.spiders.yahoo_global_index._fetch_chart") as mock_fetch:
            mock_fetch.return_value = _chart_result([(_TS[0], 100.0, 101.0, 1)])
            await collector.collect(symbols=["SPX"])

        mock_fetch.assert_called_once_with(
            "^GSPC", {"http": "http://u:p@1.2.3.4:17890", "https": "http://u:p@1.2.3.4:17890"}
        )

    async def test_fetch_chart_passes_proxies_and_timeout(self) -> None:
        """_fetch_chart 走 chrome_get（Chrome 指纹）并透传 proxies/超时。"""
        from collector.spiders import yahoo_global_index as mod

        class _FakeResponse:
            def json(self) -> dict:
                return {"chart": {"result": [{"ok": 1}]}}

        proxies = {"http": "http://u:p@1.2.3.4:17890", "https": "http://u:p@1.2.3.4:17890"}
        with patch.object(mod, "chrome_get", return_value=_FakeResponse()) as mock_get:
            result = mod._fetch_chart("^GSPC", proxies)

        assert result == {"ok": 1}
        mock_get.assert_called_once_with(
            "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC",
            params={"range": "1y", "interval": "1d"},
            timeout=30,
            proxies=proxies,
        )

    async def test_fetch_chart_without_proxies(self) -> None:
        from collector.spiders import yahoo_global_index as mod

        class _FakeResponse:
            def json(self) -> dict:
                return {"chart": {"result": [None]}}

        with patch.object(mod, "chrome_get", return_value=_FakeResponse()) as mock_get:
            assert mod._fetch_chart("BZ=F") is None

        mock_get.assert_called_once_with(
            "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F",
            params={"range": "1y", "interval": "1d"},
            timeout=30,
            proxies=None,
        )
