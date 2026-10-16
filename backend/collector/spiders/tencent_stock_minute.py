"""腾讯财经个股分钟 K 线采集器（stock-minute 盘中主渠道）。

ifzq mkline m1 接口：无鉴权、无指纹要求（普通 requests 直连）、小批量
连发无流控（2026-10-13 盘中实测：8 symbol/轮 ≈1s，末根=当前分钟，秒级
延迟；9:30 首根含集合竞价成交）。返回最近 330 根（≈1.3 交易日），运行时
只保留目标交易日；volume 单位为手，×100 换算为股落库；amount 无，置
NULL（盘后新浪渠道以同主键 upsert 校正四价与成交量）。symbols 缺省时取
共享默认范围（见 stock_minute_base）。
"""

from datetime import date, datetime
from typing import Any, ClassVar

from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.http_client import plain_get
from collector.spiders.stock_minute_base import (
    CN_TZ,
    fetch_default_codes,
    to_cn_symbol,
    transform_minute_row,
)

_DEFAULT_BASE_URL = "https://ifzq.gtimg.cn"
_MKLINE_PATH = "/appstock/app/kline/mkline"
_BAR_COUNT = 330  # 覆盖当日 240 根 + 昨日尾段
_BAR_TIME_FORMAT = "%Y%m%d%H%M"
# mkline bar: [YYYYMMDDHHMM, open, close, high, low, volume(手), {}, 换手率]
_BAR_FIELD_MIN_LENGTH = 6
_LOT_SIZE = 100


def _fetch_mkline(symbol: str, base_url: str | None = None) -> list[list[Any]]:
    """拉取单 symbol 的 1 分钟 bar 序列（连接级瞬时错误由 plain_get 重试）。"""
    url = f"{(base_url or _DEFAULT_BASE_URL).rstrip('/')}{_MKLINE_PATH}"
    response = plain_get(url, params={"param": f"{symbol},m1,,{_BAR_COUNT}"})
    data = (response.json().get("data") or {}).get(symbol) or {}
    bars: list[list[Any]] = data.get("m1") or []
    return bars


class TencentStockMinuteCollector(PostgresCollector):
    """腾讯财经个股分钟线采集器，写入 quote_kline_stock_minute。"""

    table = "quote_kline_stock_minute"
    conflict_key = "stock_code, trade_time"
    # 首写的当分钟 bar 是进行中的快照，值不完整，须随后续抓取刷新；
    # update_skip_null 使腾讯的 amount=None 不会覆盖新浪盘后校正写入的成交额
    update_columns: ClassVar[list[str]] = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    ]
    update_skip_null = True
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_time"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_time", "close"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url") or _DEFAULT_BASE_URL

    async def collect(
        self,
        symbols: list[str] | None = None,
        trade_date: date | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        target = trade_date or datetime.now(CN_TZ).date()
        codes = symbols or await fetch_default_codes(target)
        if not codes:
            return []
        return await run_in_thread(self._collect_sync, codes, target)

    def _collect_sync(self, codes: list[str], target: date) -> list[dict[str, Any]]:
        raw: list[dict[str, Any]] = []
        for code in codes:
            symbol = to_cn_symbol(code)
            if symbol is None:
                continue
            try:
                bars = _fetch_mkline(symbol, self.base_url)
            except Exception:  # noqa: BLE001 - 单票失败不拖垮整批
                continue
            for bar in bars:
                if len(bar) < _BAR_FIELD_MIN_LENGTH:
                    continue
                trade_time = datetime.strptime(str(bar[0]), _BAR_TIME_FORMAT)
                if trade_time.date() != target:
                    continue
                raw.append(
                    {
                        "stock_code": code,
                        "trade_time": trade_time.replace(tzinfo=CN_TZ),
                        "open": bar[1],
                        "high": bar[3],
                        "low": bar[4],
                        "close": bar[2],
                        "volume": round(float(bar[5]) * _LOT_SIZE) if bar[5] else None,
                        "amount": None,
                    }
                )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return transform_minute_row(raw)
