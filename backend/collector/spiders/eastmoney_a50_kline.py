"""东方财富富时中国 A50 期指日 K 采集器。"""

from typing import Any

from collector.core.async_helpers import run_in_thread
from collector.core.http_client import eastmoney_get
from collector.core.parsing import parse_date
from collector.spiders.kline_base import BaseKlineCollector

_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
# 104 = 东财全球期货市场代码；CN00Y = A50 期指当月连续
_SECID = "104.CN00Y"
_STOCK_CODE = "CN00Y"
# f51 日期 f52 开 f53 收 f54 高 f55 低 f56 量（字段顺序即 klines CSV 列顺序）
_FIELDS2 = "f51,f52,f53,f54,f55,f56"


class EastmoneyA50KlineCollector(BaseKlineCollector):
    """东方财富富时中国 A50 期指（当月连续）日 K 采集器，写入 quote_kline_stock_daily。

    新浪 XIN9 日 K 已下线，东财 push2his 为唯一可用免费源；接口返回全历史，
    天然支持一次性回填与幂等重跑。期货无成交额字段，置 None。
    """

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        response = await run_in_thread(
            eastmoney_get,
            _KLINE_URL,
            params={
                "secid": _SECID,
                "klt": "101",
                "fqt": "1",
                "lmt": "6600",
                "end": "20500000",
                "iscca": "1",
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
                "fields2": _FIELDS2,
                "ut": "f057cbcbce2a86e2866ab8877db1d059",
                "forcect": "1",
            },
        )
        data = response.json().get("data") or {}
        raw: list[dict[str, Any]] = []
        for kline in data.get("klines") or []:
            parts = kline.split(",")
            if len(parts) < 6:
                continue
            raw.append(
                {
                    "stock_code": _STOCK_CODE,
                    "trade_date": parse_date(parts[0]),
                    "open": parts[1],
                    "close": parts[2],
                    "high": parts[3],
                    "low": parts[4],
                    "volume": parts[5],
                    "amount": None,
                }
            )
        return raw
