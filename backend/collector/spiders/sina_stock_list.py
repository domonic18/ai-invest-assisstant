"""A-share stock list sync collector via akshare.

Fetches the full A-share code/name list and enriches it with:

- exchange-published details (full name, listing date, share counts, province)
  from the SSE/SZSE/BSE official lists
- the Shenwan (申万) three-level industry classification resolved from index
  constituents (L3 first, falling back to L2 then L1 for unmapped stocks)

Results are upserted into ``stock_basic``.  Richer profile fields (legal
person, registered capital, business scope, ...) stay owned by the
company-profile task; ``update_skip_null`` ensures this collector never
overwrites existing values with NULLs.
"""

import logging
import time
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from collector.base import BaseCollector
from collector.exporters import PostgresExporter
from collector.pipelines import DataPipeline, NormalizeStep, ValidateStep
from collector.settings import settings

logger = logging.getLogger(__name__)

_UPDATE_COLUMNS = [
    "stock_name",
    "full_name",
    "industry_l1",
    "industry_l2",
    "industry_l3",
    "listing_date",
    "total_shares",
    "circulating_shares",
    "province",
]


class SinaStockListCollector(BaseCollector):
    """全市场 A 股股票列表同步采集器，回写 stock_basic。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                ValidateStep(required_fields=["stock_code", "stock_name", "market"]),
            ]
        )
        self._engine = create_async_engine(settings.database_url)
        self._sw_request_delay = float(config.get("sw_request_delay", 0.2))

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_info_a_code_name()
        if df.empty:
            return []

        requested = None
        if symbols:
            requested = {_clean_code(symbol) for symbol in symbols}

        codes: list[str] = []
        names: dict[str, str] = {}
        for _, row in df.iterrows():
            code = str(row["code"]).strip().zfill(6)
            if requested and code not in requested:
                continue
            codes.append(code)
            names[code] = str(row["name"]).strip()

        details = _fetch_exchange_details(ak)
        industries = _fetch_sw_industry_map(
            ak, codes, delay=self._sw_request_delay
        )

        raw: list[dict[str, Any]] = []
        for code in codes:
            item: dict[str, Any] = {
                "stock_code": code,
                "stock_name": names[code],
                "market": _guess_market(code),
            }
            item.update(details.get(code, {}))
            item.update(industries.get(code, {}))
            raw.append(item)
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "stock_name": str(raw["stock_name"]),
            "market": str(raw["market"]),
            "full_name": raw.get("full_name"),
            "industry_l1": raw.get("industry_l1"),
            "industry_l2": raw.get("industry_l2"),
            "industry_l3": raw.get("industry_l3"),
            "listing_date": raw.get("listing_date"),
            "total_shares": raw.get("total_shares"),
            "circulating_shares": raw.get("circulating_shares"),
            "province": raw.get("province"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("stock_code") and item.get("stock_name") and item.get("market")
        )

    async def store(self, items: list[dict[str, Any]]) -> int:
        cleaned = await self.pipeline.process(items)
        if not cleaned:
            return 0

        session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_maker() as session:
            exporter = PostgresExporter(session)
            count = await exporter.insert_many(
                "stock_basic",
                cleaned,
                conflict_key="stock_code, market",
                update_columns=_UPDATE_COLUMNS,
                update_skip_null=True,
            )
        await self._engine.dispose()
        return count


def _fetch_exchange_details(ak: Any) -> dict[str, dict[str, Any]]:
    """Merge listing details from the SSE/SZSE/BSE official stock lists."""
    details: dict[str, dict[str, Any]] = {}

    try:
        sh_df = ak.stock_info_sh_name_code()
        for _, row in sh_df.iterrows():
            code = str(row["证券代码"]).strip().zfill(6)
            details[code] = {
                "full_name": _to_str(row.get("公司全称")),
                "listing_date": _parse_date(row.get("上市日期")),
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch SSE stock list failed: %s", exc)

    try:
        sz_df = ak.stock_info_sz_name_code()
        for _, row in sz_df.iterrows():
            code = str(row["A股代码"]).strip().zfill(6)
            details[code] = {
                "listing_date": _parse_date(row.get("A股上市日期")),
                "total_shares": _parse_int(row.get("A股总股本")),
                "circulating_shares": _parse_int(row.get("A股流通股本")),
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch SZSE stock list failed: %s", exc)

    try:
        bj_df = ak.stock_info_bj_name_code()
        for _, row in bj_df.iterrows():
            code = str(row["证券代码"]).strip().zfill(6)
            details[code] = {
                "listing_date": _parse_date(row.get("上市日期")),
                "total_shares": _parse_int(row.get("总股本")),
                "circulating_shares": _parse_int(row.get("流通股本")),
                "province": _to_str(row.get("地区")),
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch BSE stock list failed: %s", exc)

    return details


def _fetch_sw_industry_map(
    ak: Any,
    stock_codes: list[str],
    delay: float = 0.2,
) -> dict[str, dict[str, Any]]:
    """Map stock codes to the Shenwan L1/L2/L3 industry classification.

    Constituents are fetched per index, most detailed level first; stocks not
    yet mapped fall back to L2 and then L1 indices.
    """
    try:
        l1_info = ak.sw_index_first_info()
        l2_info = ak.sw_index_second_info()
        l3_info = ak.sw_index_third_info()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch SW index info failed: %s", exc)
        return {}

    l2_to_l1 = dict(zip(l2_info["行业名称"], l2_info["上级行业"], strict=False))
    l3_to_l2 = dict(zip(l3_info["行业名称"], l3_info["上级行业"], strict=False))

    mapping: dict[str, dict[str, Any]] = {}
    pending = set(stock_codes)

    def consume(cons_df: Any, l1: str | None, l2: str | None, l3: str | None) -> None:
        for value in cons_df["证券代码"]:
            code = str(value).strip().zfill(6)
            if code in pending and code not in mapping:
                mapping[code] = {
                    "industry_l1": l1,
                    "industry_l2": l2,
                    "industry_l3": l3,
                }
                pending.discard(code)

    levels = [
        (
            l3_info,
            lambda name: (l2_to_l1.get(l3_to_l2.get(name)), l3_to_l2.get(name), name),
        ),
        (l2_info, lambda name: (l2_to_l1.get(name), name, None)),
        (l1_info, lambda name: (name, None, None)),
    ]
    for info, resolve in levels:
        for index_code, index_name in zip(
            info["行业代码"], info["行业名称"], strict=False
        ):
            if not pending:
                return mapping
            cons = _fetch_sw_components(ak, index_code)
            if cons is None:
                continue
            l1, l2, l3 = resolve(index_name)
            consume(cons, l1, l2, l3)
            time.sleep(delay)

    return mapping


def _fetch_sw_components(ak: Any, index_code: str) -> Any | None:
    """Fetch index constituents, tolerating per-index failures."""
    symbol = str(index_code).split(".")[0]
    try:
        return ak.index_component_sw(symbol=symbol)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch SW components for %s failed: %s", symbol, exc)
        return None


def _clean_code(symbol: str) -> str:
    return symbol.lstrip("sh").lstrip("sz").lstrip("bj").strip()


def _guess_market(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith(("4", "8", "920")):
        return "bj"
    return "sz"


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
