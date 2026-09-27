"""日线/周线技术指标纯函数（无 IO）：均线关系、大阳大阴、新低/地量/支撑。

为 ``index_technical_service`` 的文本装配提供指标族计算；趋势理论事实
（通道归属/拐点信号）在 ``trend_facts``，此处不重复。
"""

from typing import Any

from app.services.market.trend_facts import (
    EXTREME_WINDOW,
    MA_WINDOWS,
    SUPPORT_WINDOW,
)

_BIG_BODY_PCT = 2.0  # 大阴/大阳线实体幅度阈值（%）

Bar = dict[str, Any]


def ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def weekly_bars(bars: list[Bar]) -> list[Bar]:
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


def ma_relations(close: float, closes: list[float], prefix: str) -> str:
    parts = []
    for window in MA_WINDOWS:
        avg = ma(closes, window)
        if avg is None:
            parts.append(f"{prefix}MA{window} 数据不足")
            continue
        relation = "跌破" if close < avg else "站上"
        parts.append(f"{relation} {prefix}MA{window}（{avg:.2f}）")
    return "、".join(parts)


def format_daily(bars: list[Bar]) -> str:
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

    parts.append(ma_relations(close, closes, ""))

    if len(closes) > EXTREME_WINDOW:
        prior_low = min(closes[-EXTREME_WINDOW - 1 : -1])
        parts.append(
            f"创 {EXTREME_WINDOW} 日新低（前低 {prior_low:.2f}）"
            if close < prior_low
            else f"未创 {EXTREME_WINDOW} 日新低（前低 {prior_low:.2f}）"
        )

    volumes = [b["volume"] for b in bars if b["volume"] is not None]
    if len(volumes) > 5 and latest["volume"] is not None:
        avg5 = sum(volumes[-6:-1]) / 5
        if avg5 > 0:
            ratio = latest["volume"] / avg5
            label = "放量" if ratio >= 1.3 else "缩量" if ratio <= 0.7 else "量能平稳"
            parts.append(f"成交量为前 5 日均量的 {ratio:.2f} 倍（{label}）")
    if len(volumes) >= EXTREME_WINDOW and latest["volume"] is not None:
        is_floor = latest["volume"] <= min(volumes[-EXTREME_WINDOW:])
        parts.append(f"{EXTREME_WINDOW} 日地量：{'是' if is_floor else '否'}")

    lows = [b["low"] for b in bars[-SUPPORT_WINDOW:-5] if b["low"] is not None]
    if lows:
        parts.append(f"近 {SUPPORT_WINDOW} 日前低支撑位 {min(lows):.2f}")

    return "- 日线：" + "；".join(parts)


def format_weekly(bars: list[Bar]) -> str:
    weeks = weekly_bars(bars)
    latest = weeks[-1]
    closes = [w["close"] for w in weeks]
    parts = [ma_relations(latest["close"], closes, "周")]
    if len(weeks) >= 2:
        prev_vol = weeks[-2]["volume"]
        if prev_vol:
            ratio = (latest["volume"] or 0) / prev_vol
            parts.append(f"周量能环比上周 {ratio - 1:+.0%}")
    return "- 周线（当周未完结）：" + "；".join(parts)
