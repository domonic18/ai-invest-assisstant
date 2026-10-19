"""基于 akshare 的新浪港股日 K 采集器（东财 hk-kline 的 fallback 渠道）。

akshare ``stock_hk_daily``（新浪源，adjust='qfq' 前复权）逐股拉取，写
quote_kline_stock_daily，冲突键与更新列与东财渠道一致，可无缝互备。
新浪源比东财少 amplitude/change_pct/turnover_rate：前两者由相邻收盘价
推算补齐；换手率无流通股本来源，置 None，``update_skip_null`` 保留
库中东财已写入的原值（新浪为备源，不做破坏性覆盖）。

东财 push2his 被 WAF 封禁时本渠道接管；缺省宇宙与东财相同 =
stock_basic 全部 market='hk' 股票。
"""

import asyncio
import contextlib
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.stock import StockBasic
from collector.core.async_helpers import run_in_thread
from collector.core.base import get_engine
from collector.core.parsing import parse_date, to_float
from collector.spiders.kline_base import BaseKlineCollector

logger = structlog.get_logger(__name__)


async def _fetch_hk_codes() -> list[str]:
    """缺省采集范围：stock_basic 全部港股代码去重升序。"""
    session_maker = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        rows = await session.execute(
            select(StockBasic.stock_code)
            .where(StockBasic.market == "hk")
            .distinct()
            .order_by(StockBasic.stock_code)
        )
        return [row[0] for row in rows.all()]


class SinaHkKlineCollector(BaseKlineCollector):
    """新浪港股日 K 采集器（前复权，东财渠道的 fallback）。"""

    update_skip_null = True

    # 全市场逐股拉取（2800+ 次/轮），新浪按频率反爬（超频返回异常页导致
    # akshare KeyError），逐股间小 pacing 降低触发概率
    _REQUEST_INTERVAL_SECONDS = 0.2

    async def collect(
        self,
        symbols: list[str] | None = None,
        lookback_days: int | None = 5,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or await _fetch_hk_codes()
        cutoff = _cutoff_date(lookback_days)
        raw: list[dict[str, Any]] = []
        failed = 0
        for symbol in symbols:
            code = str(symbol).strip().zfill(5)
            try:
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    df = await run_in_thread(ak.stock_hk_daily, symbol=code, adjust="qfq")
            except Exception:  # noqa: BLE001 — 单票失败不拖垮整批
                failed += 1
                continue
            if df is None or df.empty:
                continue
            raw.extend(_parse_rows(code, df, cutoff))
            await asyncio.sleep(self._REQUEST_INTERVAL_SECONDS)
        if failed and not raw:
            raise RuntimeError(f"港股日K新浪源全量失败：{failed}/{len(symbols)} 只抓取异常")
        if failed:
            logger.warning(
                "sina_hk_kline_partial_failures", failed=failed, total=len(symbols)
            )
        return raw


def _parse_rows(code: str, df: Any, cutoff: date) -> list[dict[str, Any]]:
    """df → kline 原始行；只保留 cutoff 起的行，派生列跨全序列计算。"""
    rows: list[dict[str, Any]] = []
    prev_close: float | None = None
    for record in df.to_dict("records"):
        trade_date = parse_date(record.get("date"))
        if trade_date is None:
            continue
        close = to_float(record.get("close"))
        high = to_float(record.get("high"))
        low = to_float(record.get("low"))
        change_pct = (
            _pct(close - prev_close, prev_close)
            if close is not None and prev_close is not None
            else None
        )
        amplitude = _pct(
            (high - low) if high is not None and low is not None else None,
            prev_close,
        )
        if trade_date >= cutoff:
            rows.append(
                {
                    "stock_code": code,
                    "trade_date": trade_date,
                    "open": to_float(record.get("open")),
                    "close": close,
                    "high": high,
                    "low": low,
                    "volume": record.get("volume"),
                    "amount": record.get("amount"),
                    "amplitude": amplitude,
                    "change_pct": change_pct,
                    "turnover_rate": None,
                }
            )
        prev_close = close if close is not None else prev_close
    return rows


def _pct(value: float | None, base: float | None) -> float | None:
    if value is None or base is None or base == 0:
        return None
    return round(value / base * 100, 4)


def _cutoff_date(lookback_days: int | None) -> date:
    """lookback 换算为截取起始日；None/非法值回退 5 天（与东财渠道一致）。"""
    try:
        days = max(int(lookback_days), 1)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        days = 5
    now = datetime.now(timezone.utc).date()
    return now - timedelta(days=days)
