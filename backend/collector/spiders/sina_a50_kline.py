"""新浪财经富时中国 A50 期指（CHA50CFD）日 K 采集器。"""

import json
import re
from typing import Any

import httpx

from collector.core.parsing import parse_date
from collector.spiders.kline_base import BaseKlineCollector

_KLINE_URL = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php"
    "/var%20_=/GlobalFuturesService.getGlobalFuturesDailyKline"
)
_SYMBOL = "CHA50CFD"  # 新加坡交易所富时中国 A50 期指连续
_STOCK_CODE = "CN00Y"
_JSONP_RE = re.compile(r"var _=\((.*)\)\s*;\s*$", re.S)


class SinaA50KlineCollector(BaseKlineCollector):
    """新浪财经全球期货日 K 采集器（富时中国 A50 当月连续，写入 CN00Y）。

    东财 push2his kline 路径被 WAF 路径级封死（TLS 指纹无关，
    curl_cffi Chrome 指纹同样被拒），改走新浪全球期货接口；返回全历史，
    天然支持一次性回填与幂等重跑。期货无成交额字段，置 None。
    """

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                _KLINE_URL,
                params={"symbol": _SYMBOL},
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            response.raise_for_status()

        match = _JSONP_RE.search(response.text)
        if match is None:
            raise ValueError("新浪全球期货日 K 响应不是预期 JSONP 格式")
        payload = json.loads(match.group(1))
        rows = payload if isinstance(payload, list) else payload.get("data") or []

        return [
            {
                "stock_code": _STOCK_CODE,
                "trade_date": parse_date(row.get("date")),
                "open": row.get("open"),
                "close": row.get("close"),
                "high": row.get("high"),
                "low": row.get("low"),
                "volume": row.get("volume"),
                "amount": None,
            }
            for row in rows
        ]
