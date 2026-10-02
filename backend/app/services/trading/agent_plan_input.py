"""每日计划 LLM 输入组装（批次 7 §10.2 输入清单的唯一组装点）。

输入 = 当日复盘解读（18:35 后就绪——缺失即 ``ReviewInputDataNotReadyError``
退避重试）+ 涨停归因 + 异动归因 + agent 账户本地持仓 + 人工移出清单 +
方法论基座（温程《趋势理论》KB 直读双层注入，见 ``agent_methodology``）+
agent 经验记忆（``agent_memory`` active 条目）+ 候选价格锚点（治幻觉价格：
区间/止损的锚点值由代码供给，模型只负责区间语义）。仅取数，不做 LLM 调用；
各采集函数可独立 mock 测试。
"""

import asyncio
from contextlib import nullcontext
from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trading import AgentStockSelection
from app.models.market_anomaly import StockAnomaly
from app.models.paper_trade import PaperTradeExecution, TradingAgent
from app.repositories.market.kline_repository import (
    fetch_daily_bars_multi,
    upsert_daily_bars,
)
from app.repositories.review import ai_analysis_repository
from app.services.review.market_review_generator import (
    SKILL_ID as MARKET_REVIEW_SKILL_ID,
)
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_methodology
from app.services.trading.agent_run_recorder import AgentRunRecorder
from app.services.trading.paper_trade_converters import SIDE_BUY, SIDE_SELL

logger = structlog.get_logger(__name__)

#: 异动归因注入 prompt 的条数上限（按 strength 降序）
_ANOMALY_TOP_N = 10
#: 人工移出清单回看窗口（天）——超过后允许重新候选
_MANUAL_REMOVED_WINDOW_DAYS = 14
#: agent 经验记忆注入条数上限
_MEMORY_TOP_N = 20
#: 锚点日 K 根数（末 5 根收盘算 MA5，再留一根昨收）
_ANCHOR_BAR_LIMIT = 6
#: 新浪日 K 单标的现拉超时（秒）——超时按缺失处理，不阻塞计划生成
_ANCHOR_FETCH_TIMEOUT_SECONDS = 30.0


async def _market_review_sections(
    session: AsyncSession, trade_date: date
) -> dict[str, Any]:
    """当日复盘解读全文（就绪预检：缺失即输入未就绪，18:35 任务生成）。"""
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=MARKET_REVIEW_SKILL_ID, trade_date=trade_date
    )
    if row is None or not row.structured_output:
        raise ReviewInputDataNotReadyError(
            f"{trade_date.isoformat()} 当日复盘解读尚未生成，每日计划输入未就绪"
        )
    return row.structured_output


async def _limit_up_attribution(
    session: AsyncSession, trade_date: date
) -> dict[str, Any] | None:
    from app.services.review import limit_up_ai_service

    content = await limit_up_ai_service.get_cached_attribution(session, trade_date)
    return None if content is None else content.model_dump()


async def _stock_anomalies(
    session: AsyncSession, trade_date: date
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(StockAnomaly)
                .where(StockAnomaly.trade_date == trade_date)
                .order_by(StockAnomaly.strength.desc())
                .limit(_ANOMALY_TOP_N)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "stock_code": r.stock_code,
            "stock_name": r.stock_name,
            "change_pct": float(r.change_pct) if r.change_pct is not None else None,
            "anomaly_types": r.anomaly_types,
            "attribution_category": r.attribution_category,
            "attribution_summary": r.attribution_summary,
        }
        for r in rows
    ]


async def _manual_removed_codes(
    session: AsyncSession, agent_key: str, trade_date: date
) -> list[str]:
    """近期人工移出清单（按 Agent 生效：prompt 声明禁止选入 + 服务层兜底过滤）。"""
    since = trade_date.toordinal() - _MANUAL_REMOVED_WINDOW_DAYS
    rows = await session.execute(
        select(AgentStockSelection.stock_code)
        .where(
            AgentStockSelection.agent_key == agent_key,
            AgentStockSelection.removed_reason == "manual",
            AgentStockSelection.trade_date >= date.fromordinal(since),
        )
        .distinct()
    )
    return [code for code in rows.scalars().all()]


def _anchors_from_bars(bars: list[Any]) -> dict[str, Any] | None:
    """升序日 K 序列 → 价格锚点（close/prev_close/ma5）；无收盘价返回 None。

    ma5 需满 5 根收盘，不足为 None（prompt 按可用锚点推导，缺项不许编）。
    """
    closes = [float(bar.close) for bar in bars if bar.close is not None]
    if not closes:
        return None
    return {
        "close": closes[-1],
        "prev_close": closes[-2] if len(closes) >= 2 else None,
        "ma5": round(sum(closes[-5:]) / len(closes[-5:]), 4)
        if len(closes) >= 5
        else None,
        "last_bar_date": bars[-1].trade_date.isoformat(),
    }


