"""市场行情与板块资金流向相关助手工具。"""

import time
from datetime import date
from typing import Any

from langchain_core.tools import tool

from app.agent.tools.page_event import page_event
from app.core.clock import now_cn
from app.core.database import AsyncSessionLocal
from app.services.market import (
    auction_service,
    index_quotation_service,
    sector_fund_flow_service,
    trade_calendar_service,
)
from app.services.market import (
    market_stats_service as market_stats_svc,
)

SECTOR_MAX_DAYS = 60
SECTOR_TOP_N = 10
AUCTION_MAX_DAYS = 30

# 复盘生成耗时锚点：助手对话路径没有外层计时器（定时路径由 run_skill 计时），
# 以首次 SKILL 数据工具调用为生成起点，persist_market_review 落库时消耗。
# 超过 30 分钟的锚点视为与本次生成无关（如日常闲聊触发的取数），重新计时。
_REVIEW_GEN_MAX_S = 1800.0
_review_gen_start: float | None = None


def _note_review_start() -> None:
    global _review_gen_start
    now = time.monotonic()
    if _review_gen_start is None or (now - _review_gen_start) > _REVIEW_GEN_MAX_S:
        _review_gen_start = now


def _consume_review_latency() -> int:
    global _review_gen_start
    if _review_gen_start is None:
        return 0
    elapsed_ms = int((time.monotonic() - _review_gen_start) * 1000)
    _review_gen_start = None
    return elapsed_ms if elapsed_ms <= _REVIEW_GEN_MAX_S * 1000 else 0


def _parse_trade_date(value: str | None) -> tuple[date | None, str | None]:
    """解析可选 ISO 日期参数；返回 (日期, None) 或 (None, 错误提示)。"""
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "trade_date 须为 YYYY-MM-DD 格式"


def _trim_sector_flow(response: Any, top_n: int) -> dict[str, Any]:
    """板块资金流响应裁剪：只保留净流入绝对值 Top N 板块的区间累计与最新值。"""
    dates = [d.isoformat() for d in response.dates]
    rows: list[dict[str, Any]] = []
    for sector in response.sectors:
        values = [v for v in sector.values if v is not None]
        period_net = round(sum(sector.values[i] or 0.0 for i in range(len(dates))), 2)
        rows.append(
            {
                "code": sector.code,
                "name": sector.name,
                "period_net_inflow_yi": period_net,
                "latest_yi": values[-1] if values else None,
            }
        )
    rows.sort(key=lambda r: abs(r["period_net_inflow_yi"]), reverse=True)
    return {
        "dates": [dates[0], dates[-1]] if dates else [],
        "unit": "亿元（主力净流入）",
        "sectors": rows[:top_n],
    }


