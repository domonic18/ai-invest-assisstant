"""趋势事实纯计算模块（温程趋势理论：量能不变，趋势不变，拐点确认必须量能配合）。

从 ``index_technical_service._trend_summary`` 提取的事实层：给定升序日 K bars，
产出结构化 ``TrendFacts``（通道归属 / 均线 / 量能 / 拐点 / 周线位置），供复盘
文本渲染、异动检测与归因证据共用；文本渲染 ``trend_facts_summary`` 与提取前
逐字节一致。

周线门控（48集 18:14：日线/周线 M60 以下即便涨停也无参与意义）：收盘在周线
MA60 之下时突破拐点不成立（turning_points 剔除 breakout）——日线的带量收复/
新高只是下降通道中的反弹，不构成参与级别的趋势启动；风险/支撑拐点不受限。
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

Bar = dict[str, Any]

MA_WINDOWS = (10, 30, 60)
EXTREME_WINDOW = 20  # 新低/新高/地量判断窗口（交易日）
SUPPORT_WINDOW = 60  # 前低支撑位参考窗口
WEEKLY_MA_WINDOW = 60  # 周线 MA60 窗口（周）；约需 60 周 ≈ 300 根日 K
CHANNEL_GLUE_PCT = 0.5  # 均线两两差小于该值（%）视为粘合，判阻尼运动
SUPPORT_NEAR_PCT = 1.5  # 收盘距 60 日前低支撑不超过该值（%）视为「支撑位附近」
VOL_SHRINK = 0.7  # 量 <= 0.7 倍 5 日均量视为缩量
VOL_SURGE = 1.3  # 量 >= 1.3 倍 5 日均量视为放量

# 通道归属取值（MA10/30/60 排列）
CHANNEL_UP = "上升通道"
CHANNEL_DOWN = "下降通道"
CHANNEL_DAMPED = "阻尼运动（震荡收敛）"
CHANNEL_CROSSED = "均线交错（方向未明）"
CHANNEL_INSUFFICIENT = "均线数据不足"

# 量能确认后的拐点类型（turning_points 元素）
TURNING_SUPPORT_TEST = "support_test"
TURNING_BREAKOUT = "breakout"
TURNING_RISK_BREAK = "risk_break"


@dataclass(frozen=True)
class TrendFacts:
    """单标的趋势事实（由升序日 K 计算的纯数据，无 I/O）。"""

    channel: str
    ma10: float | None
    ma30: float | None
    ma60: float | None
    close: float | None
    volume_ratio: float | None  # 当日量 / 5 日均量
    is_volume_floor: bool  # 20 日地量
    new_20d_high: bool
    new_20d_low: bool
    near_support: bool  # 收盘距 60 日前低支撑 <= SUPPORT_NEAR_PCT%
    support_price: float | None  # 60 日前低支撑位
    prev_close: float | None
    reclaimed_ma30: bool  # 前收 < MA30 < 今收（未含量能确认）
    broke_ma30: bool  # 今收 < MA30（未含量能确认）
    weekly_ma60: float | None = None  # 周线 MA60（不足 60 周为 None，次新股不门控）
    above_weekly_ma60: bool | None = None  # None=周线数据不足；False=周线 M60 之下
    turning_points: tuple[str, ...] = ()

    def has_turning(self, kind: str) -> bool:
        return kind in self.turning_points


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _to_date(raw: Any) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


def _weekly_closes(bars: list[Bar]) -> list[float]:
    """按 ISO 周聚合周收盘（升序 bars，每周最后一根；当周未走完用最新价近似）。

    个股/板块 bar 的日期键分别为 ``date``/``trade_date``，两者都接受；
    任一根缺失可解析日期即放弃聚合（返回空表），调用方按周线数据不足处理。
    """
    weekly: dict[tuple[int, int], float] = {}
    for bar in bars:
        d = _to_date(bar.get("date") or bar.get("trade_date"))
        close = bar.get("close")
        if d is None or close is None:
            return []
        weekly[d.isocalendar()[:2]] = float(close)
    return list(weekly.values())


def _vol_ratio(bars: list[Bar]) -> float | None:
    latest = bars[-1]
    volumes = [float(b["volume"]) for b in bars if b["volume"] is not None]
    if len(volumes) > 5 and latest["volume"] is not None:
        avg5 = sum(volumes[-6:-1]) / 5
        if avg5 > 0:
            return float(latest["volume"]) / avg5
    return None


def _empty_facts() -> TrendFacts:
    return TrendFacts(
        channel=CHANNEL_INSUFFICIENT,
        ma10=None,
        ma30=None,
        ma60=None,
        close=None,
        volume_ratio=None,
        is_volume_floor=False,
        new_20d_high=False,
        new_20d_low=False,
        near_support=False,
        support_price=None,
        prev_close=None,
        reclaimed_ma30=False,
        broke_ma30=False,
        weekly_ma60=None,
        above_weekly_ma60=None,
    )


def compute_trend_facts(bars: list[Bar]) -> TrendFacts:
    """从升序日 K bars 计算趋势事实。

    bars 为空时返回空事实（channel=均线数据不足，各拐点皆空），
    调用方据此跳过趋势维度。
    """
    if not bars:
        return _empty_facts()

    closes = [b["close"] for b in bars]
    latest = bars[-1]
    close = latest["close"]
    ma10 = _ma(closes, 10)
    ma30 = _ma(closes, 30)
    ma60 = _ma(closes, 60)

    channel = CHANNEL_INSUFFICIENT
    if ma10 is not None and ma30 is not None and ma60 is not None:
        mid = (ma10 + ma30 + ma60) / 3
        glue_pct = (max(ma10, ma30, ma60) - min(ma10, ma30, ma60)) / mid * 100
        if ma10 > ma30 > ma60:
            channel = CHANNEL_UP
        elif ma10 < ma30 < ma60:
            channel = CHANNEL_DOWN
        elif glue_pct < CHANNEL_GLUE_PCT:
            channel = CHANNEL_DAMPED
        else:
            channel = CHANNEL_CROSSED

    volumes = [float(b["volume"]) for b in bars if b["volume"] is not None]
    vol_ratio = _vol_ratio(bars)
    is_floor = (
        len(volumes) >= EXTREME_WINDOW
        and latest["volume"] is not None
        and latest["volume"] <= min(volumes[-EXTREME_WINDOW:])
    )
    shrunk = is_floor or (vol_ratio is not None and vol_ratio <= VOL_SHRINK)
    surged = vol_ratio is not None and vol_ratio >= VOL_SURGE

    new_20d_high = len(closes) > EXTREME_WINDOW and close > max(
        closes[-EXTREME_WINDOW - 1 : -1]
    )
    new_20d_low = len(closes) > EXTREME_WINDOW and close < min(
        closes[-EXTREME_WINDOW - 1 : -1]
    )

    lows = [b["low"] for b in bars[-SUPPORT_WINDOW:-5] if b["low"] is not None]
    support = min(lows) if lows else None
    near_support = bool(
        support
        and close is not None
        and abs(close - support) / support * 100 <= SUPPORT_NEAR_PCT
    )

    prev_close = closes[-2] if len(closes) >= 2 else None
    reclaimed_ma30 = bool(
        ma30 is not None and prev_close is not None and prev_close < ma30 < close
    )
    broke_ma30 = bool(ma30 is not None and close < ma30)

    # 周线位置（M60=主力建仓成本，周线 M60 为牛熊分界）：周收盘不足 60 周
    # （次新股）时 above 为 None，不参与门控。
    weekly_closes = _weekly_closes(bars)
    weekly_ma60 = _ma(weekly_closes, WEEKLY_MA_WINDOW)
    above_weekly: bool | None = None
    if close is not None and weekly_ma60 is not None:
        above_weekly = close > weekly_ma60

    # 拐点判定（量能确认，按概要出现顺序去重）：支撑=回踩 60 日支撑带+缩量；
    # 突破=带量收复 MA30 或带量创 20 日新高（未确认新高不成拐点，仅文本提示
    # 假突破；周线 M60 之下突破不成立，门控见模块注释）；风险=上升通道中放量
    # 跌破 MA30。
    turning: list[str] = []
    if (
        support is not None
        and channel in (CHANNEL_DOWN, CHANNEL_DAMPED)
        and shrunk
        and near_support
    ):
        turning.append(TURNING_SUPPORT_TEST)
    if surged and (reclaimed_ma30 or new_20d_high) and above_weekly is not False:
        turning.append(TURNING_BREAKOUT)
    if channel == CHANNEL_UP and broke_ma30 and surged:
        turning.append(TURNING_RISK_BREAK)

    return TrendFacts(
        channel=channel,
        ma10=ma10,
        ma30=ma30,
        ma60=ma60,
        close=close,
        volume_ratio=vol_ratio,
        is_volume_floor=is_floor,
        new_20d_high=new_20d_high,
        new_20d_low=new_20d_low,
        near_support=near_support,
        support_price=support,
        prev_close=prev_close,
        reclaimed_ma30=reclaimed_ma30,
        broke_ma30=broke_ma30,
        weekly_ma60=weekly_ma60,
        above_weekly_ma60=above_weekly,
        turning_points=tuple(turning),
    )


def trend_facts_summary(facts: TrendFacts) -> str:
    """渲染「- 趋势概要：…」文本（与提取前 ``_trend_summary`` 逐字节一致）。"""
    vol_ratio = facts.volume_ratio
    is_floor = facts.is_volume_floor
    shrunk = is_floor or (vol_ratio is not None and vol_ratio <= VOL_SHRINK)
    surged = vol_ratio is not None and vol_ratio >= VOL_SURGE
    vol_note = f"量为 5 日均量的 {vol_ratio:.2f} 倍" if vol_ratio is not None else ""

    signals: list[str] = []

    if facts.support_price is not None and facts.channel in (
        CHANNEL_DOWN,
        CHANNEL_DAMPED,
    ) and shrunk and facts.near_support:
        if is_floor or vol_ratio is None:
            vol_desc = "20 日地量" if is_floor else "量能明显收缩"
        else:
            vol_desc = f"量仅为 5 日均量的 {vol_ratio:.2f} 倍"
        signals.append(
            "支撑拐点（触底观察）：临近 60 日前低支撑且量能明显收缩"
            f"（{vol_desc}），符合「支撑+缩量」触底要件"
        )

    if facts.reclaimed_ma30 and surged:
        signals.append(f"突破拐点：带量收复 MA30（{vol_note}）")

    if facts.new_20d_high:
        vol_part = f"量能配合（{vol_note}）" if surged else "量能未确认，留意假突破"
        signals.append(
            f"突破拐点：创 {EXTREME_WINDOW} 日新高（平台突破，{vol_part}）"
        )

    if facts.channel == CHANNEL_UP and facts.broke_ma30 and surged:
        signals.append(
            f"风险拐点：上升通道中放量跌破 MA30（{vol_note}），上升动能衰竭观察"
        )

    parts = [facts.channel, *(signals or ["暂无拐点信号"])]
    return "- 趋势概要：" + "；".join(parts)