def _anchor_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """现拉日 K 行（升序 dict）→ 价格锚点，形状同 ``_anchors_from_bars``。"""
    closes = [
        float(row["close"]) for row in rows if row.get("close") is not None
    ]
    if not closes:
        return None
    return {
        "close": closes[-1],
        "prev_close": closes[-2] if len(closes) >= 2 else None,
        "ma5": round(sum(closes[-5:]) / len(closes[-5:]), 4)
        if len(closes) >= 5
        else None,
        "last_bar_date": rows[-1]["trade_date"].isoformat(),
    }


async def _fetch_and_store_sina_daily(
    session: AsyncSession, code: str
) -> list[dict[str, Any]]:
    """现拉新浪日 K 末 N 根并 upsert 落库（锚点兜底补数，顺手补采集缺口）。

    调用方捕获一切异常按缺失处理；单标的超时/源失败不阻塞计划生成。
    """
    import akshare as ak  # type: ignore[import-untyped]

    prefix = "sh" if code.startswith("6") else "sz"
    df = await asyncio.wait_for(
        asyncio.to_thread(ak.stock_zh_a_daily, symbol=f"{prefix}{code}"),
        timeout=_ANCHOR_FETCH_TIMEOUT_SECONDS,
    )
    if df is None or df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in df.tail(_ANCHOR_BAR_LIMIT).iterrows():
        trade_date = row.get("date")
        if isinstance(trade_date, datetime):
            trade_date = trade_date.date()
        if not isinstance(trade_date, date):
            continue
        rows.append(
            {
                "stock_code": code,
                "trade_date": trade_date,
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": int(row["volume"]) if row.get("volume") is not None else None,
                "amount": row.get("amount"),
                "amplitude": None,
                "change_pct": None,
                "turnover_rate": float(row["turnover"]) * 100
                if row.get("turnover") is not None
                else None,
            }
        )
    await upsert_daily_bars(session, rows)
    return rows


