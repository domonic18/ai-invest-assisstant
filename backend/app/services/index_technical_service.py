"""指数技术分析输入构建（AI 大盘综述）。

为综述的五标的（沪指/创业板/科创50/沪深300ETF/富时A50）从本地
kline_daily 预计算日线/周线技术指标，并从 kline_minute 预计算沪指
分时量能结构，格式化为文本注入复盘 prompt。

设计原则：Python 预计算指标、LLM 只负责叙述——大模型从原始 OHLCV
推算均线/新低/地量容易出错，必须在输入侧算好。
"""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline import KlineDaily, KlineMinute
from app.repositories.kline_repository import fetch_daily_bars, fetch_minute_bars

_CN_TZ = ZoneInfo("Asia/Shanghai")

TECH_CODES: dict[str, str] = {
    "sh000001": "沪指",
    "sz399006": "创业板",
    "sh000688": "科创50",
    "sh510300": "沪深300ETF",
    "CN00Y": "富时A50",
}

_DAILY_LIMIT = 400  # 覆盖周线 MA60（约 300 个交易日）
_MA_WINDOWS = (10, 30, 60)
_BIG_BODY_PCT = 2.0  # 大阴/大阳线实体幅度阈值（%）
_EXTREME_WINDOW = 20  # 新低/地量判断窗口（交易日）
_SUPPORT_WINDOW = 60  # 前低支撑位参考窗口
_INTRADAY_CODE = "sh000001"  # 仅沪指有本地分钟线

Bar = dict[str, Any]


def _to_bars(rows: list[KlineDaily]) -> list[Bar]:
    """ORM 行转升序 dict（倒序查询结果反转），剔除收盘缺失的行。"""
    bars: list[Bar] = []
    for row in reversed(rows):
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


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _weekly_bars(bars: list[Bar]) -> list[Bar]:
    """日 K 聚合为 ISO 周 K（最后一周通常未完结）。"""
    weeks: dict[tuple[int, int], Bar] = {}
    for bar in bars:
        iso = bar["trade_date"].isocalendar()
        key = (iso[0], iso[1])
        if key not in weeks:
            weeks[key] = {**bar, "week": key}
            continue
        week = weeks[key]
        if bar["high"] is not None:
            week["high"] = max(week["high"] or bar["high"], bar["high"])
        if bar["low"] is not None:
            week["low"] = min(week["low"] or bar["low"], bar["low"])
        week["close"] = bar["close"]
        if bar["volume"] is not None:
            week["volume"] = (week["volume"] or 0) + bar["volume"]
    return list(weeks.values())


def _ma_relations(close: float, closes: list[float], prefix: str) -> str:
    parts = []
    for window in _MA_WINDOWS:
        ma = _ma(closes, window)
        if ma is None:
            parts.append(f"{prefix}MA{window} 数据不足")
            continue
        relation = "跌破" if close < ma else "站上"
        parts.append(f"{relation} {prefix}MA{window}（{ma:.2f}）")
    return "、".join(parts)


def _format_daily(bars: list[Bar]) -> str:
    latest = bars[-1]
    close = latest["close"]
    closes = [b["close"] for b in bars]

    parts: list[str] = []
    open_ = latest["open"]
    if open_:
        body_pct = (close - open_) / open_ * 100
        if body_pct <= -_BIG_BODY_PCT:
            parts.append(f"收大阴线（实体 {body_pct:+.2f}%）")
        elif body_pct >= _BIG_BODY_PCT:
            parts.append(f"收大阳线（实体 {body_pct:+.2f}%）")
        else:
            parts.append(f"K 线实体 {body_pct:+.2f}%")

    parts.append(_ma_relations(close, closes, ""))

    if len(closes) > _EXTREME_WINDOW:
        prior_low = min(closes[-_EXTREME_WINDOW - 1 : -1])
        parts.append(
            f"创 {_EXTREME_WINDOW} 日新低（前低 {prior_low:.2f}）"
            if close < prior_low
            else f"未创 {_EXTREME_WINDOW} 日新低（前低 {prior_low:.2f}）"
        )

    volumes = [b["volume"] for b in bars if b["volume"] is not None]
    if len(volumes) > 5 and latest["volume"] is not None:
        avg5 = sum(volumes[-6:-1]) / 5
        if avg5 > 0:
            ratio = latest["volume"] / avg5
            label = "放量" if ratio >= 1.3 else "缩量" if ratio <= 0.7 else "量能平稳"
            parts.append(f"成交量为前 5 日均量的 {ratio:.2f} 倍（{label}）")
    if len(volumes) >= _EXTREME_WINDOW and latest["volume"] is not None:
        is_floor = latest["volume"] <= min(volumes[-_EXTREME_WINDOW:])
        parts.append(f"{_EXTREME_WINDOW} 日地量：{'是' if is_floor else '否'}")

    lows = [b["low"] for b in bars[-_SUPPORT_WINDOW:-5] if b["low"] is not None]
    if lows:
        parts.append(f"近 {_SUPPORT_WINDOW} 日前低支撑位 {min(lows):.2f}")

    return "- 日线：" + "；".join(parts)


