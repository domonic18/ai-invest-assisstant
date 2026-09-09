"""事件故事线服务：AI 建线/续接（定时路径）+ 手动建线与用户级操作（API 路径）。

故事线为全局内容（AI 线 + 手动线共用一张表，origin 区分）；用户级「停止跟踪」
只影响本人视图，AI 续接全局进行。
"""

import json
from datetime import datetime, time, timezone
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, today_cn
from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.core.locking import redis_lock
from app.repositories.news import storyline_repository
from app.schemas.news import (
    FocusItemResponse,
    FocusResponse,
    ScoreFactorsResponse,
    StorylineBatch,
    StorylineDetailResponse,
    StorylineItemResponse,
    StorylineResponse,
    UserStorylineAction,
)

logger = structlog.get_logger(__name__)

SKILL_ID = "news-storyline"

_LOCK_KEY = "news-storyline"
_LOCK_TTL_SECONDS = 900
_MAX_CANDIDATES = 40
_MIN_REPORTS_TO_CREATE = 5
_WINDOW_HOURS = 48
_MIN_SCORE = 70
_CONTENT_CHARS = 200
_INPUT_CHAR_CAP = 12000
_HIGHLIGHTS_LIMIT = 20
_FOCUS_LINES_LIMIT = 50


def _candidate_payload(row: Any) -> dict[str, Any]:
    """(电报行, score) -> 聚类输入 payload（content 节选控 token）。"""
    telegraph, score = row
    return {
        "source": storyline_repository.SOURCE_TELEGRAPH,
        "item_id": str(telegraph.cls_msg_id),
        "title": telegraph.title,
        "content": (telegraph.content or "")[:_CONTENT_CHARS],
        "category": telegraph.category,
        "stock_codes": telegraph.stock_codes or [],
        "score": score,
        "publish_time": telegraph.publish_time.isoformat(),
    }


