"""THS（同花顺）板块行情快照采集器：东财 push2 通道的免费 fallback 渠道。

行业走数据中心一览表（``stock_board_industry_summary_ths`` 单次请求 90
行业全量，含涨跌幅/总成交额/涨跌家数/领涨股，字段覆盖度与东财 clist 相当）；
概念板块无行情一览表，直接复用 ``quote_kline_sector_daily``（17:30
sector-kline 批次落库）派生当日涨跌幅与成交额，齐动维字段（涨跌家数/
领涨股）置空、由检测层按缺失跳过。因此 16:05 首跑窗口概念 K 线尚未落库
时仅覆盖行业，17:30 后重跑可补齐概念。

写入 ``quote_sector_daily``（source='ths'），与东财渠道同表同约定：
- 一览表总成交额单位亿元，×1e8 对齐 K 线表/东财渠道的元口径（量能维
  基线对比要求两渠道单位一致）；
- 板块收盘价不取一览表均价（成分均价语义，与东财指数点位不可比），置空
  由消费方容错；概念板块从 K 线取真实指数收盘价。
"""

from datetime import date
from typing import Any, ClassVar

import structlog

from app.core.database import AsyncSessionLocal
from app.repositories.market import kline_repository
from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.calendar import latest_trading_day
from collector.core.parsing import is_nan, to_float, to_int, to_optional_str

logger = structlog.get_logger(__name__)

# 一览表总成交额单位：亿元（K 线表与东财渠道均为元）
_AMOUNT_YI_TO_YUAN = 100_000_000.0


def _summary_pct(value: Any) -> float | None:
    """一览表涨跌幅：数值直取，带 % 字符串剥壳。"""
    if value is None or is_nan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().rstrip("%"))
    except ValueError:
        return None


def transform_summary_row(
    row: dict[str, Any], sector_code: str | None, trade_date: date
) -> dict[str, Any] | None:
    """一览表行 -> quote_sector_daily 行（industry）；板块名缺失跳过。"""
    sector_name = to_optional_str(row.get("板块"))
    if not sector_name:
        return None
    amount_yi = to_float(row.get("总成交额"))
    leader = to_optional_str(row.get("领涨股"))
    return {
        "sector_type": "industry",
        "sector_code": sector_code or sector_name,
        "sector_name": sector_name,
        "trade_date": trade_date,
        "close": None,
        "change_pct": _summary_pct(row.get("涨跌幅")),
        "amount": None if amount_yi is None else amount_yi * _AMOUNT_YI_TO_YUAN,
        "turnover_rate": None,
        "up_count": to_int(row.get("上涨家数")),
        "down_count": to_int(row.get("下跌家数")),
        "leader_stock_name": None if leader == "-" else leader,
        "source": "ths",
    }


def concept_row_from_bars(
    bars: list[Any], trade_date: date
) -> dict[str, Any] | None:
    """升序板块日 K -> quote_sector_daily 行（concept）。

    当日无 bar（板块停更/未落库）返回 None；无前一交易日 bar 时涨跌幅
    置 None（价格维跳过，量能维仍可用）。
    """
    idx = next((i for i, bar in enumerate(bars) if bar.trade_date == trade_date), None)
    if idx is None:
        return None
    bar = bars[idx]
    if bar.close is None:
        return None
    prev = bars[idx - 1] if idx > 0 else None
    change_pct: float | None = None
    if prev is not None and prev.close is not None:
        change_pct = (float(bar.close) / float(prev.close) - 1) * 100
    return {
        "sector_type": "concept",
        "sector_code": bar.sector_code or bar.sector_name,
        "sector_name": bar.sector_name,
        "trade_date": trade_date,
        "close": float(bar.close),
        "change_pct": change_pct,
        "amount": float(bar.amount) if bar.amount is not None else None,
        "turnover_rate": None,
        "up_count": None,
        "down_count": None,
        "leader_stock_name": None,
        "source": "ths",
    }


class ThsSectorQuoteCollector(PostgresCollector):
    """同花顺板块行情快照采集器，写入 quote_sector_daily。"""

    table = "quote_sector_daily"
    conflict_key = "sector_type, sector_code, trade_date"
    update_columns: ClassVar[list[str]] = [
        "sector_name",
        "close",
        "change_pct",
        "amount",
        "turnover_rate",
        "up_count",
        "down_count",
        "leader_stock_name",
        "source",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["sector_type", "sector_code", "trade_date"]
    required_fields: ClassVar[list[str]] = [
        "sector_type",
        "sector_code",
        "sector_name",
        "trade_date",
    ]

    async def collect(
        self, trade_date: date | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        target = trade_date or latest_trading_day()
        rows: list[dict[str, Any]] = await run_in_thread(
            self._collect_industry_sync, target
        )
        rows.extend(await self._collect_concept_from_kline(target))
        if not rows:
            raise RuntimeError("同花顺板块快照采集为空：行业一览表无数据")
        return rows

    def _collect_industry_sync(self, trade_date: date) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        summary = ak.stock_board_industry_summary_ths()
        if summary is None or summary.empty:
            return []
        code_map = self._industry_code_map(ak)
        rows = [
            transformed
            for record in summary.to_dict(orient="records")
            if (
                transformed := transform_summary_row(
                    record, code_map.get(to_optional_str(record.get("板块")) or ""),
                    trade_date,
                )
            )
        ]
        logger.info(
            "ths_sector_quote_industry_fetched",
            listed=len(summary),
            rows=len(rows),
        )
        return rows

    @staticmethod
    def _industry_code_map(ak: Any) -> dict[str, str]:
        """板块名 -> 881xxx 代码；清单失败不阻塞主数据（退化为名称作代码）。"""
        try:
            df = ak.stock_board_industry_name_ths()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ths_sector_quote_code_list_failed", error=repr(exc))
            return {}
        if df is None or df.empty:
            return {}
        return {
            name: code
            for record in df.to_dict(orient="records")
            if (name := to_optional_str(record.get("name")))
            and (code := to_optional_str(record.get("code")))
        }

    async def _collect_concept_from_kline(self, trade_date: date) -> list[dict[str, Any]]:
        """从 THS 板块日 K 表派生概念板块快照行（17:30 批次后可用）。"""
        async with AsyncSessionLocal() as session:
            concept_names = [
                name
                for sector_type, name in await kline_repository.list_ths_sector_names(
                    session
                )
                if sector_type == "concept"
            ]
            bars_map = await kline_repository.map_sector_kline_by_name(
                session, concept_names
            )
        rows = [
            transformed
            for bars in bars_map.values()
            if (transformed := concept_row_from_bars(bars, trade_date))
        ]
        logger.info(
            "ths_sector_quote_concept_derived",
            boards=len(bars_map),
            rows=len(rows),
        )
        return rows
