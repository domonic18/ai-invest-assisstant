"""CME FedWatch 加息概率采集器（QuikStrike 官方概率表直采）。

CME 工具页内嵌 QuikStrike WebForms 应用（Akamai 按 TLS 指纹拦截 httpx，
须 curl_cffi Chrome 指纹）。三步同一 cookie 会话：入口页取
#global_instanceCache 会话参数 → Current 标签页取「Data as of … CT」
时间戳与「<low>-<high> (Current)」当前目标区间 → 隐藏字段 postback 切
Probabilities 标签，解析 Conditional Meeting Probabilities 表（行=FOMC
会议日美式日期，列=目标区间 bps，值=落位概率%）。每日 3 请求无频控压力。
快照元数据写 fed_watch_snapshot，概率行写 fed_watch_probability（双表）。
"""

import html as html_module
import re
from datetime import date, datetime, timezone
from typing import Any, ClassVar
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector, get_engine
from collector.core.exporters import PostgresExporter
from collector.core.http_client import chrome_get, chrome_post

logger = structlog.get_logger(__name__)

_TOOL_PAGE_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
_ENTRY_URL = "https://cmegroup-tools.quikstrike.net/User/QuikStrikeTools.aspx"
_VIEW_URL = "https://cmegroup-tools.quikstrike.net/User/QuikStrikeView.aspx"
_VIEW_PARAMS = {"viewitemid": "IntegratedFedWatchTool", "userId": "lwolf"}
_PTREE_TARGET = "ctl00$MainContent$ucViewControl_IntegratedFedWatchTool$lbPTree"
_CHICAGO_TZ = ZoneInfo("America/Chicago")
_PROB_TABLE_TITLE = "Conditional Meeting Probabilities"
# 写路径哨兵：官网概率四舍五入到 0.1%，FedWatch 常年覆盖 8 场以上会议
_PROB_SUM_TOLERANCE = 0.5
_MIN_MEETINGS = 4
_RANGE_CELL = re.compile(r"(\d{3})-(\d{3})\s*\(Current\)")
_DATA_AS_OF = re.compile(
    r"Data as of\s+(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\s+\d{2}:\d{2}:\d{2})\s+CT"
)
_MEETING_DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_PERCENT_CELL = re.compile(r"([\d.]+)%")


def extract_session_cache(page_html: str) -> str:
    """入口页 ``#global_instanceCache`` 的会话参数（insid&qsid）。"""
    match = re.search(
        r'id="global_instanceCache"[^>]*value="([^"]+)"', page_html
    )
    if not match:
        raise ValueError("QuikStrike entry page missing global_instanceCache")
    return html_module.unescape(match.group(1))


def parse_data_as_at(page_html: str) -> tuple[datetime, date]:
    """Current 页「Data as of 7 Sep 2026 06:37:58 CT」→ (aware UTC, CT 日期)。"""
    match = _DATA_AS_OF.search(page_html)
    if not match:
        raise ValueError("FedWatch page missing 'Data as of' timestamp")
    local = datetime.strptime(match.group(1), "%d %b %Y %H:%M:%S").replace(
        tzinfo=_CHICAGO_TZ
    )
    return local.astimezone(timezone.utc), local.date()


def parse_current_range(page_html: str) -> tuple[int, int]:
    """Current 页「350-375 (Current)」→ 当前目标区间 (low, high) bps。"""
    match = _RANGE_CELL.search(page_html)
    if not match:
        raise ValueError("FedWatch page missing current target range marker")
    return int(match.group(1)), int(match.group(2))


def extract_hidden_fields(page_html: str) -> dict[str, str]:
    """收集隐藏 input 的 name/value（WebForms postback 载荷）。"""
    payload: dict[str, str] = {}
    for tag in re.finditer(r'<input[^>]*type="hidden"[^>]*>', page_html):
        name = re.search(r'name="([^"]+)"', tag.group(0))
        if not name:
            continue
        value = re.search(r'value="([^"]*)"', tag.group(0))
        payload[name.group(1)] = html_module.unescape(value.group(1)) if value else ""
    return payload


def _clean_cell(cell: str) -> str:
    return re.sub(r"<[^>]+>|&nbsp;|\s+", " ", cell).strip()


