"""日本财务省日债收益率采集器（10Y，全量 CSV upsert）。

「国債金利情報」全量 CSV（1974 年起）：无鉴权无频控，但走 HTTP 压缩协商时
Content-Length 与解压后长度不一致，故强制 identity 编码并按 Content-Length
校验完整下载（连接中断导致的静默截断不易察觉）。基准日为和历记法
（S49.9.24 / H8.1.4 / R8.8.31），需换算公历。旧英文路径 jgbcve.csv 已 404。
"""

from datetime import date
from typing import ClassVar

import requests
import structlog

from app.core.constants import GLOBAL_INDEX_CODES
from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.http_client import DEFAULT_USER_AGENT
from collector.core.parsing import to_float

logger = structlog.get_logger(__name__)

_ALL_CSV_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
_TEN_YEAR_HEADER = "10年"
_ERA_OFFSETS = {"S": 1925, "H": 1988, "R": 2018}
_TIMEOUT_SECONDS = 60.0


def wareki_to_date(text: str) -> date:
    """和历基准日（如 ``R8.8.31``）转公历日期；未知年号抛 ValueError。"""
    parts = text.strip().split(".")
    if len(parts) != 3 or not parts[0] or parts[0][0] not in _ERA_OFFSETS:
        raise ValueError(f"invalid wareki date: {text!r}")
    era, year = parts[0][0], int(parts[0][1:])
    return date(_ERA_OFFSETS[era] + year, int(parts[1]), int(parts[2]))


def _download_all_csv() -> str:
    """下载全量 CSV 并按 Content-Length 校验完整性（截断防御）。"""
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Encoding": "identity"}
    head = requests.head(_ALL_CSV_URL, headers=headers, timeout=_TIMEOUT_SECONDS)
    head.raise_for_status()
    expected = int(head.headers["Content-Length"])
    response = requests.get(_ALL_CSV_URL, headers=headers, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    if len(response.content) != expected:
        raise OSError(
            f"jgbcm_all.csv truncated: got {len(response.content)} bytes, "
            f"expected {expected}"
        )
    return response.content.decode("shift_jis")


class MofJpyYieldCollector(PostgresCollector):
    """日债 10Y 收益率（全量历史 upsert），写入 quote_global_index_daily。"""

    table = "quote_global_index_daily"
    conflict_key = "index_code, trade_date"
    update_columns: ClassVar[list[str]] = [
        "open",
        "high",
        "low",
        "close",
        "change_pct",
        "volume",
        "amount",
        "source",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["index_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["index_code", "trade_date", "close"]

    async def collect(self, **kwargs: object) -> list[dict[str, object]]:
        index_code = next(
            code
            for code, meta in GLOBAL_INDEX_CODES.items()
            if meta["data_source"] == "mof"
        )
        return await run_in_thread(self._collect_sync, index_code)

    def _collect_sync(self, index_code: str) -> list[dict[str, object]]:
        text = _download_all_csv()
        rows = parse_jgbcm_all(text, index_code)
        logger.info(
            "mof_jpy_yield_parsed", index_code=index_code, rows=len(rows)
        )
        return rows


def parse_jgbcm_all(text: str, index_code: str) -> list[dict[str, object]]:
    """全量 CSV 文本 -> quote_global_index_daily 行（10Y 列，`-` 缺失日跳过）。"""
    lines = text.splitlines()
    try:
        header_index = next(i for i, ln in enumerate(lines) if ln.startswith("基準日"))
    except StopIteration as exc:
        raise ValueError("jgbcm_all.csv missing 基準日 header row") from exc

    columns = lines[header_index].split(",")
    try:
        ten_year_col = columns.index(_TEN_YEAR_HEADER)
    except ValueError as exc:
        raise ValueError(f"jgbcm_all.csv missing {_TEN_YEAR_HEADER!r} column") from exc

    rows: list[dict[str, object]] = []
    prev_close: float | None = None
    for line in lines[header_index + 1 :]:
        fields = line.split(",")
        if len(fields) <= ten_year_col:
            continue
        close = to_float(fields[ten_year_col])
        if close is None:
            continue
        trade_date = wareki_to_date(fields[0])
        change_pct = (
            round((close - prev_close) / prev_close * 100, 4) if prev_close else None
        )
        rows.append(
            {
                "index_code": index_code,
                "trade_date": trade_date,
                "open": None,
                "high": None,
                "low": None,
                "close": close,
                "change_pct": change_pct,
                "volume": None,
                "amount": None,
                "source": "mof",
            }
        )
        prev_close = close
    return rows
