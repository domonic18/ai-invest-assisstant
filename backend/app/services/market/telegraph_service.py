"""财联社电报查询服务。"""

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.repositories.market import telegraph_repository
from app.repositories.market.telegraph_repository import TelegraphRow
from app.repositories.news import ai_score_repository, subscription_repository
from app.schemas.news import ScoreFactorsResponse
from app.schemas.telegraph import TelegraphResponse, TelegraphStockResponse
from app.services.market import stock_service

_MARKET_PREFIX_RE = re.compile(r"^(sh|sz|bj)(\d{6})$", re.IGNORECASE)


def _bare_stock_code(raw: str) -> str:
    """cls 带市场前缀代码（sh600115）转裸代码（600115）。"""
    match = _MARKET_PREFIX_RE.match(raw.strip())
    return match.group(2) if match else raw.strip()


async def list_telegraph(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    min_importance: int | None = None,
    min_ai_score: int | None = None,
    subscription_only: bool = False,
    user_id: int | None = None,
) -> tuple[list[TelegraphRow], int]:
    """分页查询电报（publish_time 降序），返回 (当前页含 AI 分级, 总条数)。"""
    return await telegraph_repository.list_telegraph(
        session,
        page=page,
        page_size=page_size,
        category=category,
        min_importance=min_importance,
        min_ai_score=min_ai_score,
        subscription_user_id=user_id if subscription_only else None,
    )


def to_responses(
    rows: list[TelegraphRow],
    *,
    factors_map: dict[str, dict[str, Any]] | None = None,
    subscribed_ids: set[str] | None = None,
    stocks_map: dict[str, dict[str, Any]] | None = None,
) -> list[TelegraphResponse]:
    """把 ``(电报行, ai_score, ai_scored_at)`` 映射为响应模型（电报页/工作台共用）。

    factors_map/subscribed_ids/stocks_map 可选回填（资讯中心电报流 ★ 标注、
    评分构成与关联标的名称/当日涨跌幅）。
    """
    items: list[TelegraphResponse] = []
    for item, ai_score, ai_scored_at in rows:
        response = TelegraphResponse.model_validate(item)
        response.ai_score = ai_score
        response.ai_scored_at = ai_scored_at
        detail = (factors_map or {}).get(str(item.cls_msg_id))
        if subscribed_ids is not None:
            response.subscribed = str(item.cls_msg_id) in subscribed_ids
        if detail:
            factors = detail.get("factors")
            if isinstance(factors, dict):
                response.ai_factors = ScoreFactorsResponse.model_validate(factors)
        if stocks_map is not None:
            for raw in item.stock_codes or []:
                code = _bare_stock_code(raw)
                snap = stocks_map.get(code)
                response.stocks.append(
                    TelegraphStockResponse(
                        code=code,
                        name=snap["name"] if snap else raw,
                        change_pct=snap["change_pct"] if snap else None,
                    )
                )
        items.append(response)
    return items


async def enrich_and_respond(
    session: AsyncSession,
    rows: list[TelegraphRow],
    *,
    user_id: int,
) -> list[TelegraphResponse]:
    """按当前页条目批量回填评分构成、订阅命中与关联标的快照（电报流路由入口）。"""
    item_ids = [str(item.cls_msg_id) for item, _, _ in rows]
    if not item_ids:
        return []
    details = await ai_score_repository.score_details(
        session, source=NEWS_SOURCE_TELEGRAPH, item_ids=item_ids
    )
    subscribed_ids = await subscription_repository.hit_item_ids(
        session, user_id=user_id, source=NEWS_SOURCE_TELEGRAPH, item_ids=item_ids
    )
    codes = [
        _bare_stock_code(raw)
        for item, _, _ in rows
        for raw in (item.stock_codes or [])
    ]
    stocks_map = await stock_service.batch_quote_snapshot(session, codes)
    return to_responses(
        rows, factors_map=details, subscribed_ids=subscribed_ids, stocks_map=stocks_map
    )
