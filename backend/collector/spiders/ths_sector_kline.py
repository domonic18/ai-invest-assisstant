"""THS（同花顺）板块指数日 K 采集器：板块详情页真实 OHLC K 线。

行业（90）/概念（375）指数日 K，OHLC + 成交量 + 成交额。检测/资金流保持
东财体系，经板块名桥接（行业 90/90 同名、概念 ~96% 同名）；THS 代码
881xxx 写入 quote_kline_sector_daily。akshare 按板块名称拉取，
hexin-v 签名由 akshare 内置处理；10jqka 反爬较严，板块间显式限速。
"""

import time
from datetime import date, timedelta
from typing import Any, ClassVar

import structlog

from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.calendar import latest_trading_day
from collector.core.parsing import parse_date, to_float, to_int

logger = structlog.get_logger(__name__)

# 板块间限速（秒）：465 个板块 × 0.3s ≈ 2.5 分钟纯等待，避开 10jqka 频控
_BOARD_INTERVAL_SECONDS = 0.3

_KLINE_CN_COLS = ("日期", "开盘价", "最高价", "最低价", "收盘价", "成交量", "成交额")


def _fetch_board_list(sector_type: str) -> list[dict[str, str]]:
    """拉取同花顺板块清单（name + 881xxx code）。"""
    import akshare as ak  # type: ignore[import-untyped]

    fetcher = (
        ak.stock_board_industry_name_ths
        if sector_type == "industry"
        else ak.stock_board_concept_name_ths
    )
    df = fetcher()
    if df is None or df.empty:
        return []
    return [
        {"name": str(row["name"]), "code": str(row["code"])}
        for row in df.to_dict(orient="records")
    ]


def _fetch_board_kline(
    sector_type: str, name: str, start: date, end: date
) -> list[dict[str, Any]]:
    """拉取单板块区间日 K 并转为 quote_kline_sector_daily 行。"""
    import akshare as ak  # type: ignore[import-untyped]

    fetcher = (
        ak.stock_board_industry_index_ths
        if sector_type == "industry"
        else ak.stock_board_concept_index_ths
    )
    df = fetcher(
        symbol=name,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    if df is None or df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for record in df.to_dict(orient="records"):
        trade_date = parse_date(record.get("日期"))
        close = to_float(record.get("收盘价"))
        if trade_date is None or close is None:
            continue
        rows.append(
            {
                "sector_code": None,  # 由调用方回填（df 不带代码列）
                "trade_date": trade_date,
                "sector_type": sector_type,
                "sector_name": name,
                "open": to_float(record.get("开盘价")),
                "high": to_float(record.get("最高价")),
                "low": to_float(record.get("最低价")),
                "close": close,
                "volume": to_int(record.get("成交量")),
                "amount": to_float(record.get("成交额")),
                "source": "ths",
            }
        )
    return rows


class ThsSectorKlineCollector(PostgresCollector):
    """同花顺板块指数日 K 采集器，写入 quote_kline_sector_daily。"""

    table = "quote_kline_sector_daily"
    conflict_key = "sector_code, trade_date"
    update_columns: ClassVar[list[str]] = [
        "sector_name",
        "sector_type",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "source",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["sector_code", "trade_date"]
    required_fields: ClassVar[list[str]] = [
        "sector_code",
        "sector_name",
        "sector_type",
        "trade_date",
        "close",
    ]

    async def collect(self, lookback_days: int = 10, **kwargs: Any) -> list[dict[str, Any]]:
        end = latest_trading_day()
        start = end - timedelta(days=max(int(lookback_days), 1))
        rows: list[dict[str, Any]] = await run_in_thread(self._collect_sync, start, end)
        return rows

    def _collect_sync(self, start: date, end: date) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for sector_type in ("industry", "concept"):
            boards = _fetch_board_list(sector_type)
            logger.info(
                "ths_sector_kline_board_list",
                sector_type=sector_type,
                count=len(boards),
            )
            if not boards:
                continue
            ok = 0
            for board in boards:
                try:
                    board_rows = _fetch_board_kline(
                        sector_type, board["name"], start, end
                    )
                except Exception as exc:  # noqa: BLE001 — 单板块失败不废弃整批
                    logger.warning(
                        "ths_sector_kline_board_failed",
                        sector_type=sector_type,
                        sector_name=board["name"],
                        error=repr(exc),
                    )
                    time.sleep(_BOARD_INTERVAL_SECONDS)
                    continue
                ok += 1
                rows.extend(
                    {**row, "sector_code": board["code"]} for row in board_rows
                )
                time.sleep(_BOARD_INTERVAL_SECONDS)
            if ok == 0:
                # 全部板块失败视为渠道不可用，向上抛错交由任务 FAILED 可见
                raise RuntimeError(
                    f"同花顺板块指数日 K 采集全部失败（{sector_type}，{len(boards)} 个板块）"
                )
            logger.info(
                "ths_sector_kline_fetched",
                sector_type=sector_type,
                boards=len(boards),
                succeeded=ok,
                rows=len(rows),
            )
        return rows
