"""分时（分钟 K）量能结构纯函数（无 IO）：开盘量、阴线占比、尾盘占比、最大跳水时段。

仅沪指有本地分钟线；为 ``index_technical_service`` 的文本装配提供分时指标族。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.kline import KlineMinute

_CN_TZ = ZoneInfo("Asia/Shanghai")


def minute_amount(bars: list[KlineMinute]) -> float | None:
    amounts = [float(b.amount) for b in bars if b.amount is not None]
    return sum(amounts) if len(amounts) == len(bars) and bars else None


def hhmm(bars: list[KlineMinute], index: int) -> str:
    trade_time: datetime = bars[index].trade_time
    return trade_time.astimezone(_CN_TZ).strftime("%H:%M")


def format_intraday(
    today: list[KlineMinute], prev: list[KlineMinute]
) -> str | None:
    if len(today) < 60:
        return None

    parts: list[str] = []
    today_open = minute_amount(today[:30])
    prev_open = minute_amount(prev[:30]) if prev else None
    if today_open is not None:
        text = f"开盘 30 分钟成交 {today_open / 1e8:.0f} 亿元"
        if prev_open:
            text += f"（较前日同期 {today_open / prev_open - 1:+.0%}）"
        parts.append(text)

    total = minute_amount(today)
    down_amount = sum(
        float(b.amount)
        for b in today
        if b.amount is not None and b.close is not None and b.open is not None
        and float(b.close) < float(b.open)
    )
    if total:
        parts.append(f"阴线分钟量能占比 {down_amount / total:.0%}（价跌量增则为恐慌盘特征）")
        tail = minute_amount(today[-30:])
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
                f"最大跳水时段 {hhmm(valid, worst_at)}-{hhmm(valid, worst_at + 30)}"
                f"（{worst * 100:+.2f}%）"
            )

    return "- 分时：" + "；".join(parts) if parts else None