def parse_probabilities(page_html: str) -> list[dict[str, Any]]:
    """PTree 页概率表 → 行；空 cell 跳过，0.0% 全量保留（0 值有语义）。"""
    title_at = page_html.find(_PROB_TABLE_TITLE)
    if title_at < 0:
        raise ValueError(f"FedWatch page missing {_PROB_TABLE_TITLE!r} table")
    start = page_html.rfind("<table", 0, title_at)
    table_html = page_html[start : page_html.find("</table>", title_at) + 8]

    ranges: list[tuple[int, int]] | None = None
    rows: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        cells = [
            _clean_cell(c)
            for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.S)
        ]
        if not cells:
            continue
        if cells[0] == "Meeting Date":
            ranges = [
                (int(m.group(1)), int(m.group(2)))
                for m in (
                    re.fullmatch(r"(\d{3})-(\d{3})", c) for c in cells[1:]
                )
                if m
            ]
            continue
        if ranges and _MEETING_DATE.fullmatch(cells[0]):
            meeting_date = datetime.strptime(cells[0], "%m/%d/%Y").date()
            for (low, high), cell in zip(ranges, cells[1:]):
                percent = _PERCENT_CELL.fullmatch(cell)
                if not percent:
                    continue
                rows.append(
                    {
                        "meeting_date": meeting_date,
                        "range_low": low,
                        "range_high": high,
                        "probability": float(percent.group(1)),
                    }
                )
    if ranges is None:
        raise ValueError("FedWatch probabilities table missing 'Meeting Date' header")
    return rows


def validate_probabilities(rows: list[dict[str, Any]]) -> None:
    """写路径哨兵：拦站点微调产出的坏数据（列错位/表截断）。

    每会议区间概率和应恒为 ~100；会议数骤降意味着表被截断或解析
    错位——此时抛错转 FAILED 走死信告警，而不是静默落库坏数据。
    """
    by_meeting: dict[Any, list[float]] = {}
    for row in rows:
        by_meeting.setdefault(row["meeting_date"], []).append(row["probability"])
    if len(by_meeting) < _MIN_MEETINGS:
        raise ValueError(
            f"FedWatch meetings {len(by_meeting)} < {_MIN_MEETINGS}: table truncated?"
        )
    for meeting_date, probs in by_meeting.items():
        total = sum(probs)
        if abs(total - 100) > _PROB_SUM_TOLERANCE:
            raise ValueError(
                f"FedWatch probabilities of {meeting_date} sum to "
                f"{total:.1f}% (expect ~100): column misaligned?"
            )


class CmeFedWatchCollector(PostgresCollector):
    """FedWatch 官方概率直采，写 fed_watch_snapshot + fed_watch_probability。"""

    table = "fed_watch_probability"
    conflict_key = "as_of_date, meeting_date, range_low"
    update_columns: ClassVar[list[str]] = ["range_high", "probability"]
    normalize = False
    key_fields: ClassVar[list[str]] = ["as_of_date", "meeting_date", "range_low"]
    required_fields: ClassVar[list[str]] = [
        "as_of_date",
        "meeting_date",
        "range_low",
        "range_high",
        "probability",
    ]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._snapshot: dict[str, Any] | None = None

    async def collect(self, **kwargs: object) -> list[dict[str, Any]]:
        return await run_in_thread(self._collect_sync)

    def _collect_sync(self) -> list[dict[str, Any]]:
        entry_url = f"{_ENTRY_URL}?{urlencode(_VIEW_PARAMS)}"
        entry_html = chrome_get(entry_url, headers={"Referer": _TOOL_PAGE_URL}).text
        view_url = f"{_VIEW_URL}?{urlencode(_VIEW_PARAMS)}&{extract_session_cache(entry_html)}"
        current_html = chrome_get(view_url, headers={"Referer": entry_url}).text
        data_as_at, as_of_date = parse_data_as_at(current_html)
        range_low, range_high = parse_current_range(current_html)

        payload = extract_hidden_fields(current_html)
        payload["__EVENTTARGET"] = _PTREE_TARGET
        payload["__EVENTARGUMENT"] = ""
        tree_html = chrome_post(view_url, data=payload, headers={"Referer": view_url}).text

        rows = parse_probabilities(tree_html)
        if not rows:
            raise ValueError("FedWatch probabilities table empty after postback")
        validate_probabilities(rows)
        self._snapshot = {
            "as_of_date": as_of_date,
            "data_as_at": data_as_at,
            "current_range_low": range_low,
            "current_range_high": range_high,
        }
        for row in rows:
            row["as_of_date"] = as_of_date
        logger.info(
            "cme_fed_watch_parsed",
            as_of=as_of_date.isoformat(),
            meetings=len({r["meeting_date"] for r in rows}),
            rows=len(rows),
        )
        return rows

    async def store(self, items: list[dict[str, Any]]) -> int:
        """双表写入：先 upsert 快照元数据，再 upsert 概率行。"""
        cleaned = await self.pipeline.process(items)
        if not cleaned or self._snapshot is None:
            return 0
        session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
        async with session_maker() as session:
            exporter = PostgresExporter(session)
            await exporter.insert_many(
                "fed_watch_snapshot",
                [self._snapshot],
                conflict_key="as_of_date",
                update_columns=[
                    "data_as_at",
                    "current_range_low",
                    "current_range_high",
                ],
            )
            return await exporter.insert_many(
                self.table,
                cleaned,
                conflict_key=self.conflict_key,
                update_columns=self.update_columns,
            )