@tool
async def get_sector_fund_flow(
    sector_type: str = "industry", days: int = 20, top: int = 10
) -> dict[str, Any]:
    """查询板块主力资金净流入排行（区间累计与最新一日，单位亿元）。当前仅支持行业板块。

    Args:
        sector_type: 板块类型，当前仅 "industry"。
        days: 统计区间交易日数，1-60，默认 20。
        top: 返回板块数，默认 10。
    """
    days = max(1, min(days, SECTOR_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        response = await sector_fund_flow_service.get_sector_flow_trend(
            session, sector_type, days
        )
    return _trim_sector_flow(response, top)


@tool
async def get_market_overview(trade_date: str | None = None) -> dict[str, Any]:
    """获取大盘概览：四大指数行情 + 全市场涨跌家数、成交额（含环比）、涨停/跌停家数与情绪温度。

    Args:
        trade_date: 可选历史交易日，ISO 格式如 "2026-08-21"；缺省为最新交易日。
    """
    _note_review_start()
    resolved: date | None = None
    if trade_date:
        try:
            resolved = date.fromisoformat(trade_date)
        except ValueError:
            return {"error": "trade_date 须为 YYYY-MM-DD 格式"}

    async with AsyncSessionLocal() as session:
        stats = await market_stats_svc.get_market_stats(session, resolved)
        quotes = await index_quotation_service.get_index_quotes(session, resolved)

    return {
        "market_stats": stats.model_dump(mode="json"),
        "index_quotes": [
            q.model_dump(mode="json", exclude={"trend"}) for q in quotes
        ],
    }


@tool
async def get_auction_summary(days: int = 5) -> dict[str, Any]:
    """查询指数集合竞价成交额趋势（单位亿元），反映开盘前资金活跃度。

    Args:
        days: 最近交易日数，1-30，默认 5。
    """
    days = max(1, min(days, AUCTION_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        response = await auction_service.get_index_auction_trend(session, days=days)

    dates = [d.isoformat() for d in response.dates]
    series = [
        {
            "code": s.code,
            "name": s.name,
            "values_yi": s.values,
            "latest_yi": next((v for v in reversed(s.values) if v is not None), None),
        }
        for s in response.series
    ]
    return {"dates": dates, "series": series}


@tool
async def get_trade_calendar() -> dict[str, Any]:
    """获取当前北京时间与 A 股交易日信息：今天日期、今天是否交易日、最近（含今日）交易日。

    涉及「今天/最近交易日/最新数据」等时间语义时先调用本工具确认，
    再与查到的数据日期对照；数据日期早于最近交易日时须向用户如实披露滞后。
    """
    now = now_cn()
    async with AsyncSessionLocal() as session:
        latest = await trade_calendar_service.resolve_latest_trade_date(session)
        today_is_trading = await trade_calendar_service.is_trading_day(
            session, now.date()
        )
    return {
        "now": now.isoformat(),
        "today": now.date().isoformat(),
        "today_is_trading_day": today_is_trading,
        "latest_trading_day": latest.isoformat(),
    }


@tool
async def get_sector_overview(trade_date: str | None = None) -> dict[str, Any]:
    """查询行业板块概览：涨跌幅热力图、主力净流入/净流出 TOP5（含领涨股）、领涨板块（涨跌幅、涨停家数、代表个股）。

    Args:
        trade_date: 可选历史交易日，ISO 格式如 "2026-08-21"；缺省为最近交易日。
    """
    from app.services.market import sector_service

    _note_review_start()
    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}

    async with AsyncSessionLocal() as session:
        response = await sector_service.get_sector_overview(session, resolved)

    return {
        "trade_date": response.trade_date.isoformat(),
        "heatmap": [item.model_dump(mode="json") for item in response.heatmap],
        "top_inflow": [item.model_dump(mode="json") for item in response.top_inflow],
        "top_outflow": [item.model_dump(mode="json") for item in response.top_outflow],
        "leading": [item.model_dump(mode="json") for item in response.leading],
    }


@tool
async def get_limit_up_ladder(trade_date: str | None = None) -> dict[str, Any]:
    """查询涨停池与连板天梯：涨停总数、首板/连板家数、最高连板数与 ≥2 板连板梯队（含个股与所属行业）。

    Args:
        trade_date: 可选历史交易日，ISO 格式如 "2026-08-21"；缺省为最近交易日（盘中未收盘时当日涨停池尚未写入，返回空）。
    """
    from app.services.market import limit_pool_service

    _note_review_start()
    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}

    async with AsyncSessionLocal() as session:
        response = await limit_pool_service.get_limit_up(session, resolved)

    return {
        "trade_date": response.trade_date.isoformat(),
        "total": response.total,
        "first_board": response.first_board,
        "continuous": response.continuous,
        "max_boards": response.max_boards,
        "ladder": [
            {
                "stock_code": item.stock_code,
                "stock_name": item.stock_name,
                "consecutive_boards": item.consecutive_boards,
                "industry": item.industry,
            }
            for item in response.ladder
        ],
    }


@tool
async def get_index_technical(trade_date: str | None = None) -> dict[str, Any]:
    """获取五大标的（沪指/创业板/科创50/沪深300ETF/富时A50）的预计算技术分析文本：日 K/周 K 形态、均线、新低/地量/放量判断。

    Args:
        trade_date: 可选历史交易日，ISO 格式如 "2026-08-21"；缺省为最新交易日。
    """
    from app.services.market import index_technical_service

    _note_review_start()
    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}

    async with AsyncSessionLocal() as session:
        resolved_date = (
            resolved
            if resolved is not None
            else await trade_calendar_service.resolve_latest_trade_date(session)
        )
        context = await index_technical_service.build_technical_context(
            session, resolved_date
        )
    return {"trade_date": resolved_date.isoformat(), "technical_context": context}


@tool
async def persist_market_review(
    trade_date: str, sections: dict[str, str]
) -> dict[str, Any]:
    """持久化大盘每日复盘生成结果到数据库，复盘页卡片会自动刷新展示。

    Args:
        trade_date: 交易日（YYYY-MM-DD）。
        sections: 复盘分区内容字典，键必须与 market-daily-review SKILL 输出 Schema
            完全一致（overview / technical_analysis / capital_analysis /
            emotion_analysis / risk_advice），值为对应分区的 Markdown 正文。
    """
    from app.services.admin.llm_config_service import resolve_default_llm
    from app.services.review import market_review_generator

    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}
    assert resolved is not None

    async with AsyncSessionLocal() as session:
        cfg = await resolve_default_llm(session)
        response = await market_review_generator.persist_market_review_result(
            session,
            trade_date=resolved,
            contents=sections,
            model=f"{cfg.provider}/{cfg.model_name}",
            latency_ms=_consume_review_latency(),
        )
        return {
            "trade_date": response.trade_date.isoformat(),
            "section_titles": [section.title for section in response.sections],
            "__event__": page_event(
                "market_daily_review.complete",
                trade_date=response.trade_date.isoformat(),
            ),
        }


@tool
async def collect_market_data(
    trade_date: str, symbols: list[str] | None = None
) -> dict[str, Any]:
    """补采指定交易日的行情数据：查询工具发现数据缺失/滞后时用于数据自愈。

    覆盖涨停池、炸板池、跌停池、市场成交额、板块资金流与指数 K 线；
    传入 symbols 时补采对应个股日 K。任务异步执行：涨停池/成交额约 1 分钟入库，
    板块资金流约 10 分钟；派发后须等待数据入库再重新查询验证。
    涨跌家数为盘中快照，无法补采。

    Args:
        trade_date: 交易日，ISO 格式如 "2026-09-04"。
        symbols: 可选个股代码列表（如 ["000001", "600519"]），补采其日 K 数据。
    """
    from app.services.collector import market_dispatch_service

    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}
    assert resolved is not None

    try:
        async with AsyncSessionLocal() as session:
            results = await market_dispatch_service.collect_market_data(
                session, resolved, symbols
            )
    except market_dispatch_service.NonTradingDayError as exc:
        return {"error": str(exc)}

    return {
        "trade_date": resolved.isoformat(),
        "dispatched": [r.task for r in results],
        "note": (
            "补采任务已提交，涨停池/成交额约 1 分钟入库，板块资金流约 10 分钟；"
            "请稍后重新调用查询工具验证数据，仍缺失时如实告知用户。"
        ),
    }