async def build_stories(session: AsyncSession) -> dict[str, Any]:
    """对近 48h 高分未入线电报聚类：≥5 篇建新线、既有线续接（每 30 分钟）。

    Returns:
        {created: 新建线数, continued: 续接线数, attached: 新挂入条数}；
        未获锁或无候选时全零。
    """
    zeros = {"created": 0, "continued": 0, "attached": 0}
    async with redis_lock(_LOCK_KEY, ttl=_LOCK_TTL_SECONDS, blocking=False) as acquired:
        if not acquired:
            logger.info("storyline_lock_busy")
            return zeros

        rows = await storyline_repository.list_telegraph_candidates(
            session, limit=_MAX_CANDIDATES
        )
        if not rows:
            return zeros
        open_lines = await storyline_repository.list_open_lines(session)

        # 候选按发布时间新→旧排列，超出单轮字符上限时丢弃最旧的部分
        payload = [_candidate_payload(row) for row in rows]
        payload = _trim_to_cap(payload)

        from app.skills.prompt import load_skill_prompt

        prompt_config = load_skill_prompt(SKILL_ID)
        from app.agent.core.prompt_renderer import PromptRenderer
        from app.agent.runtime.structured import run_structured

        lines_payload = [
            {
                "storyline_id": line.id,
                "title": line.title,
                "summary": line.summary,
                "status": line.status,
            }
            for line in open_lines
        ]
        user_prompt = PromptRenderer.render(
            prompt_config.user_prompt_template,
            count=len(payload),
            items_json=json.dumps(payload, ensure_ascii=False),
            lines_json=json.dumps(lines_payload, ensure_ascii=False),
        )
        try:
            output: StorylineBatch = await run_structured(
                session, result_type=StorylineBatch, user_prompt=user_prompt
            )
        except Exception as exc:  # noqa: BLE001
            # LLM/解析失败本轮跳过，下轮任务重试（news-score 同款语义）
            logger.warning("storyline_llm_failed", error=str(exc))
            return zeros

        valid_keys = {(p["source"], p["item_id"]) for p in payload}
        publish_of = {
            (p["source"], p["item_id"]): datetime.fromisoformat(p["publish_time"])
            for p in payload
        }
        now = datetime.now(timezone.utc)
        created = 0
        attached_total = 0
        for draft in output.new_storylines:
            refs = [
                {"source": ref.source, "item_id": ref.item_id}
                for ref in draft.item_refs
                if (ref.source, ref.item_id) in valid_keys
            ]
            if len(refs) < _MIN_REPORTS_TO_CREATE:
                logger.info(
                    "storyline_draft_below_threshold",
                    title=draft.title,
                    refs=len(refs),
                )
                continue
            times = [publish_of[(r["source"], r["item_id"])] for r in refs]
            storyline_id = await storyline_repository.insert_storyline(
                session,
                title=draft.title,
                summary=draft.summary,
                status=draft.status,
                origin="ai",
                user_id=None,
                first_seen_at=min(times),
                last_seen_at=max(times),
                latest_brief=draft.latest_brief,
                nodes=[{"time": max(times).isoformat(), "brief": draft.latest_brief}],
            )
            inserted = await storyline_repository.attach_items(
                session, storyline_id=storyline_id, refs=refs
            )
            await storyline_repository.refresh_progress(
                session,
                storyline_id=storyline_id,
                status=draft.status,
                latest_brief=draft.latest_brief,
                nodes=None,
                last_seen_at=max(times),
            )
            created += 1
            attached_total += inserted

        open_line_ids = {line.id for line in open_lines}
        line_nodes = {line.id: list(line.nodes or []) for line in open_lines}
        continued = 0
        for att in output.attachments:
            if att.storyline_id not in open_line_ids:
                logger.warning(
                    "storyline_attach_unknown_line", storyline_id=att.storyline_id
                )
                continue
            refs = [
                {"source": ref.source, "item_id": ref.item_id}
                for ref in att.item_refs
                if (ref.source, ref.item_id) in valid_keys
            ]
            if not refs:
                continue
            inserted = await storyline_repository.attach_items(
                session, storyline_id=att.storyline_id, refs=refs
            )
            if inserted == 0:
                # 全部条目已挂入过：不追加节点不更新，保证续接幂等
                continue
            times = [publish_of[(r["source"], r["item_id"])] for r in refs]
            nodes = line_nodes.get(att.storyline_id, []) + [
                {"time": now.isoformat(), "brief": att.latest_brief}
            ]
            await storyline_repository.refresh_progress(
                session,
                storyline_id=att.storyline_id,
                status=att.status,
                latest_brief=att.latest_brief,
                nodes=nodes,
                last_seen_at=max(times + [now]),
            )
            continued += 1
            attached_total += inserted

        await session.commit()
        if created or continued:
            logger.info(
                "storyline_round_done",
                created=created,
                continued=continued,
                attached=attached_total,
            )
        return {
            "created": created,
            "continued": continued,
            "attached": attached_total,
        }