def _format_weekly(bars: list[Bar]) -> str:
    weeks = _weekly_bars(bars)
    latest = weeks[-1]
    closes = [w["close"] for w in weeks]
    parts = [_ma_relations(latest["close"], closes, "周")]
    if len(weeks) >= 2:
        prev_vol = weeks[-2]["volume"]
        if prev_vol:
            ratio = (latest["volume"] or 0) / prev_vol
            parts.append(f"周量能环比上周 {ratio - 1:+.0%}")
    return "- 周线（当周未完结）：" + "；".join(parts)


def _minute_amount(bars: list[KlineMinute]) -> float | None:
    amounts = [float(b.amount) for b in bars if b.amount is not None]
    return sum(amounts) if len(amounts) == len(bars) and bars else None


def _hhmm(bars: list[KlineMinute], index: int) -> str:
    trade_time: datetime = bars[index].trade_time
    return trade_time.astimezone(_CN_TZ).strftime("%H:%M")


def _format_intraday(
    today: list[KlineMinute], prev: list[KlineMinute]
) -> str | None:
    if len(today) < 60:
        return None

    parts: list[str] = []
    today_open = _minute_amount(today[:30])
    prev_open = _minute_amount(prev[:30]) if prev else None
    if today_open is not None:
        text = f"开盘 30 分钟成交 {today_open / 1e8:.0f} 亿元"
        if prev_open:
            text += f"（较前日同期 {today_open / prev_open - 1:+.0%}）"
        parts.append(text)

    total = _minute_amount(today)
    down_amount = sum(
        float(b.amount)
        for b in today
        if b.amount is not None and b.close is not None and b.open is not None
        and float(b.close) < float(b.open)
    )
    if total:
        parts.append(f"阴线分钟量能占比 {down_amount / total:.0%}（价跌量增则为恐慌盘特征）")
        tail = _minute_amount(today[-30:])
        if tail is not None:
            parts.append(f"尾盘 30 分钟量能占全天 {tail / total:.0%}")

    valid: list[KlineMinute] = []
    closes: list[float] = []
    for b in today:
        if b.close is None:
            continue
        valid.append(b)
        closes.append(float(b.close))
    if len(closes) >= 31:
        worst, worst_at = 0.0, 0
        for i in range(len(closes) - 30):
            drop = closes[i + 30] / closes[i] - 1
            if drop < worst:
                worst, worst_at = drop, i
        if worst <= -0.003:
            parts.append(
                f"最大跳水时段 {_hhmm(valid, worst_at)}-{_hhmm(valid, worst_at + 30)}"
                f"（{worst * 100:+.2f}%）"
            )

    return "- 分时：" + "；".join(parts) if parts else None


async def build_technical_context(session: AsyncSession, trade_date: date) -> str:
    """构建五标的日线/周线/分时技术分析文本（复盘 prompt 输入）。"""
    sections: list[str] = []
    for code, label in TECH_CODES.items():
        rows = await fetch_daily_bars(
            session, code, end_date=trade_date, limit=_DAILY_LIMIT
        )
        bars = _to_bars(rows)
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

        lines = [header, _format_daily(bars), _format_weekly(bars)]
        if code == _INTRADAY_CODE:
            today = await fetch_minute_bars(session, code, trade_date)
            prev_day = bars[-2]["trade_date"] if len(bars) >= 2 else None
            prev = (
                await fetch_minute_bars(session, code, prev_day)
                if prev_day is not None
                else []
            )
            intraday = _format_intraday(today, prev)
            if intraday:
                lines.append(intraday)
        sections.append("\n".join(lines))

    return "\n".join(sections)
