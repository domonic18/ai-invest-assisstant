"""后台 AI 分析结果通用管理服务。

``SKILL_DESCRIPTORS`` 是新增 AI 任务纳管的唯一扩展点：登记 skill_id / label /
完成事件 / 重新生成 prompt 模板 / 业务键提取函数即可出现在管理页，
无需改动仓储、路由或前端管线。
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, today_cn
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.ai_analysis_result import AiAnalysisResult
from app.repositories.admin import ai_result_repository
from app.schemas.ai_result import (
    AdminAiResultDetail,
    AdminAiResultItem,
    AdminAiResultKeyField,
    AdminAiSkillInfo,
)
from app.services.chain.chain_analysis_service import SKILL_ID as CHAIN_SKILL_ID
from app.services.review.limit_up_ai_service import (
    SKILL_ID as LIMIT_UP_SKILL_ID,
)
from app.services.review.limit_up_ai_service import (
    _input_hash as _limit_up_input_hash,
)
from app.services.review.market_review_generator import (
    SKILL_ID as MARKET_REVIEW_SKILL_ID,
)
from app.services.review.stock_daily_analysis_service import (
    SKILL_ID as STOCK_ANALYSIS_SKILL_ID,
)

UNKNOWN = "未知"

ExtractFn = Callable[[AiAnalysisResult, dict[str, Any]], list[AdminAiResultKeyField]]

_CHAIN_HASH_RE = re.compile(r"^(\d+):(.+):v(\d+)$")


def _json_text(row: AiAnalysisResult, key: str) -> str | None:
    output = row.structured_output
    if not isinstance(output, dict):
        return None
    raw = output.get(key)
    if raw is None or raw == "":
        return None
    return str(raw)


def _field(name: str, label: str, value: str | None) -> AdminAiResultKeyField:
    return AdminAiResultKeyField(name=name, label=label, value=value or UNKNOWN)


def _extract_market_review(
    row: AiAnalysisResult, ctx: dict[str, Any]
) -> list[AdminAiResultKeyField]:
    return [_field("trade_date", "交易日", _json_text(row, "trade_date"))]


def _extract_stock_analysis(
    row: AiAnalysisResult, ctx: dict[str, Any]
) -> list[AdminAiResultKeyField]:
    return [
        _field(
            "stock_code",
            "股票代码",
            row.stock_code or _json_text(row, "stock_code"),
        ),
        _field("stock_name", "股票名称", _json_text(row, "stock_name")),
        _field("trade_date", "交易日", _json_text(row, "trade_date")),
    ]


def _extract_limit_up(
    row: AiAnalysisResult, ctx: dict[str, Any]
) -> list[AdminAiResultKeyField]:
    index: dict[str, date] = ctx.get("trade_dates_by_hash", {})
    trade_date = index.get(row.input_hash or "")
    return [
        _field("trade_date", "交易日", trade_date.isoformat() if trade_date else None)
    ]


def _extract_chain(
    row: AiAnalysisResult, ctx: dict[str, Any]
) -> list[AdminAiResultKeyField]:
    match = _CHAIN_HASH_RE.match(row.input_hash or "")
    if match is None:
        return []
    return [
        _field("user_id", "用户", match.group(1)),
        _field("industry", "行业", match.group(2)),
        _field("version", "版本", f"v{match.group(3)}"),
    ]


def _extract_noop(
    row: AiAnalysisResult, ctx: dict[str, Any]
) -> list[AdminAiResultKeyField]:
    return []


@dataclass(frozen=True)
class AdminSkillDescriptor:
    """单个 AI skill 的管理元数据（label 展示 / 事件订阅 / 重新生成 / 业务键提取）。"""

    skill_id: str
    label: str
    event_type: str | None
    prompt_template: str | None
    extract: ExtractFn


SKILL_DESCRIPTORS: list[AdminSkillDescriptor] = [
    AdminSkillDescriptor(
        skill_id=MARKET_REVIEW_SKILL_ID,
        label="大盘每日复盘",
        event_type="market_daily_review.complete",
        prompt_template="请重新生成 {trade_date} 的大盘每日复盘",
        extract=_extract_market_review,
    ),
    AdminSkillDescriptor(
        skill_id=LIMIT_UP_SKILL_ID,
        label="涨停归因",
        event_type="limit_up_attribution.complete",
        prompt_template="请重新生成 {trade_date} 的涨停板块归因",
        extract=_extract_limit_up,
    ),
    AdminSkillDescriptor(
        skill_id=STOCK_ANALYSIS_SKILL_ID,
        label="个股分析",
        event_type="stock_daily_analysis.complete",
        prompt_template="请重新生成 {stock_code}（{trade_date}）的每日个股分析",
        extract=_extract_stock_analysis,
    ),
    AdminSkillDescriptor(
        skill_id=CHAIN_SKILL_ID,
        label="产业链分析",
        event_type=None,
        prompt_template=None,
        extract=_extract_chain,
    ),
]


class AdminAiResultService:
    """后台 AI 分析结果管理服务（查看 / 删除 / 重新生成触发）。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ai_result_repository

    @staticmethod
    def list_skills() -> list[AdminAiSkillInfo]:
        """已纳管 AI skill 清单（前端 Tab 与完成事件订阅的数据源）。"""
        return [
            AdminAiSkillInfo(
                skill_id=d.skill_id, label=d.label, event_type=d.event_type
            )
            for d in SKILL_DESCRIPTORS
        ]

    async def list_results(
        self,
        skill_id: str,
        *,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdminAiResultItem], int]:
        """分页返回每个业务键最新一条生成记录的元信息。"""
        descriptor = self._descriptor(skill_id)
        rows, total = await self.repo.list_paginated(
            self.session,
            skill_id=skill_id,
            page=page,
            page_size=page_size,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        counts = await self.repo.counts_by_hash(
            self.session, skill_id, [r.input_hash for r in rows if r.input_hash]
        )
        ctx = await self._extract_context(skill_id)
        items = [
            self._to_item(descriptor, row, counts.get(row.input_hash or "", 0), ctx)
            for row in rows
        ]
        return items, total

    async def get_detail(self, row_id: int) -> AdminAiResultDetail:
        """读取单条生成记录详情（未纳管 skill 也能查看原始内容）。"""
        row = await self._get_row(row_id)
        descriptor = self._descriptor_or_fallback(row.skill_id)
        ctx = await self._extract_context(row.skill_id)
        item = self._to_item(descriptor, row, 1, ctx)
        return AdminAiResultDetail(
            **item.model_dump(),
            error_msg=row.error_msg,
            structured_output=row.structured_output,
        )

    async def delete(self, row_id: int) -> int:
        """删除该业务键的全部生成记录（缓存清除），返回删除行数。"""
        row = await self._get_row(row_id)
        if row.input_hash:
            deleted = await self.repo.delete_by_hash(
                self.session, skill_id=row.skill_id, input_hash=row.input_hash
            )
        else:
            deleted = await self.repo.delete_by_id(self.session, row_id)
        await self.session.commit()
        return deleted

    async def _get_row(self, row_id: int) -> AiAnalysisResult:
        row = await self.repo.get_by_id(self.session, row_id)
        if row is None:
            raise NotFoundError(f"生成记录 {row_id} 不存在")
        return row

    def _descriptor(self, skill_id: str) -> AdminSkillDescriptor:
        for descriptor in SKILL_DESCRIPTORS:
            if descriptor.skill_id == skill_id:
                return descriptor
        raise UnprocessableEntityError(f"未纳管的 AI skill：{skill_id}")

    def _descriptor_or_fallback(self, skill_id: str) -> AdminSkillDescriptor:
        if any(d.skill_id == skill_id for d in SKILL_DESCRIPTORS):
            return self._descriptor(skill_id)
        return AdminSkillDescriptor(
            skill_id=skill_id,
            label=skill_id,
            event_type=None,
            prompt_template=None,
            extract=_extract_noop,
        )

    async def _extract_context(self, skill_id: str) -> dict[str, Any]:
        """业务键提取的辅助数据（目前仅 limit-up 需要 reverse-hash 日期索引）。"""
        if skill_id != LIMIT_UP_SKILL_ID:
            return {}
        earliest = await self.repo.min_created_at(self.session, skill_id)
        if earliest is None:
            return {}
        start = earliest.astimezone(CN_TZ).date()
        end = today_cn()
        days = (end - start).days + 1
        return {
            "trade_dates_by_hash": {
                _limit_up_input_hash(start + timedelta(offset)): start + timedelta(offset)
                for offset in range(max(days, 0))
            }
        }

    @staticmethod
    def _to_item(
        descriptor: AdminSkillDescriptor,
        row: AiAnalysisResult,
        history_count: int,
        ctx: dict[str, Any],
    ) -> AdminAiResultItem:
        fields = descriptor.extract(row, ctx)
        prompt = None
        if (
            descriptor.prompt_template
            and fields
            and all(f.value != UNKNOWN for f in fields)
        ):
            prompt = descriptor.prompt_template.format(
                **{f.name: f.value for f in fields}
            )
        return AdminAiResultItem(
            id=row.id,
            skill_id=row.skill_id,
            key_fields=fields,
            model=row.model,
            latency_ms=row.latency_ms,
            status=row.status,
            created_at=row.created_at,
            history_count=history_count,
            regenerate_prompt=prompt,
        )
