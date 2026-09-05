"""后台大盘复盘管理服务：共享 base 记录的增删改查（事务边界）。"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.admin import market_review_repository
from app.schemas.market import (
    AdminMarketReviewItem,
    AdminSectionDefinition,
    MarketReviewResponse,
)
from app.services.review.market_review_generator import (
    SKILL_ID,
    ReviewNotFoundError,
    _load_base_review,
    assert_trading_day,
    load_prompt_config,
    persist_market_review_result,
)

MANUAL_MODEL = "manual"


class AdminMarketReviewService:
    """后台大盘复盘管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = market_review_repository

    async def list_reviews(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[AdminMarketReviewItem], int]:
        """分页返回每个交易日最新一条复盘的元信息与计数。"""
        rows, total = await self.repo.list_paginated(
            self.session,
            skill_id=SKILL_ID,
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
        )
        parsed: list[tuple[date, Any]] = []
        for row in rows:
            raw = (row.structured_output or {}).get("trade_date")
            try:
                parsed.append((date.fromisoformat(str(raw)), row))
            except (TypeError, ValueError):
                continue
        trade_dates = [trade_date for trade_date, _ in parsed]
        history = await self.repo.counts_by_date(self.session, SKILL_ID, trade_dates)
        copies = await self.repo.user_copy_counts(self.session, trade_dates)

        items = [
            AdminMarketReviewItem(
                trade_date=trade_date,
                model=row.model,
                latency_ms=row.latency_ms,
                generated_at=row.created_at,
                history_count=history.get(trade_date, 0),
                user_copy_count=copies.get(trade_date, 0),
            )
            for trade_date, row in parsed
        ]
        return items, total

    async def get_detail(self, trade_date: date) -> MarketReviewResponse:
        """读取指定交易日最新一条复盘的完整分区内容。"""
        base = await _load_base_review(
            self.session, trade_date, load_prompt_config().sections
        )
        if base is None:
            raise ReviewNotFoundError(f"{trade_date.isoformat()} 尚无 AI 复盘记录")
        return base.response

    async def create_manual(
        self, trade_date: date, sections: dict[str, str]
    ) -> MarketReviewResponse:
        """手动创建指定交易日的复盘（覆盖同日已有 base，成为最新一条）。"""
        await assert_trading_day(self.session, trade_date)
        return await persist_market_review_result(
            self.session, trade_date=trade_date, contents=sections, model=MANUAL_MODEL
        )

    async def update_sections(
        self, trade_date: date, sections: dict[str, str]
    ) -> MarketReviewResponse:
        """以新记录覆盖指定交易日的复盘内容（旧行保留作历史）。"""
        base = await _load_base_review(
            self.session, trade_date, load_prompt_config().sections
        )
        if base is None:
            raise ReviewNotFoundError(f"{trade_date.isoformat()} 尚无 AI 复盘记录")
        return await persist_market_review_result(
            self.session, trade_date=trade_date, contents=sections, model=MANUAL_MODEL
        )

    async def delete(self, trade_date: date) -> int:
        """删除该交易日全部生成记录，返回删除行数。"""
        deleted = await self.repo.delete_by_date(
            self.session, skill_id=SKILL_ID, trade_date=trade_date
        )
        if deleted == 0:
            raise ReviewNotFoundError(f"{trade_date.isoformat()} 尚无 AI 复盘记录")
        await self.session.commit()
        return deleted

    @staticmethod
    def section_definitions() -> list[AdminSectionDefinition]:
        """prompt YAML 声明的分区定义（手动填写表单的数据源）。"""
        return [
            AdminSectionDefinition(key=section.key, title=section.title)
            for section in load_prompt_config().sections
        ]
