"""异动 AI 归因服务（anomaly-attribution skill）。

两条路径共用本服务（见根 CLAUDE.md AI 交互范式）：
- 自动路径：检测任务尾部对强度榜 top-N 批量归因（单次 LLM 调用）；
- 手动路径：异动页「AI 归因」按钮经助手 agent 取证后 persist 工具落库。

归因底稿按 (skill_id, input_hash=skill+域+代码+日期) 缓存在
``ai_analysis_result``，已生成直接复用；归因回写只覆盖检测行的
``attribution_category`` / ``attribution_summary``（docs/arch/08 §5/§6）。
本模块顶层不导入 agent 层，执行器在生成路径内延迟导入。
"""

import hashlib
from datetime import date
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locking import DEFAULT_LOCK_TTL_SECONDS, redis_lock
from app.repositories.market import anomaly_repository
from app.repositories.review import ai_analysis_repository
from app.services.market.anomaly_common import AnomalyInputNotReadyError
from app.skills.prompt import load_skill_prompt

logger = structlog.get_logger(__name__)

SKILL_ID = "anomaly-attribution"

DOMAINS = ("sector", "stock")

SECTOR_CATEGORIES = frozenset({"resonance", "rotation"})
STOCK_CATEGORIES = frozenset({"breakout", "acceleration", "pullback"})

_DOMAIN_LABELS = {"sector": "板块", "stock": "个股"}


class SectorAttributionItem(BaseModel):
    """单条板块异动的 LLM 归因输出。"""

    sector_type: str
    sector_code: str
    category: str
    summary: str


class SectorAnomalyAttributionContent(BaseModel):
    """板块域批量结构化输出（items 覆盖全部输入标的）。"""

    items: list[SectorAttributionItem]


class StockAttributionItem(BaseModel):
    """单条个股异动的 LLM 归因输出。"""

    stock_code: str
    category: str
    summary: str


class StockAnomalyAttributionContent(BaseModel):
    """个股域批量结构化输出（items 覆盖全部输入标的）。"""

    items: list[StockAttributionItem]


def _input_hash(domain: str, code: str, trade_date: date) -> str:
    return hashlib.sha256(
        f"{SKILL_ID}:{domain}:{code}:{trade_date.isoformat()}".encode()
    ).hexdigest()


def _row_code(domain: str, row: Any) -> str:
    """检测行的归因键：板块用 type:code（行业/概念可能同码），个股用 6 位码。"""
    if domain == "sector":
        return f"{row.sector_type}:{row.sector_code}"
    return str(row.stock_code)


def _item_code(domain: str, item: Any) -> str:
    if domain == "sector":
        return f"{item.sector_type}:{item.sector_code}"
    return str(item.stock_code)


def _allowed_categories(domain: str) -> frozenset[str]:
    return SECTOR_CATEGORIES if domain == "sector" else STOCK_CATEGORIES


def _sector_targets(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "sector_type": row.sector_type,
            "sector_code": row.sector_code,
            "sector_name": row.sector_name,
            "change_pct": float(row.change_pct) if row.change_pct is not None else None,
            "amount_ratio": (
                float(row.amount_ratio) if row.amount_ratio is not None else None
            ),
            "up_count": row.up_count,
            "down_count": row.down_count,
            "anomaly_types": list(row.anomaly_types or []),
            "strength": row.strength,
            "rule_category": row.attribution_category,
        }
        for row in rows
    ]


def _stock_targets(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "stock_code": row.stock_code,
            "stock_name": row.stock_name,
            "change_pct": float(row.change_pct) if row.change_pct is not None else None,
            "turnover_rate": (
                float(row.turnover_rate) if row.turnover_rate is not None else None
            ),
            "volume_ratio": (
                float(row.volume_ratio) if row.volume_ratio is not None else None
            ),
            "is_above_ma60": row.is_above_ma60,
            "ma60_breakout": row.ma60_breakout,
            "anomaly_types": list(row.anomaly_types or []),
            "strength": row.strength,
            "rule_category": row.attribution_category,
        }
        for row in rows
    ]


