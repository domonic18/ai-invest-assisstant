"""Sina macro economic indicator collector via akshare."""

import re
from datetime import date, datetime
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import to_float, to_optional_str


class SinaMacroCollector(PostgresCollector):
    """新浪财经宏观经济指标采集器，写入 macro_indicator。"""

    table = "macro_indicator"
    conflict_key = "indicator_name, period_type, publish_date"
    key_fields: ClassVar[list[str]] = ["indicator_name", "period_type", "publish_date"]
    required_fields: ClassVar[list[str]] = [
        "indicator_name",
        "period_type",
        "publish_date",
    ]

    async def collect(
        self, indicators: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        indicators = indicators or ["cpi", "pmi", "gdp"]
        raw: list[dict[str, Any]] = []
        for name in indicators:
            try:
                if name == "cpi":
                    df = ak.macro_china_cpi()
                    raw.extend(_parse_cpi(df))
                elif name == "pmi":
                    df = ak.macro_china_pmi()
                    raw.extend(_parse_pmi(df))
                elif name == "gdp":
                    df = ak.macro_china_gdp()
                    raw.extend(_parse_gdp(df))
                else:
                    continue
            except Exception:  # noqa: BLE001
                continue
        return raw


def _parse_cpi(df: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        period = to_optional_str(_find_col(row, ["月份", "月"]))
        publish_date = _parse_month_period(period)
        value = to_float(_find_col(row, ["全国-当月", "当月", "全国"]))
        yoy = to_float(_find_col(row, ["全国-同比增长", "同比增长"]))
        mom = to_float(_find_col(row, ["全国-环比增长", "环比增长"]))
        rows.append(
            {
                "indicator_name": "cpi",
                "period_type": "month",
                "publish_date": publish_date,
                "value": value,
                "value_yoy": yoy,
                "value_mom": mom,
                "source": "sina",
            }
        )
    return rows


def _parse_pmi(df: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        period = to_optional_str(_find_col(row, ["月份", "月"]))
        publish_date = _parse_month_period(period)
        value = to_float(_find_col(row, ["制造业-指数", "制造业采购经理指数", "指数"]))
        rows.append(
            {
                "indicator_name": "pmi",
                "period_type": "month",
                "publish_date": publish_date,
                "value": value,
                "value_yoy": None,
                "value_mom": None,
                "source": "sina",
            }
        )
    return rows


def _parse_gdp(df: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        period = to_optional_str(_find_col(row, ["季度"]))
        publish_date = _parse_quarter_period(period)
        value = to_float(_find_col(row, ["国内生产总值-绝对值", "GDP-绝对值", "绝对值"]))
        yoy = to_float(
            _find_col(row, ["国内生产总值-同比增长", "GDP-同比增长", "同比增长"])
        )
        rows.append(
            {
                "indicator_name": "gdp",
                "period_type": "quarter",
                "publish_date": publish_date,
                "value": value,
                "value_yoy": yoy,
                "value_mom": None,
                "source": "sina",
            }
        )
    return rows


def _find_col(row: Any, candidates: list[str]) -> Any:
    for col in candidates:
        try:
            return row[col]
        except KeyError:
            continue
    return None


def _parse_month_period(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    # e.g. "2024年06月" / "2024年06月份"
    match = re.match(r"^(\d{4})[年/-](\d{1,2})月份?$", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    for fmt in ("%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_quarter_period(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    match = re.match(r"^(\d{4})年第?(\d)季度?$", text)
    if match:
        year = int(match.group(1))
        quarter = int(match.group(2))
        month = (quarter - 1) * 3 + 1
        return date(year, month, 1)
    return None
