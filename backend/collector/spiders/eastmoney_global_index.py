"""东方财富全球指标采集器（COMEX 黄金 / 美元指数）。

实时快照走 push2delay ulist（fltt=2 数值已缩放：f2 最新价、f3 涨跌幅、
f15/f16/f17 高/低/开、f124 更新时间戳）。push2delay 无日 K、push2his 对
外盘期货 secid（101.GC00Y）按路径断连，历史回补分双路：

- DXY：push2his kline（Chrome 指纹，实测可用）
- GC00Y：akshare ``futures_foreign_hist``（新浪源，英文列 date/open/high/low/close/volume）
"""

from datetime import datetime
from typing import Any, ClassVar

import structlog

from app.core.clock import CN_TZ, today_cn
from app.core.constants import GLOBAL_INDEX_CODES
from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.http_client import eastmoney_get_chrome
from collector.core.parsing import parse_date, to_float, to_int

logger = structlog.get_logger(__name__)

_ULIST_URL = "https://push2delay.eastmoney.com/api/qt/ulist.np/get"
_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_UT = "f057cbcbce2a86e2866ab8877db1d059"


class EastmoneyGlobalIndexCollector(PostgresCollector):
    """东财全球指标采集器，写入 quote_global_index_daily。"""

    table = "quote_global_index_daily"
    conflict_key = "index_code, trade_date"
    update_columns: ClassVar[list[str]] = [
        "open",
        "high",
        "low",
        "close",
        "change_pct",
        "volume",
        "amount",
        "source",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["index_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["index_code", "trade_date", "close"]

    async def collect(
        self,
        symbols: list[str] | None = None,
        history_days: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        codes = [
            code
            for code, meta in GLOBAL_INDEX_CODES.items()
            if meta["data_source"] == "eastmoney"
            and (not symbols or code in set(symbols))
        ]
        if not codes:
            return []
        items: list[dict[str, Any]] = await run_in_thread(
            self._collect_sync, codes, history_days
        )
        return items

    def _collect_sync(
        self, codes: list[str], history_days: int | None
    ) -> list[dict[str, Any]]:
        if history_days:
            return self._collect_history(codes, int(history_days))
        return self._collect_realtime(codes)

    # ------------------------------------------------------------------
    # 实时快照（push2delay ulist）
    # ------------------------------------------------------------------

    def _collect_realtime(self, codes: list[str]) -> list[dict[str, Any]]:
        secid_to_code = {GLOBAL_INDEX_CODES[c]["secid"]: c for c in codes}
        response = eastmoney_get_chrome(
            _ULIST_URL,
            params={
                "secids": ",".join(secid_to_code),
                "fields": "f2,f3,f12,f13,f15,f16,f17,f124",
                "fltt": "2",
                "invt": "2",
                "np": "1",
            },
        )
        diff: list[dict[str, Any]] = (
            (response.json().get("data") or {}).get("diff") or []
        )
        items: list[dict[str, Any]] = []
        for row in diff:
            secid = f"{row.get('f13')}.{row.get('f12')}"
            code = secid_to_code.get(secid)
            if code is None:
                continue
            close = to_float(row.get("f2"))
            if close is None:
                continue
            update_ts = to_int(row.get("f124"))
            trade_date = (
                datetime.fromtimestamp(update_ts, tz=CN_TZ).date()
                if update_ts
                else today_cn()
            )
            items.append(
                {
                    "index_code": code,
                    "trade_date": trade_date,
                    "open": to_float(row.get("f17")),
                    "high": to_float(row.get("f15")),
                    "low": to_float(row.get("f16")),
                    "close": close,
                    "change_pct": to_float(row.get("f3")),
                    "volume": None,
                    "amount": None,
                    "source": "eastmoney",
                }
            )
        return items

    # ------------------------------------------------------------------
    # 历史回补（history_days 指定末 N 个交易日）
    # ------------------------------------------------------------------

    def _collect_history(self, codes: list[str], days: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for code in codes:
            if code == "DXY":
                rows = self._dxy_history(days)
            else:
                rows = self._gold_history(days)
            items.extend(rows)
        return items

    def _dxy_history(self, days: int) -> list[dict[str, Any]]:
        """美元指数日 K：push2his kline（klines CSV：日期,开,收,高,低,量）。"""
        response = eastmoney_get_chrome(
            _KLINE_URL,
            params={
                "secid": GLOBAL_INDEX_CODES["DXY"]["secid"],
                "klt": "101",
                "fqt": "1",
                "lmt": str(days),
                "end": "20500000",
                "iscca": "1",
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "ut": _UT,
                "forcect": "1",
            },
        )
        data = response.json().get("data") or {}
        rows: list[dict[str, Any]] = []
        prev_close: float | None = None
        # push2his klines 按日期升序返回，直接顺算相邻涨跌幅
        for kline in data.get("klines") or []:
            parts = kline.split(",")
            if len(parts) < 5:
                continue
            close = to_float(parts[2])
            change_pct = (
                round((close - prev_close) / prev_close * 100, 4)
                if close is not None and prev_close
                else None
            )
            rows.append(
                {
                    "index_code": "DXY",
                    "trade_date": parse_date(parts[0]),
                    "open": to_float(parts[1]),
                    "high": to_float(parts[3]),
                    "low": to_float(parts[4]),
                    "close": close,
                    "change_pct": change_pct,
                    "volume": None,
                    "amount": None,
                    "source": "eastmoney",
                }
            )
            if close is not None:
                prev_close = close
        return rows

    def _gold_history(self, days: int) -> list[dict[str, Any]]:
        """COMEX 黄金日 K：akshare futures_foreign_hist（新浪源，全历史）。"""
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.futures_foreign_hist(symbol="GC")
        if df is None or df.empty:
            return []
        df = df.tail(days)
        rows: list[dict[str, Any]] = []
        prev_close: float | None = None
        for _, row in df.iterrows():
            close = to_float(row.get("close"))
            change_pct = (
                round((close - prev_close) / prev_close * 100, 4)
                if close is not None and prev_close
                else None
            )
            rows.append(
                {
                    "index_code": "GC00Y",
                    "trade_date": parse_date(str(row.get("date"))[:10]),
                    "open": to_float(row.get("open")),
                    "high": to_float(row.get("high")),
                    "low": to_float(row.get("low")),
                    "close": close,
                    "change_pct": change_pct,
                    "volume": to_int(row.get("volume")),
                    "amount": None,
                    "source": "eastmoney",
                }
            )
            if close is not None:
                prev_close = close
        return rows
