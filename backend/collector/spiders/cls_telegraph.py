"""财联社电报采集器（www.cls.cn/v1/roll/get_roll_list）。

写入 ``news_telegraph``，``cls_msg_id`` 幂等 append-only（DO NOTHING）。
WAF 要求 Chrome TLS 指纹 + 首访 ``/telegraph`` 取 Cookie；会话为模块级
单例自持，``warm_session()`` 在首次调用与失败后由调用方（backfill 任务 /
stream 驻留进程）触发重预热。签名见 :mod:`collector.spiders.cls_sign`。
"""

import json
import threading
from datetime import datetime, timezone
from typing import Any, ClassVar

import structlog
from curl_cffi.requests import Response as CffiResponse
from curl_cffi.requests import Session as CffiSession

from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.parsing import to_optional_str
from collector.spiders.cls_sign import DEFAULT_SV, build_cls_sign, extract_sv

logger = structlog.get_logger(__name__)

_TELEGRAPH_PAGE_URL = "https://www.cls.cn/telegraph"
_ROLL_LIST_URL = "https://www.cls.cn/v1/roll/get_roll_list"

_LEVEL_TO_IMPORTANCE = {"A": 3, "B": 2, "C": 1}

_session_lock = threading.Lock()
_session: CffiSession | None = None
_sv = DEFAULT_SV


def shared_session() -> CffiSession:
    """cls 站点共享会话（Chrome 指纹，WAF Cookie 跨任务复用）。"""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = CffiSession(impersonate="chrome")
    return _session


def warm_session() -> str:
    """首访电报页取 WAF Cookie 并刷新 sv 缓存，返回当前 sv。

    失败时抛出原始异常，由调用方决定退避重试节奏。
    """
    global _sv
    response = shared_session().get(_TELEGRAPH_PAGE_URL, timeout=15)
    response.raise_for_status()
    _sv = extract_sv(response.text)
    logger.info("cls_session_warmed", sv=_sv)
    return _sv


def reset_session() -> None:
    """丢弃会话（Cookie 失效/被 WAF 拦截时由调用方触发，下次请求前重预热）。"""
    global _session, _sv
    with _session_lock:
        _session = None
        _sv = DEFAULT_SV


def _level_to_importance(level: Any) -> int | None:
    """cls level → importance：数字原值保留；A/B/C 等级映射 3/2/1。"""
    if level is None:
        return None
    if isinstance(level, int):
        return level
    text = str(level).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    return _LEVEL_TO_IMPORTANCE.get(text.upper())


def _stock_codes(stock_list: Any) -> list[str] | None:
    """cls stock_list → 代码数组（元素形如 {"StockID": "sh600519", ...}）。"""
    if not isinstance(stock_list, list):
        return None
    codes = [
        str(item.get("StockID"))
        for item in stock_list
        if isinstance(item, dict) and item.get("StockID")
    ]
    return codes or None


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    rows = data.get("roll_data") or data.get("rolling_data") or []
    return rows if isinstance(rows, list) else []


def fetch_page(last_time: int = 0, rn: int = 20) -> list[dict[str, Any]]:
    """拉取一页电报并映射为 news_telegraph 行。

    Args:
        last_time: 翻页游标（Unix 秒，排他，向旧翻页）；0 表示取最新一页。
        rn: 每页条数（探针实测上限约 20）。

    Returns:
        news_telegraph 行列表（publish_time 为 aware UTC）。

    Raises:
        RuntimeError: 响应 errno 非 0（含 WAF 拦截场景）。
    """
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "sv": _sv,
        "refresh_type": "1",
        "rn": str(rn),
        "last_time": str(last_time),
    }
    params["sign"] = build_cls_sign(params)
    response: CffiResponse = shared_session().get(
        _ROLL_LIST_URL, params=params, timeout=15
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errno") != 0:
        raise RuntimeError(f"cls roll_list errno={payload.get('errno')}")
    logger.info("cls_page_fetched", last_time=last_time, rn=rn)
    return [_map_item(row) for row in _extract_rows(payload) if row.get("id")]


def _map_item(row: dict[str, Any]) -> dict[str, Any]:
    extra = {
        key: row[key]
        for key in ("brief", "shareurl", "modified_time", "subjects")
        if row.get(key)
    }
    return {
        "cls_msg_id": int(row["id"]),
        "title": to_optional_str(row.get("title")),
        "content": to_optional_str(row.get("content")),
        "category": to_optional_str(row.get("type")),
        "importance": _level_to_importance(row.get("level")),
        "shared": row.get("shared") if isinstance(row.get("shared"), int) else None,
        "stock_codes": _stock_codes(row.get("stock_list")),
        # PostgresExporter 直通 asyncpg，JSONB 须自行序列化为字符串
        "extra": json.dumps(extra, ensure_ascii=False) if extra else None,
        # ctime 为 Unix 秒，直接换算 aware UTC
        "publish_time": datetime.fromtimestamp(int(row["ctime"]), tz=timezone.utc),
    }


class ClsTelegraphCollector(PostgresCollector):
    """财联社电报采集器，写入 news_telegraph（cls_msg_id 幂等 DO NOTHING）。"""

    table = "news_telegraph"
    conflict_key = "cls_msg_id"
    normalize = False
    key_fields: ClassVar[list[str]] = ["cls_msg_id"]
    required_fields: ClassVar[list[str]] = ["cls_msg_id", "publish_time"]

    async def collect(
        self,
        symbols: list[str] | None = None,
        rn: int = 20,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        del symbols  # 电报为市场级数据，无标的维度
        return await run_in_thread(fetch_page, 0, rn)
