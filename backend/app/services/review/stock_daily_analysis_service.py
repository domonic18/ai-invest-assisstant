"""个股每日 AI 分析服务：数据就绪检查、锁、缓存与持久化。

LLM 生成委托 ``app.agent.skills.stock_daily_analysis_agent.run_skill``
（deepagents 工具循环，分析流程见 ``skills/stock-daily-analysis/SKILL.md``）；
结果按 (skill_id, input_hash) 缓存于 ai_analysis_result 表，stock_code
独立落列以便按标的检索。
"""

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig, PromptLoader, PromptSection
from app.core.config import get_settings
from app.core.locking import redis_lock
from app.models.watchlist import UserWatchlist, UserWatchlistGroup
from app.repositories.review import ai_analysis_repository
from app.schemas.stock import StockAiAnalysisResponse, StockAiAnalysisSection
from app.services.review.market_review_generator import (
    ReviewGenerationLockedError,
    ReviewInputDataNotReadyError,
)

logger = structlog.get_logger(__name__)

SKILL_ID = "stock-daily-analysis"
KLINE_BARS = 20
KLINE_WINDOW_DAYS = 40  # 日历日窗口，足够覆盖 KLINE_BARS 个交易日
LOCK_TTL_SECONDS = 300


def load_prompt_config() -> PromptConfig:
    config = PromptLoader(get_settings().prompts_dir).load("skills", SKILL_ID)
    if not config.sections:
        raise ValueError(f"{SKILL_ID} prompt 未声明任何 sections 分区")
    return config


def input_hash(stock_code: str, trade_date: date, sections: list[PromptSection]) -> str:
    """缓存键纳入股票代码与分区键集合：调整分区后旧缓存自动失效。"""
    keys = ",".join(section.key for section in sections)
    raw = f"{SKILL_ID}:{keys}:{stock_code}:{trade_date.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_response(
    *,
    stock_code: str,
    stock_name: str,
    trade_date: date,
    contents: dict[str, str],
    sections: list[PromptSection],
    model: str | None,
    generated_at: datetime,
    cached: bool,
) -> StockAiAnalysisResponse:
    return StockAiAnalysisResponse(
        stock_code=stock_code,
        stock_name=stock_name,
        trade_date=trade_date,
        model=model,
        generated_at=generated_at,
        cached=cached,
        sections=[
            StockAiAnalysisSection(
                key=section.key, title=section.title, content=contents.get(section.key, "")
            )
            for section in sections
        ],
    )


async def _load_cached(
    session: AsyncSession,
    stock_code: str,
    trade_date: date,
    sections: list[PromptSection],
) -> StockAiAnalysisResponse | None:
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=SKILL_ID, input_hash=input_hash(stock_code, trade_date, sections)
    )
    if row is None or not row.structured_output:
        return None
    output = row.structured_output
    return _build_response(
        stock_code=stock_code,
        stock_name=str(output.get("stock_name") or stock_code),
        trade_date=trade_date,
        contents=output.get("sections") or {},
        sections=sections,
        model=row.model,
        generated_at=row.created_at,
        cached=True,
    )


async def _load_recent_kline(
    session: AsyncSession, stock_code: str, trade_date: date
) -> list[Any]:
    from app.services.market import kline_service

    bars, _ = await kline_service.get_kline_by_code(
        session,
        stock_code,
        start_date=trade_date - timedelta(days=KLINE_WINDOW_DAYS),
        end_date=trade_date,
        page=1,
        page_size=KLINE_BARS,
    )
    return bars


async def _persist(
    session: AsyncSession,
    *,
    stock_code: str,
    stock_name: str,
    trade_date: date,
    hash_str: str,
    model: str,
    contents: dict[str, str],
    latency_ms: int,
) -> None:
    structured: dict[str, Any] = {
        "trade_date": trade_date.isoformat(),
        "stock_code": stock_code,
        "stock_name": stock_name,
        "sections": contents,
    }
    await ai_analysis_repository.insert_result(
        session,
        skill_id=SKILL_ID,
        input_hash=hash_str,
        prompt_id=SKILL_ID,
        model=model,
        structured=structured,
        latency_ms=latency_ms,
        stock_code=stock_code,
    )
    await session.commit()