def _normalize_entries(
    content_items: list[Any],
    pending_targets: list[dict[str, Any]],
    domain: str,
) -> list[tuple[str, str, str]]:
    """后置校验：仅保留清单内标的与合法分类，返回 (键, category, summary)。"""
    valid = {_key_of_target(domain, t) for t in pending_targets}
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for item in content_items:
        code = _item_code(domain, item)
        if code not in valid or code in seen:
            continue
        seen.add(code)
        category = item.category if item.category in _allowed_categories(domain) else ""
        if not category:
            continue
        entries.append((code, category, item.summary))
    return entries


def _key_of_target(domain: str, target: dict[str, Any]) -> str:
    if domain == "sector":
        return f"{target['sector_type']}:{target['sector_code']}"
    return str(target["stock_code"])


async def _list_rows(session: AsyncSession, domain: str, trade_date: date) -> list[Any]:
    if domain == "sector":
        return await anomaly_repository.list_sector_anomalies(session, trade_date)
    return await anomaly_repository.list_stock_anomalies(session, trade_date)


async def _load_cached_entries(
    session: AsyncSession,
    domain: str,
    trade_date: date,
    keys: list[str],
) -> dict[str, tuple[str, str]]:
    """读取已生成的归因底稿，返回 键 → (category, summary)。"""
    result: dict[str, tuple[str, str]] = {}
    for key in keys:
        row = await ai_analysis_repository.load_latest_success(
            session,
            skill_id=SKILL_ID,
            input_hash=_input_hash(domain, key, trade_date),
        )
        if row is None or not isinstance(row.structured_output, dict):
            continue
        payload = row.structured_output
        category, summary = payload.get("category"), payload.get("summary")
        if isinstance(category, str) and isinstance(summary, str) and category:
            result[key] = (category, summary)
    return result


async def _insert_cache_rows(
    session: AsyncSession,
    domain: str,
    trade_date: date,
    entries: list[tuple[str, str, str]],
    *,
    model: str,
    latency_ms: int,
) -> None:
    """归因底稿逐标的写 ai_analysis_result（批量一次生成，N 行缓存）。"""
    for key, category, summary in entries:
        code = key.split(":", 1)[1] if domain == "sector" else key
        await ai_analysis_repository.insert_result(
            session,
            skill_id=SKILL_ID,
            input_hash=_input_hash(domain, key, trade_date),
            prompt_id=SKILL_ID,
            model=model,
            structured={"category": category, "summary": summary},
            latency_ms=latency_ms,
            status="success",
            stock_code=code if domain == "stock" else None,
        )


def _apply_to_rows(rows: list[Any], domain: str, entries: dict[str, tuple[str, str]]) -> None:
    """把归因条目回写到检测 ORM 行（不 commit，事务由调用方控制）。"""
    for row in rows:
        entry = entries.get(_row_code(domain, row))
        if entry is None:
            continue
        row.attribution_category = entry[0]
        row.attribution_summary = entry[1]


async def _generate_missing(
    session: AsyncSession,
    domain: str,
    trade_date: date,
    pending_targets: list[dict[str, Any]],
) -> dict[str, tuple[str, str]]:
    """单次 LLM 调用生成未缓存标的的归因，写底稿缓存并返回条目映射。"""
    prompt_config = load_skill_prompt(SKILL_ID)

    # 延迟导入：执行器反向依赖本模块输出模型，避免 services 聚合时环导入
    from app.agent.skills.anomaly_attribution_agent import run_skill

    content, model_name, latency_ms = await run_skill(
        session,
        domain=domain,
        trade_date=trade_date,
        targets=pending_targets,
        prompt_config=prompt_config,
    )

    entries = _normalize_entries(content.items, pending_targets, domain)
    # 漏标的按规则分类兜底并落一条占位摘要，避免每轮重跑重复生成
    covered = {key for key, _, _ in entries}
    for target in pending_targets:
        key = _key_of_target(domain, target)
        if key not in covered:
            rule = str(target.get("rule_category") or "")
            entries.append((key, rule, "证据不足，保留规则分类"))

    await _insert_cache_rows(
        session, domain, trade_date, entries, model=model_name, latency_ms=latency_ms
    )
    return {key: (category, summary) for key, category, summary in entries}


