"""指数与个股技术分析输入构建（AI 大盘综述 / 个股每日分析）。

为综述的五标的（沪指/创业板/科创50/沪深300ETF/富时A50）从本地
quote_kline_stock_daily 预计算日线/周线技术指标，并从 quote_kline_stock_minute 预计算沪指
分时量能结构，格式化为文本注入复盘 prompt；个股版见 ``build_stock_technical_context``。

设计原则：Python 预计算指标、LLM 只负责叙述——大模型从原始 OHLCV
推算均线/新低/地量容易出错，必须在输入侧算好。指标族纯函数在
``indicators_daily``（日/周线）与 ``indicators_intraday``（分时），
趋势理论事实在 ``trend_facts``，本模块只做取数与文本装配。
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline import KlineDaily
from app.repositories.market.kline_repository import (
    fetch_daily_bars_multi,
    fetch_minute_bars,
)
from app.services.market.indicators_daily import Bar, format_daily, format_weekly
from app.services.market.indicators_intraday import format_intraday
from app.services.market.trend_facts import (
    compute_trend_facts,
    trend_facts_summary,
)

TECH_CODES: dict[str, str] = {
    "sh000001": "沪指",
    "sz399006": "创业板",
    "sh000688": "科创50",
    "sh510300": "沪深300ETF",
    "CN00Y": "富时A50",
}

_DAILY_LIMIT = 400  # 覆盖周线 MA60（约 300 个交易日）
_INTRADAY_CODE = "sh000001"  # 仅沪指有本地分钟线


def _to_bars(rows: list[KlineDaily]) -> list[Bar]:
    """ORM 行转升序 dict（fetch_daily_bars_multi 返回组内升序），剔除收盘缺失的行。"""
    bars: list[Bar] = []
    for row in rows:
        if row.close is None:
            continue
        bars.append(
            {
                "trade_date": row.trade_date,
                "open": float(row.open) if row.open is not None else None,
                "high": float(row.high) if row.high is not None else None,
                "low": float(row.low) if row.low is not None else None,
                "close": float(row.close),
                "volume": int(row.volume) if row.volume is not None else None,
            }
        )
    return bars


def _trend_summary(bars: list[Bar]) -> str:
    """温程趋势理论概要：通道归属（MA10/30/60 排列）+ 拐点信号（须量能配合）。

    事实计算与文本渲染见 ``app.services.market.trend_facts``（结构化事实供
    异动检测/归因共用），此处仅保留薄壳。
    """
    return trend_facts_summary(compute_trend_facts(bars))


async def build_stock_technical_context(
    session: AsyncSession, stock_code: str, trade_date: date
) -> str:
    """构建单只个股的日线/周线技术分析文本（个股复盘 prompt 输入）。

    与五标的大盘版同构：通道归属（MA10/30/60）、三类拐点信号（趋势概要行）、
    新低/地量/放量与 60 日前低支撑；个股无本地分钟线，不含分时段。
    """
    bars_by_code = await fetch_daily_bars_multi(
        session, [stock_code], end_date=trade_date, limit=_DAILY_LIMIT
    )
    bars = _to_bars(bars_by_code.get(stock_code, []))
    if not bars:
        return f"■ {stock_code}：本地无日 K 数据"

    latest = bars[-1]
    prev_close = bars[-2]["close"] if len(bars) >= 2 else None
    change_pct = (latest["close"] / prev_close - 1) * 100 if prev_close else None
    header = f"■ {stock_code} 收 {latest['close']:.2f}"
    if change_pct is not None:
        header += f"（{change_pct:+.2f}%）"
    if latest["trade_date"] != trade_date:
        header += f"［数据为最近交易日 {latest['trade_date'].isoformat()}］"

    return "\n".join(
        [header, _trend_summary(bars), format_daily(bars), format_weekly(bars)]
    )


async def build_technical_context(session: AsyncSession, trade_date: date) -> str:
    """构建五标的日线/周线/分时技术分析文本（复盘 prompt 输入）。"""
    bars_by_code = await fetch_daily_bars_multi(
        session, list(TECH_CODES), end_date=trade_date, limit=_DAILY_LIMIT
    )

    sections: list[str] = []
    for code, label in TECH_CODES.items():
        bars = _to_bars(bars_by_code.get(code, []))
        if not bars:
            sections.append(f"■ {label}（{code}）：本地无日 K 数据")
            continue

        latest = bars[-1]
        prev_close = bars[-2]["close"] if len(bars) >= 2 else None
        change_pct = (
            (latest["close"] / prev_close - 1) * 100 if prev_close else None
        )
        header = f"■ {label}（{code}）收 {latest['close']:.2f}"
        if change_pct is not None:
            header += f"（{change_pct:+.2f}%）"
        if latest["trade_date"] != trade_date:
            header += f"［数据为最近交易日 {latest['trade_date'].isoformat()}］"

        lines = [header, _trend_summary(bars), format_daily(bars), format_weekly(bars)]
        if code == _INTRADAY_CODE:
            today = await fetch_minute_bars(session, code, trade_date)
            prev_day = bars[-2]["trade_date"] if len(bars) >= 2 else None
            prev = (
                await fetch_minute_bars(session, code, prev_day)
                if prev_day is not None
                else []
            )
            intraday = format_intraday(today, prev)
            if intraday:
                lines.append(intraday)
        sections.append("\n".join(lines))

    return "\n".join(sections)