def _trim_to_cap(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """候选超出单轮字符上限时自尾部（最旧）裁剪，至少保留 1 条。"""
    total = sum(len(json.dumps(p, ensure_ascii=False)) for p in payload)
    while len(payload) > 1 and total > _INPUT_CHAR_CAP:
        removed = payload.pop()
        total -= len(json.dumps(removed, ensure_ascii=False))
    return payload


async def create_manual(
    session: AsyncSession,
    *,
    user_id: int,
    source: str,
    item_id: str,
) -> int:
    """用户手动建线（单条种子报道，origin=manual 仅本人视图）。"""
    existing = await storyline_repository.find_item_line(
        session, source=source, item_id=item_id
    )
    if existing is not None:
        raise ConflictError(f"该资讯已在故事线「{existing.title}」中，直接跟踪该线即可")

    if source != NEWS_SOURCE_TELEGRAPH:
        raise BadRequestError(f"暂不支持该来源建线：{source}")
    telegraph = await storyline_repository.get_telegraph(session, item_id)
    if telegraph is None:
        raise NotFoundError("资讯不存在")
    title = (telegraph.title or telegraph.content or "")[:60] or f"跟踪 {item_id}"
    publish_time = telegraph.publish_time
    brief = (telegraph.title or telegraph.content or "")[:80]

    storyline_id = await storyline_repository.insert_storyline(
        session,
        title=title,
        summary=None,
        status="tracking",
        origin="manual",
        user_id=user_id,
        first_seen_at=publish_time,
        last_seen_at=publish_time,
        latest_brief=brief,
        nodes=[{"time": publish_time.isoformat(), "brief": brief}],
    )
    await storyline_repository.attach_items(
        session, storyline_id=storyline_id, refs=[{"source": source, "item_id": item_id}]
    )
    await storyline_repository.refresh_progress(
        session,
        storyline_id=storyline_id,
        status="tracking",
        latest_brief=None,
        nodes=None,
        last_seen_at=publish_time,
    )
    await session.commit()
    return storyline_id


async def set_user_action(
    session: AsyncSession,
    *,
    user_id: int,
    storyline_id: int,
    action: str,
) -> None:
    """用户级跟踪操作（active/stopped upsert，manual 线归属校验）。"""
    await _get_visible_line(session, user_id=user_id, storyline_id=storyline_id)
    await storyline_repository.upsert_user_action(
        session, user_id=user_id, storyline_id=storyline_id, action=action
    )
    await session.commit()


async def get_focus(session: AsyncSession, *, user_id: int) -> FocusResponse:
    """重点与跟踪视图：今日重点（score≥70 含评分构成）+ 跟踪线列表。

    线列表为 AI 线全局 + 本人 manual 线，本人已停止跟踪的线不出现。
    """
    day_start = datetime.combine(
        today_cn(), time.min, tzinfo=CN_TZ
    ).astimezone(timezone.utc)
    rows = await storyline_repository.list_today_highlights(
        session, day_start=day_start, limit=_HIGHLIGHTS_LIMIT
    )
    highlights = [
        FocusItemResponse(
            source=storyline_repository.SOURCE_TELEGRAPH,
            item_id=str(telegraph.cls_msg_id),
            title=telegraph.title,
            content=telegraph.content,
            publish_time=telegraph.publish_time,
            score=score,
            factors=_factors_response(detail),
            reason=(detail or {}).get("reason"),
        )
        for telegraph, score, detail in rows
    ]
    line_rows = await storyline_repository.list_focus_storylines(
        session, user_id=user_id, limit=_FOCUS_LINES_LIMIT
    )
    storylines = [
        _storyline_response(line, user_action) for line, user_action in line_rows
    ]
    return FocusResponse(highlights=highlights, storylines=storylines)


async def get_story(
    session: AsyncSession,
    *,
    user_id: int,
    storyline_id: int,
) -> StorylineDetailResponse:
    """线详情：线卡 + 线内条目（JOIN 电报回显，manual 线仅本人可见）。"""
    line = await _get_visible_line(
        session, user_id=user_id, storyline_id=storyline_id
    )
    action = await storyline_repository.get_user_action(
        session, user_id=user_id, storyline_id=storyline_id
    )
    item_rows = await storyline_repository.list_storyline_items(
        session, storyline_id=storyline_id
    )
    items = [
        StorylineItemResponse(
            source=ref.source,
            item_id=ref.item_id,
            title=telegraph.title if telegraph is not None else None,
            content=telegraph.content if telegraph is not None else None,
            publish_time=telegraph.publish_time if telegraph is not None else None,
            score=score,
        )
        for ref, telegraph, score in item_rows
    ]
    base = _storyline_response(line, action)
    return StorylineDetailResponse(**base.model_dump(), items=items)


async def _get_visible_line(
    session: AsyncSession,
    *,
    user_id: int,
    storyline_id: int,
) -> Any:
    """取本人可见的线（AI 线全局、manual 线仅本人），否则 NotFound。"""
    line = await storyline_repository.get_storyline(session, storyline_id)
    if line is None or (line.origin == "manual" and line.user_id != user_id):
        raise NotFoundError("故事线不存在")
    return line


def _factors_response(detail: dict[str, Any] | None) -> ScoreFactorsResponse | None:
    """score_detail.factors -> 响应模型（存量行无构成为 None）。"""
    factors = (detail or {}).get("factors")
    if isinstance(factors, dict):
        return ScoreFactorsResponse.model_validate(factors)
    return None


def _storyline_response(
    line: Any, user_action: str | None
) -> StorylineResponse:
    response = StorylineResponse.model_validate(line)
    response.user_action = cast("UserStorylineAction | None", user_action)
    return response