async def run_top_n_attribution(
    session: AsyncSession,
    domain: str,
    trade_date: date,
    *,
    top_n: int,
) -> dict[str, int]:
    """检测任务尾：对强度榜 top-N 批量归因并回写。

    缓存优先（已生成直接复用）；剩余标的合并为单次 LLM 调用；同域同日
    已有实例在生成时跳过本轮（下轮重跑补齐）。LLM 失败向上抛出，由
    spider 尾部兜底，不影响检测成败。

    Returns:
        {"targets": 参与归因条数, "from_cache": 缓存复用, "generated": 本次生成}。
    """
    rows = await _list_rows(session, domain, trade_date)
    if not rows:
        return {"targets": 0, "from_cache": 0, "generated": 0}
    top_rows = rows[:top_n]
    targets = _sector_targets(top_rows) if domain == "sector" else _stock_targets(top_rows)
    keys = [_key_of_target(domain, target) for target in targets]

    cached = await _load_cached_entries(session, domain, trade_date, keys)
    entries = dict(cached)
    pending = [key for key in keys if key not in cached]

    generated: dict[str, tuple[str, str]] = {}
    if pending:
        async with redis_lock(
            f"{SKILL_ID}:{domain}:{trade_date.isoformat()}",
            ttl=DEFAULT_LOCK_TTL_SECONDS,
        ) as acquired:
            if acquired:
                pending_targets = [
                    target
                    for target in targets
                    if _key_of_target(domain, target) in set(pending)
                ]
                generated = await _generate_missing(
                    session, domain, trade_date, pending_targets
                )
                entries.update(generated)
            else:
                logger.warning(
                    "anomaly_attribution_locked_skip",
                    domain=domain,
                    trade_date=trade_date.isoformat(),
                    pending=len(pending),
                )

    _apply_to_rows(top_rows, domain, entries)
    await session.commit()
    stats = {
        "targets": len(keys),
        "from_cache": len(cached),
        "generated": len(generated),
    }
    logger.info("anomaly_attribution_tail_done", domain=domain, **stats)
    return stats


async def persist_manual_attribution(
    session: AsyncSession,
    domain: str,
    trade_date: date,
    items: list[dict[str, Any]],
    *,
    model: str,
    latency_ms: int = 0,
) -> dict[str, int]:
    """手动路径落库：校验后回写检测行归因字段并写底稿缓存。

    Args:
        items: 归因条目，板块域含 sector_type/sector_code/category/summary，
            个股域含 stock_code/category/summary。

    Returns:
        {"attributed": 命中条数, "skipped": 清单外或非法分类条数}。

    Raises:
        AnomalyInputNotReadyError: 该交易日无检测数据。
        ValueError: 全部条目无效。
    """
    rows = await _list_rows(session, domain, trade_date)
    if not rows:
        label = _DOMAIN_LABELS[domain]
        raise AnomalyInputNotReadyError(f"{trade_date.isoformat()} 无{label}异动检测数据，无法归因")

    row_map = {_row_code(domain, row): row for row in rows}
    allowed = _allowed_categories(domain)
    applied: dict[str, tuple[str, str]] = {}
    skipped = 0
    for item in items:
        if domain == "sector":
            key = f"{item.get('sector_type')}:{item.get('sector_code')}"
        else:
            key = str(item.get("stock_code"))
        category = item.get("category")
        row = row_map.get(key)
        if row is None or category not in allowed:
            skipped += 1
            continue
        applied[key] = (str(category), str(item.get("summary") or ""))

    if not applied:
        raise ValueError("归因条目全部无效：标的不在检测清单内或分类非法")

    _apply_to_rows(rows, domain, applied)
    await _insert_cache_rows(
        session,
        domain,
        trade_date,
        [(key, category, summary) for key, (category, summary) in applied.items()],
        model=model,
        latency_ms=latency_ms,
    )
    await session.commit()
    logger.info(
        "anomaly_attribution_persisted",
        domain=domain,
        trade_date=trade_date.isoformat(),
        attributed=len(applied),
        skipped=skipped,
    )
    return {"attributed": len(applied), "skipped": skipped}