async def _price_anchors(
    session: AsyncSession, codes: list[str], trade_date: date
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """候选标的价格锚点（区间/止损的锚点值由代码供给，治幻觉价格根因）。

    库内日 K 优先；缺失标的现拉新浪日 K 并 upsert（候选多来自涨停池/异动池，
    不在 watchlist 采集宇宙内）。仍无锚点的标的随 missing 返回，由调用方
    从输入剔除——无锚点禁止出计划（fail-fast 数据契约）。
    """
    unique = sorted(set(codes))
    if not unique:
        return {}, []
    bars_by_code = await fetch_daily_bars_multi(
        session, unique, end_date=trade_date, limit=_ANCHOR_BAR_LIMIT
    )
    anchors = {
        code: anchor
        for code in unique
        if (bars := bars_by_code.get(code)) and (anchor := _anchors_from_bars(bars))
    }
    for code in [c for c in unique if c not in anchors]:
        try:
            rows = await _fetch_and_store_sina_daily(session, code)
        except Exception as exc:  # noqa: BLE001 —— 兜底源失败按缺失处理
            logger.warning(
                "plan_anchor_fetch_failed", stock_code=code, error=str(exc)
            )
            continue
        if anchor := _anchor_from_rows(rows):
            anchors[code] = anchor
    return anchors, [c for c in unique if c not in anchors]


def _candidate_codes(
    *,
    attribution: dict[str, Any] | None,
    anomalies: list[dict[str, Any]],
    positions: list[dict[str, Any]],
) -> list[str]:
    """需要价格锚点的候选全集：涨停归因分组 ∪ 异动清单 ∪ 当前持仓。"""
    codes = [str(a["stock_code"]) for a in anomalies]
    codes += [str(c) for c in (attribution or {}).get("stock_themes") or {}]
    for group in (attribution or {}).get("groups") or []:
        codes += [str(c) for c in group.get("stock_codes") or []]
    codes += [str(p["stock_code"]) for p in positions]
    return codes


async def _local_positions(session: AsyncSession, account_id: int) -> list[dict[str, Any]]:
    """agent 账户当前持仓（本地成交聚合，不依赖柜台）：净持有 > 0 的标的。"""
    rows = (
        (
            await session.execute(
                select(PaperTradeExecution)
                .where(PaperTradeExecution.paper_trade_account_id == account_id)
                .order_by(PaperTradeExecution.trade_date.asc())
            )
        )
        .scalars()
        .all()
    )
    agg: dict[str, dict[str, float]] = {}
    for row in rows:
        code = row.symbol.split(".")[-1]
        volume = float(row.volume or 0)
        price = float(row.price or 0)
        entry = agg.setdefault(code, {"volume": 0.0, "cost": 0.0})
        if row.side == SIDE_BUY:
            entry["volume"] += volume
            entry["cost"] += volume * price
        elif row.side == SIDE_SELL:
            entry["volume"] -= volume
    return [
        {
            "stock_code": code,
            "volume": int(item["volume"]),
            "avg_cost": round(item["cost"] / item["volume"], 4)
            if item["volume"] > 0
            else None,
        }
        for code, item in sorted(agg.items())
        if item["volume"] > 0
    ]


async def _active_memories(
    session: AsyncSession, agent_key: str
) -> list[dict[str, Any]]:
    """agent 经验记忆 active 条目（复盘沉淀 + 手动沉淀，停用条目不注入）。"""
    from sqlalchemy import text

    # SAVEPOINT 隔离：表缺失等失败只回滚到保存点，避免外层事务进入 aborted 态
    try:
        async with session.begin_nested():
            rows = await session.execute(
                text(
                    "SELECT title, body, mem_type FROM agent_memory "
                    "WHERE agent_key = :agent_key AND status = 'active' "
                    "ORDER BY updated_at DESC LIMIT :n"
                ),
                {"agent_key": agent_key, "n": _MEMORY_TOP_N},
            )
            items = [
                {"title": r.title, "body": r.body, "mem_type": r.mem_type}
                for r in rows.mappings().all()
            ]
    except (OperationalError, ProgrammingError):
        # 批次 9 建 agent_memory 前表不存在（asyncpg UndefinedTable → ProgrammingError）；
        # 记忆注入是可选增强，任何取数失败都降级为空集，不阻塞每日计划。
        return []
    return items


async def collect_plan_input(
    session: AsyncSession,
    agent: TradingAgent,
    account_id: int,
    trade_date: date,
    recorder: AgentRunRecorder | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """组装指定 Agent 的 LLM 输入，返回 (输入 dict, 人工移出代码清单)。

    传入 recorder 时按四步记录输入组装轨迹（D35 会话管理）：
    ``input.market_review``（复盘解读+涨停归因）→ ``input.kb_methodology``
    （方法论基座检索）→ ``input.context``（持仓/异动/记忆/人工移出）→
    ``input.price_anchors``（候选价格锚点，无锚点标的剔除出计划宇宙）。
    """
    review: dict[str, Any] | None = None
    attribution: dict[str, Any] | None = None
    async with (
        recorder.step(
            "input.market_review",
            "大盘复盘解读",
            payload_builder=lambda: {
                "sections": (review or {}).get("sections") or review,
                "limit_up_attribution": attribution,
            },
        )
        if recorder
        else nullcontext()
    ):
        review = await _market_review_sections(session, trade_date)
        attribution = await _limit_up_attribution(session, trade_date)

    anomalies = await _stock_anomalies(session, trade_date)
    manual_removed = await _manual_removed_codes(session, agent.agent_key, trade_date)
    query_text = agent_methodology.build_retrieval_query(
        review.get("sections") or review, attribution, anomalies
    )
    methodology: dict[str, Any] | None = None
    async with (
        recorder.step(
            "input.kb_methodology",
            "方法论基座检索（KB 直读）",
            payload_builder=lambda: {
                "source_id": agent.methodology_source_id,
                "query": query_text,
                "relevant_counts": _relevant_counts(methodology),
                "methodology": methodology,
            },
        )
        if recorder
        else nullcontext()
    ):
        methodology = await agent_methodology.build_methodology_input(
            session,
            source_id=agent.methodology_source_id,
            query_text=query_text,
        )

    positions: list[dict[str, Any]] = []
    memories: list[dict[str, Any]] = []
    async with (
        recorder.step(
            "input.context",
            "持仓/异动/记忆/人工移出合并",
            payload_builder=lambda: {
                "stock_anomalies": anomalies,
                "positions": positions,
                "memories": memories,
                "manual_removed_codes": manual_removed,
            },
        )
        if recorder
        else nullcontext()
    ):
        positions = await _local_positions(session, account_id)
        memories = await _active_memories(session, agent.agent_key)

    # 价格锚点（治幻觉价格）：无锚点标的从异动清单剔除（禁止出计划的宇宙）
    anchors: dict[str, dict[str, Any]] = {}
    unanchored: list[str] = []
    async with (
        recorder.step(
            "input.price_anchors",
            "候选价格锚点（库内日 K 优先，缺失现拉兜底）",
            payload_builder=lambda: {
                "codes": sorted(anchors),
                "unanchored_codes": unanchored,
                "anchors": anchors,
            },
        )
        if recorder
        else nullcontext()
    ):
        anchors, unanchored = await _price_anchors(
            session,
            _candidate_codes(
                attribution=attribution, anomalies=anomalies, positions=positions
            ),
            trade_date,
        )
    if unanchored:
        anomalies = [a for a in anomalies if a["stock_code"] not in set(unanchored)]

    return (
        {
            "trade_date": trade_date.isoformat(),
            "market_review": review.get("sections") or review,
            "limit_up_attribution": attribution,
            "stock_anomalies": anomalies,
            "price_anchors": anchors,
            "unanchored_codes": unanchored,
            "positions": positions,
            "manual_removed_codes": manual_removed,
            "methodology": methodology,
            "memories": memories,
        },
        manual_removed,
    )


def _relevant_counts(methodology: dict[str, Any] | None) -> dict[str, int]:
    """四类检索命中数（method/theorem/concept/case），relevant 为合流 list 按
    point_type 分组计数；无命中返回空表。"""
    if not methodology:
        return {}
    relevant = methodology.get("relevant") or []
    if not isinstance(relevant, list):
        return {}
    counts: dict[str, int] = {}
    for item in relevant:
        if isinstance(item, dict) and isinstance(item.get("point_type"), str):
            counts[item["point_type"]] = counts.get(item["point_type"], 0) + 1
    return counts
