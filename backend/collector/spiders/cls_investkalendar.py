"""财联社投资日历采集器（www.cls.cn/api/calendar/web/list）。

2026-09 探针实测：真实端点由页面 chunk（pages/investkalendar）定位，
返回**今日起约 3 周的滚动前瞻窗口**（tradeDate 不改变窗口），每日拉取
一次即可覆盖滚动范围。WAF 与电报同源：Chrome 指纹 + 首访页面取
Cookie（复用 :mod:`collector.spiders.cls_telegraph` 的共享会话），签名
见 :mod:`collector.spiders.cls_sign`。

条目映射：``type=1`` 经济数据（economic 载荷）→ ``宏观``；
``type=2`` 事件会议（event 载荷）→ ``会议``；其余类型（新股/解禁为
cls 独立接口）与本轮无关，跳过。``calendar_time`` 为北京时间字符串
（00:00:00 表示时间未定），统一换算 aware UTC 后写入 ``calendar_event``。
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, ClassVar

import structlog

from app.core.clock import CN_TZ
from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.parsing import to_optional_str
from collector.spiders.cls_sign import build_cls_sign
from collector.spiders.cls_telegraph import shared_session, warm_session

logger = structlog.get_logger(__name__)

_KALENDAR_URL = "https://www.cls.cn/api/calendar/web/list"
_KALENDAR_PAGE_URL = "https://www.cls.cn/investkalendar"

_TYPE_TO_CATEGORY = {1: "宏观", 2: "会议"}

_TITLE_MAX_LEN = 300


def _parse_calendar_time(raw: str) -> datetime:
    """北京时间字符串 → aware UTC（00:00:00 表示时间未定，按零点处理）。"""
    naive = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=CN_TZ).astimezone(timezone.utc)


def _source_hash(event_time: datetime, title: str) -> str:
    """幂等键 md5(source|event_time|title)，与 calendar_event 表约定一致。"""
    text = f"cls|{event_time.isoformat()}|{title}"
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _map_item(row: dict[str, Any]) -> dict[str, Any] | None:
    """单条日历目 → calendar_event 行；非宏观/会议类型返回 None 跳过。"""
    category = _TYPE_TO_CATEGORY.get(row.get("type"))
    if category is None:
        return None
    title = to_optional_str(row.get("title"))
    if not title or not row.get("calendar_time"):
        return None
    title = title[:_TITLE_MAX_LEN]
    event_time = _parse_calendar_time(str(row["calendar_time"]))
    return {
        "event_time": event_time,
        "end_time": None,
        "title": title,
        "category": category,
        "impact_markets": None,
        "source": "cls",
        "source_url": _KALENDAR_PAGE_URL,
        "related_symbols": None,
        "source_hash": _source_hash(event_time, title),
    }


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """响应按日分组（data[].items[]），展平为条目列表。"""
    days = payload.get("data")
    if not isinstance(days, list):
        return []
    return [
        item
        for day in days
        if isinstance(day, dict) and isinstance(day.get("items"), list)
        for item in day["items"]
        if isinstance(item, dict)
    ]


def fetch_calendar(trade_date: int) -> list[dict[str, Any]]:
    """拉取投资日历前瞻窗口并映射为 calendar_event 行。

    Args:
        trade_date: Unix 秒（窗口固定，仅镜像官方客户端参数）。

    Returns:
        calendar_event 行列表。

    Raises:
        RuntimeError: 响应 code 非 200（含 WAF 拦截场景）。
    """
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "sv": "8.7.9",
        "tradeDate": str(trade_date),
    }
    params["sign"] = build_cls_sign(params)
    response = shared_session().get(_KALENDAR_URL, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"cls investkalendar code={payload.get('code')}")
    rows = [
        mapped
        for item in _extract_items(payload)
        if (mapped := _map_item(item)) is not None
    ]
    logger.info("cls_kalendar_fetched", trade_date=trade_date, rows=len(rows))
    return rows


class ClsInvestkalendarCollector(PostgresCollector):
    """财联社投资日历采集器，写入 calendar_event（source_hash 幂等 DO NOTHING）。

    cls 侧的预期值/公布值更新（consensus/actual）不在 calendar_event
    字段内，冲突时保留首见行即可。
    """

    table = "calendar_event"
    conflict_key = "source_hash"
    normalize = False
    key_fields: ClassVar[list[str]] = ["source_hash"]
    required_fields: ClassVar[list[str]] = [
        "source_hash",
        "event_time",
        "title",
        "category",
    ]

    async def collect(
        self,
        symbols: list[str] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        del symbols  # 日历为市场级数据，无标的维度
        return await run_in_thread(self._collect_sync)

    def _collect_sync(self) -> list[dict[str, Any]]:
        """预热 WAF 会话后拉取（worker 进程内 Cookie/sv 与电报任务共享）。"""
        warm_session()
        return fetch_calendar(int(datetime.now(timezone.utc).timestamp()))
