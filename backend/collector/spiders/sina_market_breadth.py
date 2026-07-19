"""Sina market breadth collector via akshare.

抓取全市场 A 股快照（ak.stock_zh_a_spot，70 页串行约 28s），统计
涨跌家数与涨跌停家数，按交易日 upsert 到 ``market_breadth``。
stats 接口只读该表，不再在请求路径抓取数据源。

调度与 sina_quote 错峰（quote 用同接口，错开降低新浪封 IP 风险）。
"""

import contextlib
import io
from datetime import date, datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from collector.core.base import PostgresCollector

_UPDATE_COLUMNS = [
    "up_count",
    "down_count",
    "flat_count",
    "limit_up_count",
    "limit_down_count",
    "stat_time",
    "source",
]

_CN_TZ = ZoneInfo("Asia/Shanghai")


def limit_threshold(code: str, name: str) -> float:
    """各板块涨跌幅限制阈值（含 0.5pp 容差）。"""
    if code.startswith("bj"):
        return 29.5
    if code.startswith(("sz30", "sh68")):
        return 19.5
    if "ST" in name:
        return 4.8
    return 9.5


def count_breadth(df: Any) -> dict[str, Any]:
    """从全市场行情快照统计涨跌家数与涨跌停数（口径与同花顺一致）。

    涨跌停判定：涨跌幅达到板块阈值且收盘封板（最新价=最高/最低价），含 ST。
    """
    import pandas as pd  # type: ignore[import-untyped]

    df = df.dropna(subset=["涨跌幅"])
    up = int((df["涨跌幅"] > 0).sum())
    down = int((df["涨跌幅"] < 0).sum())
    flat = int((df["涨跌幅"] == 0).sum())

    thresholds = pd.Series(
        [
            limit_threshold(str(code), str(name))
            for code, name in zip(df["代码"], df["名称"], strict=True)
        ],
        index=df.index,
    )
    sealed_up = (df["涨跌幅"] >= thresholds) & (
        (df["最新价"] - df["最高"]).abs() < 1e-6
    )
    sealed_down = (df["涨跌幅"] <= -thresholds) & (
        (df["最新价"] - df["最低"]).abs() < 1e-6
    )

    stat_time = ""
    if "时间戳" in df.columns and len(df):
        stat_time = str(df["时间戳"].iloc[0])

    return {
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "limit_up_count": int(sealed_up.sum()),
        "limit_down_count": int(sealed_down.sum()),
        "stat_time": stat_time,
    }


class SinaMarketBreadthCollector(PostgresCollector):
    """新浪全市场涨跌统计采集器，写入 market_breadth（每交易日一行）。"""

    table = "market_breadth"
    conflict_key = "trade_date"
    update_columns: ClassVar[list[str]] = _UPDATE_COLUMNS
    key_fields: ClassVar[list[str]] = ["trade_date"]
    required_fields: ClassVar[list[str]] = ["trade_date"]

    async def collect(
        self, trade_date: date | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        # tqdm 进度条写 stderr，与 stdout 一并抑制保持日志干净
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            df = ak.stock_zh_a_spot()
        if df is None or df.empty:
            return []

        target = trade_date or datetime.now(_CN_TZ).date()
        return [{"trade_date": target, **count_breadth(df), "source": "sina"}]
