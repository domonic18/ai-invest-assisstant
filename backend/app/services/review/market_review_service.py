"""AI 大盘综述服务：读取用户视图与按分区编辑保存（facade / 事务边界）。

共享 base 的生成与缓存见 ``market_review_generator``，响应组装见
``market_review_formatter``。用户编辑副本保存在 user_market_review 表
（sections JSONB 列），读取时按分区 overlay。
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnprocessableEntityError
from app.repositories.review import user_market_review_repository
from app.schemas.market import MarketReviewResponse
from app.services import market_stats_service
from app.services.review.market_review_formatter import (
    build_response,
)
from app.services.review.market_review_generator import (
    NonTradingDayError,
    ReviewGenerationLockedError,
    ReviewInputDataNotReadyError,
    ReviewNotFoundError,
    _load_base_review,
    _load_user_edit_row,
    assert_trading_day,
    generate_market_review,
    load_prompt_config,
)

__all__ = [
    "NonTradingDayError",
    "ReviewNotFoundError",
    "ReviewGenerationLockedError",
    "ReviewInputDataNotReadyError",
    "UnknownSectionError",
    "generate_market_review",
    "get_market_review",
    "update_market_review",
]


class UnknownSectionError(UnprocessableEntityError):
    """编辑的分区未在 prompt YAML 的 sections 中声明。"""


async def get_market_review(
    session: AsyncSession,
    user_id: int,
    trade_date: date | None = None,
) -> MarketReviewResponse | None:
    """读取用户视图的大盘综述：用户编辑版按分区 overlay 在共享 base 之上。

    只读，不触发 LLM 生成。
    """
    if trade_date is not None:
        await assert_trading_day(session, trade_date)
    stats = await market_stats_service.get_market_stats(session, trade_date)
    resolved_date = stats.trade_date

    sections = load_prompt_config().sections
    base = await _load_base_review(session, resolved_date, sections)
    user_row = await _load_user_edit_row(session, user_id, resolved_date)
    if user_row is None:
        return base.response if base is not None else None

    base_contents = (
        {item.key: item.content for item in base.response.sections}
        if base is not None
        else {}
    )
    user_sections: dict[str, str] = user_row.sections or {}
    merged = {
        section.key: user_sections.get(section.key, base_contents.get(section.key, ""))
        for section in sections
    }
    base_model = base.response.model if base is not None else None
    return build_response(
        trade_date=resolved_date,
        contents=merged,
        sections=sections,
        model=user_row.model or base_model,
        generated_at=user_row.generated_at or user_row.created_at,
        cached=True,
        edited=True,
    )


async def update_market_review(
    session: AsyncSession,
    user_id: int,
    trade_date: date,
    section_key: str,
    content: str,
) -> MarketReviewResponse:
    """按分区保存用户编辑内容到个人账户（不影响共享 base）。

    其余分区沿用用户已有编辑，未曾编辑的分区从共享 base 拷贝补齐。
    """
    await assert_trading_day(session, trade_date)

    sections = load_prompt_config().sections
    if section_key not in {section.key for section in sections}:
        raise UnknownSectionError(f"未知的复盘分区：{section_key}")

    base = await _load_base_review(session, trade_date, sections)
    if base is None:
        from app.services.review.market_review_generator import ReviewNotFoundError

        raise ReviewNotFoundError(f"{trade_date.isoformat()} 尚未生成 AI 复盘")

    merged = {item.key: item.content for item in base.response.sections}
    existing = await _load_user_edit_row(session, user_id, trade_date)
    if existing is not None:
        merged.update(existing.sections or {})
    merged[section_key] = content

    await user_market_review_repository.upsert_sections(
        session,
        user_id=user_id,
        trade_date=trade_date,
        sections=merged,
        model=base.response.model,
        generated_at=base.response.generated_at,
        base_review_id=base.id,
    )
    await session.commit()

    return build_response(
        trade_date=trade_date,
        contents=merged,
        sections=sections,
        model=base.response.model,
        generated_at=base.response.generated_at,
        cached=True,
        edited=True,
    )
