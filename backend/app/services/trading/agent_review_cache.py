"""复盘缓存键与 ai_analysis_result 读写（生成/查询共用）。"""

import hashlib
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.review import ai_analysis_repository
from app.services.trading.agent_review_content import (
    REVIEW_CONTRACT_VERSION,
    REVIEW_SKILL_ID,
    PaperTradeReviewRecord,
)


def input_hash(
    agent_key: str, account_id: int, period: str, start: date, end: date
) -> str:
    """缓存键：技能 + 契约版本 + Agent + 账户 + 周期 + 窗口。

    契约版本进键，持久化契约升级后旧行失配重算，不会把旧行补空值当命中返回。
    """
    raw = (
        f"{REVIEW_SKILL_ID}:v{REVIEW_CONTRACT_VERSION}:{agent_key}:{account_id}:"
        f"{period}:{start.isoformat()}:{end.isoformat()}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def load_cached(
    session: AsyncSession, input_hash: str
) -> PaperTradeReviewRecord | None:
    """按缓存键读取最新成功行并解析为读模型。"""
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=REVIEW_SKILL_ID, input_hash=input_hash
    )
    if row is None or not row.structured_output:
        return None
    return PaperTradeReviewRecord.model_validate(row.structured_output)


async def persist_review(
    session: AsyncSession,
    *,
    input_hash: str,
    content: Any,
    meta: dict[str, Any] | None = None,
) -> int:
    """落缓存行（不 commit，与经验沉淀同一事务提交）；返回行 id 作记忆溯源。

    meta 携带 run_structured 的 model_name/latency_ms（D35 补全）。
    """
    meta = meta or {}
    return await ai_analysis_repository.insert_result(
        session,
        skill_id=REVIEW_SKILL_ID,
        input_hash=input_hash,
        prompt_id=REVIEW_SKILL_ID,
        model=meta.get("model_name"),
        structured=content.model_dump(mode="json"),
        latency_ms=int(meta.get("latency_ms") or 0),
        status="success",
    )
