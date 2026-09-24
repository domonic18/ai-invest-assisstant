"""问财 NL2Data 网关客户端（query2data）与选股结果整形。

封装 ``openapi.iwencai.com`` 的 query2data 接口，支撑即席选股（/screening
直查端点与 ``screen_stocks`` 工具共用 ``screen()``）：全字符串请求体、空结果
按候选问句放宽改写重试（Call-Type=retry）、按问句哈希做 Redis 短缓存（防配额
消耗，非持久化）。结果零落库。
服务层保持纯净：不导入 ``app.agent.*``。
"""

import hashlib
import json
import re
import secrets
from collections.abc import Sequence
from datetime import time as dt_time
from typing import Any, cast

import httpx
import structlog

from app.core.cache import cache_get, cache_set
from app.core.clock import now_cn
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_QUERY2DATA_URL = "https://openapi.iwencai.com/v1/query2data"
_SKILL_ID = "hithink-zhishu-query"
_CACHE_KEY_PREFIX = "iwencai:q2d:"
_CACHE_TTL_INTRADAY_SECONDS = 300
_CACHE_TTL_OFFHOURS_SECONDS = 1800
_MAX_REWRITES = 2
# 单次返回行数上限（问财单页上限 100；直查与工具两路径共用）
_MAX_ROWS = 100
_FIXED_COLUMNS = ("股票代码", "股票简称")
# 放宽改写第一步：剔除"非ST / 非北交所 / 非次新"类排除子句（不越过且/与连接的下一条件）
_EXCLUSION_CLAUSE_RE = re.compile(r"[，,；;、且与]?\s*(?:非|排除|剔除)[^，,；;。且与]*")

__all__ = ["IwencaiError", "query2data", "screen"]


class IwencaiError(RuntimeError):
    """问财网关调用失败（未配置 Key / 请求失败 / 协议错误）。"""


def _cache_ttl_seconds() -> int:
    now = now_cn()
    intraday = now.weekday() < 5 and dt_time(9, 0) <= now.time() <= dt_time(15, 30)
    return _CACHE_TTL_INTRADAY_SECONDS if intraday else _CACHE_TTL_OFFHOURS_SECONDS


def _build_headers(api_key: str, call_type: str) -> dict[str, str]:
    # X-Claw 头集合来自公开实测实现（6 个）；调研记录曾提 7 个，若联调 401 需复核 SkillHub 文档
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": _SKILL_ID,
        "X-Claw-Skill-Version": "2.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }


async def _post_query2data(
    query: str, *, limit: int, page: int, call_type: str
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.iwencai_api_key:
        raise IwencaiError("问财 API Key 未配置（IWENCAI_API_KEY）")
    payload = {
        "query": query,
        "page": str(page),
        "limit": str(limit),
        "is_cache": "1",
        "expand_index": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.iwencai_timeout_seconds) as client:
            response = await client.post(
                _QUERY2DATA_URL, headers=_build_headers(settings.iwencai_api_key, call_type), json=payload
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise IwencaiError(f"问财网关请求失败：{exc}") from exc
    if data.get("status_code", 0) != 0:
        raise IwencaiError(f"问财网关返回错误：{data.get('status_msg') or '未知错误'}")
    return {
        "datas": data.get("datas") or [],
        "code_count": int(data.get("code_count") or 0),
        "chunks_info": data.get("chunks_info") or [],
    }


async def query2data(
    query: str,
    *,
    limit: int = 30,
    page: int = 1,
    rewrite_candidates: Sequence[str] = (),
) -> dict[str, Any]:
    """查询问财 query2data；空结果按候选问句放宽改写重试。

    Args:
        query: 原始问句。
        limit: 单页行数。
        page: 页码，从 1 起。
        rewrite_candidates: 空结果时依次使用的放宽改写问句，
            最多取前 ``_MAX_REWRITES`` 个。

    Returns:
        ``{"datas": list[dict], "code_count": int, "chunks_info": list}``；
        ``datas`` 为空表示原问句与全部改写均未命中。

    Raises:
        IwencaiError: 未配置 API Key / 网关请求失败 / 协议错误。
    """
    digest = hashlib.sha256(f"{limit}:{page}:{query}".encode()).hexdigest()
    cache_key = f"{_CACHE_KEY_PREFIX}{digest}"
    raw = await cache_get(cache_key)
    if raw:
        return cast("dict[str, Any]", json.loads(raw))

    attempts = [query, *list(rewrite_candidates)[:_MAX_REWRITES]]
    result: dict[str, Any] | None = None
    for index, candidate in enumerate(attempts):
        call_type = "normal" if index == 0 else "retry"
        result = await _post_query2data(candidate, limit=limit, page=page, call_type=call_type)
        if result["datas"]:
            break
        if index < len(attempts) - 1:
            logger.info(
                "iwencai_empty_retry",
                attempt=index + 1,
                query=candidate,
                next_query=attempts[index + 1],
            )
    assert result is not None

    await cache_set(cache_key, json.dumps(result, ensure_ascii=False), ex=_cache_ttl_seconds())
    logger.info(
        "iwencai_query2data",
        query=query,
        attempts=len(attempts),
        n_rows=len(result["datas"]),
        code_count=result["code_count"],
    )
    return result


def _normalize_code(raw: str) -> str:
    """``000523.SZ`` → ``000523``（与自选表 6 位代码格式对齐，归一单点）。"""
    return raw.split(".")[0].strip()


def _relaxed_rewrites(query: str) -> list[str]:
    """确定性放宽改写：剔除排除项子句；与原问句相同则丢弃。"""
    relaxed = _EXCLUSION_CLAUSE_RE.sub("", query).strip("，,；;、且与 ")
    return [relaxed] if relaxed and relaxed != query else []


def _derive_columns(rows: list[dict[str, Any]]) -> list[str]:
    """按行内首次出现顺序派生列元数据，排除固定两列。"""
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key in _FIXED_COLUMNS or key in seen:
                continue
            seen.add(key)
            columns.append(key)
    return columns


async def screen(query: str, *, limit: int = 50) -> dict[str, Any]:
    """即席选股：查询问财并整形为页面/事件共用的结构化载荷。

    Args:
        query: 问财自然语言问句（原样下发，问句措辞约束由调用方负责）。
        limit: 期望行数；服务端钳位到 ``[1, _MAX_ROWS]``。

    Returns:
        ``{"query", "total", "truncated", "columns", "stocks", "chunks_info"}``；
        ``stocks`` 行以 ``stockCode``/``stockName`` 加问财原始中文列透传，
        ``total`` 为网关命中总数（事件载荷/直查响应共用，零落库）。

    Raises:
        IwencaiError: 未配置 API Key / 网关请求失败 / 协议错误。
    """
    bounded_limit = max(1, min(limit, _MAX_ROWS))
    result = await query2data(query, limit=bounded_limit, rewrite_candidates=_relaxed_rewrites(query))

    datas = list(result["datas"])
    truncated = len(datas) > _MAX_ROWS
    kept = datas[:_MAX_ROWS]

    stocks: list[dict[str, Any]] = []
    for row in kept:
        code = _normalize_code(str(row.get("股票代码", "")))
        if not code:
            continue
        stock: dict[str, Any] = {
            "stockCode": code,
            "stockName": str(row.get("股票简称", "")),
        }
        for key, value in row.items():
            if key not in _FIXED_COLUMNS:
                stock[key] = value
        stocks.append(stock)

    return {
        "query": query,
        "total": int(result["code_count"] or len(stocks)),
        "truncated": truncated,
        "columns": _derive_columns(kept),
        "stocks": stocks,
        "chunks_info": result["chunks_info"],
    }
