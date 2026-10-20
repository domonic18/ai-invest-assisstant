"""长线全市场周度选股器（温程趋势理论四大标准的技术支柱）。

KB 知识点 2265 选股四大标准：周线 M60 拐点 + 日线四线开花 + 基本面加持 + 估值低。
本模块只做技术面硬门槛与打分（周线 M60 位置 + 四线开花 + 缩量新高 + 通道上升 +
均线发散度）；基本面与产业图谱由调用方（agent_plan_input 三支柱注入）逐只补充。

周线门控（趋势理论 48 集：周线 M60 之下无参与意义）：above_weekly_ma60=False
直接剔除；次新股周线数据不足（None）保留但降权，不误杀。
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline import KlineDaily
from app.models.stock import StockBasic
from app.repositories.market.kline_repository import fetch_daily_bars_multi
from app.services.market.trend_facts import (
    CHANNEL_UP,
    VOL_SHRINK,
    Bar,
    TrendFacts,
    compute_trend_facts,
)

_UNIVERSE_CHUNK = 500  # 分批取数，chunk 内即算即释放（全市场约 5000+ 股）
_BAR_LIMIT = 320  # 覆盖周线 MA60（约 300 个交易日）+ 四线 MA250
_STALE_DAYS = 10  # 最新日 K 距 trade_date 超过该天数视为停牌/退市脏数据，剔除
_YOUNG_PENALTY = 3.0  # 次新股（周线不足 60 周）降权分
_BLOSSOM_SCORE = 2.0  # 四线开花
_SHRINK_HIGH_SCORE = 2.0  # 缩量新高
_CHANNEL_UP_SCORE = 1.0  # 上升通道
_DIVERGENCE_MAX = 2.0  # MA 间距发散度满分（min_gap_pct 每 1% 计 1 分，封顶）


def _to_bars(rows: list[KlineDaily]) -> list[Bar]:
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


async def _stock_universe(session: AsyncSession) -> dict[str, str]:
    """全市场 A 股（沪/深/北，含创业板/科创板），剔除 ST/退市整理股。"""
    stmt = select(StockBasic.stock_code, StockBasic.stock_name).where(
        StockBasic.market.in_(("sh", "sz", "bj"))
    )
    rows = (await session.execute(stmt)).all()
    return {
        code: name
        for code, name in rows
        if "ST" not in (name or "").upper() and "退" not in (name or "")
    }


def _score_facts(facts: TrendFacts, has_weekly: bool) -> float:
    """技术面打分：调用方已保证 above_weekly_ma60 != False。"""
    score = 0.0
    if facts.four_line_blossom is not None and facts.four_line_blossom.bloomed:
        score += _BLOSSOM_SCORE
    shrunk = facts.is_volume_floor or (
        facts.volume_ratio is not None and facts.volume_ratio <= VOL_SHRINK
    )
    if facts.new_20d_high and shrunk:
        score += _SHRINK_HIGH_SCORE
    if facts.channel == CHANNEL_UP:
        score += _CHANNEL_UP_SCORE
    blossom = facts.four_line_blossom
    if blossom is not None and blossom.min_gap_pct is not None:
        score += min(_DIVERGENCE_MAX, max(0.0, blossom.min_gap_pct))
    if not has_weekly:
        score -= _YOUNG_PENALTY
    return score


async def screen_long_term_candidates(
    session: AsyncSession, trade_date: date, top_n: int = 30
) -> list[dict]:
    """全市场周度筛选：周线 M60 硬门槛 + 技术面打分，返回 Top-N 紧凑 dict 列表。"""
    universe = await _stock_universe(session)
    candidates: list[dict] = []
    codes = list(universe)
    for i in range(0, len(codes), _UNIVERSE_CHUNK):
        bars_by_code = await fetch_daily_bars_multi(
            session, codes[i : i + _UNIVERSE_CHUNK], end_date=trade_date, limit=_BAR_LIMIT
        )
        for code, rows in bars_by_code.items():
            bars = _to_bars(rows)
            if not bars or (trade_date - bars[-1]["trade_date"]).days > _STALE_DAYS:
                continue
            facts = compute_trend_facts(bars)
            if facts.above_weekly_ma60 is False:
                continue
            close = facts.close
            if close is None:
                continue
            has_weekly = facts.above_weekly_ma60 is not None
            candidates.append(
                {
                    "stock_code": code,
                    "stock_name": universe[code],
                    "score": round(_score_facts(facts, has_weekly), 2),
                    "close": round(float(close), 2),
                    "weekly_ma60": (
                        round(facts.weekly_ma60, 2) if facts.weekly_ma60 is not None else None
                    ),
                    "above_weekly_ma60": facts.above_weekly_ma60,
                    "four_line_blossom": bool(
                        facts.four_line_blossom is not None and facts.four_line_blossom.bloomed
                    ),
                    "new_20d_high": facts.new_20d_high,
                    "vol_shrink": bool(
                        facts.is_volume_floor
                        or (facts.volume_ratio is not None and facts.volume_ratio <= VOL_SHRINK)
                    ),
                    "channel": facts.channel,
                }
            )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:top_n]