async def generate_stock_analysis(
    session: AsyncSession,
    stock_code: str,
    *,
    trade_date: date,
    regenerate: bool = False,
) -> StockAiAnalysisResponse:
    """生成（或读取缓存的）单只股票指定交易日 AI 分析。

    Args:
        session: 数据库会话。
        stock_code: 股票代码。
        trade_date: 交易日。
        regenerate: 是否强制重新生成。

    Returns:
        StockAiAnalysisResponse，cached=True 表示命中已有缓存。

    Raises:
        ReviewInputDataNotReadyError: K 线与行情快照均缺失。
        ReviewGenerationLockedError: 锁被占用且缓存不存在。
    """
    from app.services.market import stock_service

    prompt_config = load_prompt_config()
    sections = prompt_config.sections
    current_hash = input_hash(stock_code, trade_date, sections)

    if not regenerate:
        cached = await _load_cached(session, stock_code, trade_date, sections)
        if cached is not None:
            return cached

    async with redis_lock(
        f"ai:{SKILL_ID}:{stock_code}:{trade_date.isoformat()}",
        ttl=LOCK_TTL_SECONDS,
        blocking=True,
        blocking_timeout=30,
    ) as acquired:
        if not acquired:
            cached = await _load_cached(session, stock_code, trade_date, sections)
            if cached is not None:
                return cached
            raise ReviewGenerationLockedError(
                f"其他实例正在生成 {stock_code} {trade_date.isoformat()} 的个股分析"
            )

        if not regenerate:
            cached = await _load_cached(session, stock_code, trade_date, sections)
            if cached is not None:
                return cached

        stock = await stock_service.get_stock_by_code(session, stock_code)
        stock_name = stock.stock_name if stock else stock_code

        kline_bars = await _load_recent_kline(session, stock_code, trade_date)
        quote = await stock_service.get_stock_quote(session, stock_code)
        if not kline_bars and not quote:
            raise ReviewInputDataNotReadyError(
                f"{stock_code} 的 K 线与行情数据尚未就绪，无法生成个股分析"
            )

        from app.agent.skills.stock_daily_analysis_agent import run_skill

        contents, model_name, latency_ms = await run_skill(
            session,
            stock_code,
            trade_date=trade_date,
            stock_name=stock_name,
            prompt_config=prompt_config,
        )

        await _persist(
            session,
            stock_code=stock_code,
            stock_name=stock_name,
            trade_date=trade_date,
            hash_str=current_hash,
            model=model_name,
            contents=contents,
            latency_ms=latency_ms,
        )

        return _build_response(
            stock_code=stock_code,
            stock_name=stock_name,
            trade_date=trade_date,
            contents=contents,
            sections=sections,
            model=model_name,
            generated_at=datetime.now(timezone.utc),
            cached=False,
        )


async def persist_stock_analysis(
    session: AsyncSession,
    stock_code: str,
    *,
    trade_date: date,
    contents: dict[str, str],
    model: str,
) -> StockAiAnalysisResponse:
    """将助手/skill 产出的四分区分析落库（ai_analysis_result），返回响应。

    Raises:
        ValueError: sections 缺少 prompt 声明的分区键或内容为空。
    """
    from app.services.market import stock_service

    sections = load_prompt_config().sections
    missing = [s.key for s in sections if not (contents.get(s.key) or "").strip()]
    if missing:
        expected = ", ".join(s.key for s in sections)
        raise ValueError(
            f"sections 缺少必填分区：{', '.join(missing)}；期望键集：{expected}"
        )

    stock = await stock_service.get_stock_by_code(session, stock_code)
    stock_name = stock.stock_name if stock else stock_code

    await _persist(
        session,
        stock_code=stock_code,
        stock_name=stock_name,
        trade_date=trade_date,
        hash_str=input_hash(stock_code, trade_date, sections),
        model=model,
        contents={s.key: contents[s.key] for s in sections},
        latency_ms=0,
    )
    return _build_response(
        stock_code=stock_code,
        stock_name=stock_name,
        trade_date=trade_date,
        contents=contents,
        sections=sections,
        model=model,
        generated_at=datetime.now(timezone.utc),
        cached=False,
    )


async def get_stock_analysis(
    session: AsyncSession, stock_code: str, *, trade_date: date
) -> StockAiAnalysisResponse | None:
    """读取已生成的个股分析缓存；无则返回 None。"""
    sections = load_prompt_config().sections
    return await _load_cached(session, stock_code, trade_date, sections)


async def is_generation_running(stock_code: str, trade_date: date) -> bool:
    """该股当日分析的生成锁是否被持有（异步生成进行中）。"""
    from app.core.cache import get_redis

    client = get_redis()
    lock = client.lock(
        f"lock:ai:{SKILL_ID}:{stock_code}:{trade_date.isoformat()}",
        thread_local=False,
    )
    return bool(await lock.locked())


async def list_analysis_trade_dates(
    session: AsyncSession, stock_code: str
) -> list[date]:
    """该股已成功生成分析的全部交易日（升序），供日历标记。"""
    return await ai_analysis_repository.list_success_trade_dates(
        session, skill_id=SKILL_ID, stock_code=stock_code
    )


async def list_active_watch_stock_codes(session: AsyncSession) -> list[str]:
    """开启 AI 复盘分组内的去重股票代码（定时任务遍历范围）。"""
    stmt = (
        select(UserWatchlist.stock_code)
        .join(UserWatchlistGroup, UserWatchlist.group_id == UserWatchlistGroup.id)
        .where(UserWatchlistGroup.ai_review_enabled.is_(True))
        .distinct()
        .order_by(UserWatchlist.stock_code)
    )
    return list((await session.execute(stmt)).scalars())
