"""契约测试：锁定各 spider 的 pipeline 组装与 Postgres upsert 参数。

作为 PostgresCollector 基类迁移的回归基线：迁移前后每个 spider 的
pipeline 步骤组合与 insert_many 调用参数必须保持一致。
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.exporters import PostgresExporter
from collector.core.pipelines import DeduplicateStep, NormalizeStep, ValidateStep
from collector.spiders.cninfo_disclosure import CninfoDisclosureCollector
from collector.spiders.cninfo_ipo import CninfoIpoCollector
from collector.spiders.cninfo_profile import CninfoProfileCollector
from collector.spiders.eastmoney_broken_pool import EastmoneyBrokenPoolCollector
from collector.spiders.eastmoney_dragon_list import EastMoneyDragonListCollector
from collector.spiders.eastmoney_financial_statement import (
    EastmoneyFinancialStatementCollector,
)
from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector
from collector.spiders.eastmoney_fund_holdings import EastMoneyFundHoldingsCollector
from collector.spiders.eastmoney_global_index import (
    EastmoneyGlobalIndexCollector,
)
from collector.spiders.eastmoney_limit_up_pool import EastMoneyLimitUpPoolCollector
from collector.spiders.eastmoney_sector_fund_flow import (
    EastMoneySectorFundFlowCollector,
)
from collector.spiders.exchange_market_amount import ExchangeMarketAmountCollector
from collector.spiders.sina_auction import SinaAuctionCollector
from collector.spiders.sina_index_kline import SinaIndexKlineCollector
from collector.spiders.sina_index_minute import SinaIndexMinuteCollector
from collector.spiders.sina_kline import SinaKlineCollector
from collector.spiders.sina_macro import SinaMacroCollector
from collector.spiders.sina_market_breadth import SinaMarketBreadthCollector
from collector.spiders.sina_news import SinaNewsCollector
from collector.spiders.sina_stock_list import SinaStockListCollector
from collector.spiders.ths_auction import ThsAuctionCollector
from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector
from collector.spiders.tushare_us_yield import TushareUsYieldCollector

_SECTOR_FUND_FLOW_UPDATE_COLUMNS = [
    "sector_name",
    "change_pct",
    "main_net_inflow",
    "super_large_net",
    "large_net",
    "medium_net",
    "small_net",
    "top_stock_code",
    "top_stock_name",
]

_LIMIT_UP_POOL_UPDATE_COLUMNS = [
    "stock_name",
    "change_pct",
    "latest_price",
    "turnover_rate",
    "sealed_amount",
    "first_seal_time",
    "last_seal_time",
    "broken_limit_count",
    "limit_status",
    "consecutive_boards",
    "industry",
    "source",
]

_MARKET_BREADTH_UPDATE_COLUMNS = [
    "up_count",
    "down_count",
    "flat_count",
    "limit_up_count",
    "limit_down_count",
    "snapshot_time",
    "source",
]

_STOCK_LIST_UPDATE_COLUMNS = [
    "stock_name",
    "full_name",
    "industry_level_1",
    "industry_level_2",
    "industry_level_3",
    "listing_date",
    "total_shares",
    "circulating_shares",
    "province",
]

_PROFILE_UPDATE_COLUMNS = [
    "stock_name",
    "full_name",
    "industry_level_1",
    "legal_person",
    "website",
    "registered_capital",
    "business_scope",
    "listing_date",
    "province",
    "city",
]


@dataclass(frozen=True)
class StoreContract:
    table: str
    conflict_key: str
    update_columns: list[str] | None = None
    update_skip_null: bool = False


@dataclass(frozen=True)
class SpiderContract:
    name: str
    cls: type
    config: dict[str, Any]
    store: StoreContract
    has_normalize: bool
    dedup_keys: list[str] | None = None
    required_fields: list[str] | None = None
    store_items: list[dict[str, Any]] = field(
        default_factory=lambda: [{"dummy": "value"}]
    )


CONTRACTS: list[SpiderContract] = [
    SpiderContract(
        name="sina_kline_daily",
        cls=SinaKlineCollector,
        config={"source": "sina", "data_type": "kline"},
        store=StoreContract(table="quote_kline_stock_daily", conflict_key="stock_code, trade_date"),
        has_normalize=False,
        dedup_keys=["stock_code", "trade_date"],
        required_fields=["stock_code", "trade_date", "close"],
    ),
    SpiderContract(
        name="sina_index_kline",
        cls=SinaIndexKlineCollector,
        config={"source": "sina", "data_type": "index_kline"},
        store=StoreContract(table="quote_kline_stock_daily", conflict_key="stock_code, trade_date"),
        has_normalize=False,
        dedup_keys=["stock_code", "trade_date"],
        required_fields=["stock_code", "trade_date", "close"],
    ),
    SpiderContract(
        name="sina_kline_minute",
        cls=SinaKlineCollector,
        config={"source": "sina", "data_type": "kline", "period": "minute"},
        store=StoreContract(table="quote_kline_stock_minute", conflict_key="stock_code, trade_date"),
        has_normalize=False,
        dedup_keys=["stock_code", "trade_date"],
        required_fields=["stock_code", "trade_date", "close"],
    ),
    SpiderContract(
        name="sina_auction",
        cls=SinaAuctionCollector,
        config={"source": "sina", "data_type": "auction"},
        store=StoreContract(
            table="quote_auction_stock",
            conflict_key="stock_code, trade_date, match_time",
        ),
        has_normalize=False,
        dedup_keys=["stock_code", "trade_date", "match_time"],
        required_fields=["stock_code", "trade_date", "match_time"],
    ),
    SpiderContract(
        name="ths_auction",
        cls=ThsAuctionCollector,
        config={"source": "ths", "data_type": "auction"},
        store=StoreContract(
            table="quote_auction_stock",
            conflict_key="stock_code, trade_date, match_time",
        ),
        has_normalize=False,
        dedup_keys=["stock_code", "trade_date", "match_time"],
        required_fields=["stock_code", "trade_date", "match_time"],
    ),
    SpiderContract(
        name="sina_news",
        cls=SinaNewsCollector,
        config={"source": "sina", "data_type": "news"},
        store=StoreContract(table="news_announcement", conflict_key="source_url"),
        has_normalize=False,
        dedup_keys=["source_url"],
        required_fields=["title", "source_url", "publish_date"],
    ),
    SpiderContract(
        name="sina_macro",
        cls=SinaMacroCollector,
        config={"source": "sina", "data_type": "macro"},
        store=StoreContract(
            table="macro_indicator",
            conflict_key="indicator_name, period_type, publish_date",
        ),
        has_normalize=True,
        dedup_keys=["indicator_name", "period_type", "publish_date"],
        required_fields=["indicator_name", "period_type", "publish_date"],
    ),
    SpiderContract(
        name="sina_stock_list",
        cls=SinaStockListCollector,
        config={"source": "sina", "data_type": "stock-list"},
        store=StoreContract(
            table="stock_basic",
            conflict_key="stock_code, market",
            update_columns=_STOCK_LIST_UPDATE_COLUMNS,
            update_skip_null=True,
        ),
        has_normalize=True,
        dedup_keys=None,
        required_fields=["stock_code", "stock_name", "market"],
    ),
    SpiderContract(
        name="eastmoney_sector_fund_flow",
        cls=EastMoneySectorFundFlowCollector,
        config={"source": "eastmoney", "data_type": "sector-fund-flow"},
        store=StoreContract(
            table="capital_fund_flow_sector",
            conflict_key="sector_code, sector_type, trade_date",
            update_columns=_SECTOR_FUND_FLOW_UPDATE_COLUMNS,
            update_skip_null=True,
        ),
        has_normalize=True,
        dedup_keys=["sector_code", "sector_type", "trade_date"],
        required_fields=["sector_code", "sector_name", "trade_date"],
    ),
    SpiderContract(
        name="ths_sector_fund_flow",
        cls=ThsSectorFundFlowCollector,
        config={"source": "ths", "data_type": "sector-fund-flow"},
        store=StoreContract(
            table="capital_fund_flow_sector",
            conflict_key="sector_code, sector_type, trade_date",
            update_columns=_SECTOR_FUND_FLOW_UPDATE_COLUMNS,
            update_skip_null=True,
        ),
        has_normalize=True,
        dedup_keys=["sector_code", "sector_type", "trade_date"],
        required_fields=["sector_code", "sector_name", "trade_date"],
    ),
    SpiderContract(
        name="eastmoney_fund_flow",
        cls=EastMoneyFundFlowCollector,
        config={"source": "eastmoney", "data_type": "fund-flow"},
        store=StoreContract(table="capital_fund_flow_stock", conflict_key="stock_code, trade_date"),
        has_normalize=False,
        dedup_keys=["stock_code", "trade_date"],
        required_fields=["stock_code", "trade_date"],
    ),
    SpiderContract(
        name="eastmoney_dragon_list",
        cls=EastMoneyDragonListCollector,
        config={"source": "eastmoney", "data_type": "dragon-list"},
        store=StoreContract(
            table="pool_dragon_tiger_stock",
            conflict_key="trade_date, stock_code, rank_reason",
        ),
        has_normalize=True,
        dedup_keys=["trade_date", "stock_code", "rank_reason"],
        required_fields=["trade_date", "stock_code"],
    ),
    SpiderContract(
        name="eastmoney_limit_up_pool",
        cls=EastMoneyLimitUpPoolCollector,
        config={"source": "eastmoney", "data_type": "limit-up-pool"},
        store=StoreContract(
            table="pool_limit_up_stock",
            conflict_key="trade_date, stock_code",
            update_columns=_LIMIT_UP_POOL_UPDATE_COLUMNS,
            update_skip_null=True,
        ),
        has_normalize=True,
        dedup_keys=["trade_date", "stock_code"],
        required_fields=["trade_date", "stock_code"],
    ),
    SpiderContract(
        name="sina_market_breadth",
        cls=SinaMarketBreadthCollector,
        config={"source": "sina", "data_type": "market-breadth"},
        store=StoreContract(
            table="market_breadth",
            conflict_key="trade_date",
            update_columns=_MARKET_BREADTH_UPDATE_COLUMNS,
        ),
        has_normalize=True,
        dedup_keys=["trade_date"],
        required_fields=["trade_date"],
    ),
    SpiderContract(
        name="eastmoney_fund_holdings",
        cls=EastMoneyFundHoldingsCollector,
        config={"source": "eastmoney", "data_type": "fund-holdings"},
        store=StoreContract(
            table="fund_holding", conflict_key="stock_code, report_date"
        ),
        has_normalize=True,
        dedup_keys=["stock_code", "report_date"],
        required_fields=["stock_code", "report_date"],
    ),
    SpiderContract(
        name="cninfo_profile",
        cls=CninfoProfileCollector,
        config={"source": "cninfo", "data_type": "profile"},
        store=StoreContract(
            table="stock_basic",
            conflict_key="stock_code, market",
            update_columns=_PROFILE_UPDATE_COLUMNS,
        ),
        has_normalize=True,
        dedup_keys=None,
        required_fields=["stock_code", "market"],
    ),
    SpiderContract(
        name="cninfo_ipo",
        cls=CninfoIpoCollector,
        config={"source": "cninfo", "data_type": "ipo"},
        store=StoreContract(
            table="ipo_info", conflict_key="stock_code, subscription_date"
        ),
        has_normalize=True,
        dedup_keys=["stock_code", "subscription_date"],
        required_fields=["stock_code", "subscription_date"],
    ),
    SpiderContract(
        name="cninfo_disclosure",
        cls=CninfoDisclosureCollector,
        config={"source": "cninfo", "data_type": "disclosure"},
        store=StoreContract(table="news_announcement", conflict_key="source_url"),
        has_normalize=True,
        dedup_keys=["source_url"],
        required_fields=["stock_code", "title", "publish_date"],
    ),
    SpiderContract(
        name="sina_index_minute",
        cls=SinaIndexMinuteCollector,
        config={"source": "sina", "data_type": "index-minute"},
        store=StoreContract(
            table="quote_kline_stock_minute", conflict_key="stock_code, trade_time"
        ),
        has_normalize=False,
        dedup_keys=["stock_code", "trade_time"],
        required_fields=["stock_code", "trade_time", "close"],
    ),
    SpiderContract(
        name="exchange_market_amount",
        cls=ExchangeMarketAmountCollector,
        config={"source": "exchange", "data_type": "market-amount"},
        store=StoreContract(
            table="market_amount",
            conflict_key="trade_date",
            update_columns=["amount", "source"],
            update_skip_null=True,
        ),
        has_normalize=True,
        dedup_keys=["trade_date"],
        required_fields=["trade_date", "amount"],
    ),
    SpiderContract(
        name="eastmoney_broken_pool",
        cls=EastmoneyBrokenPoolCollector,
        config={"source": "eastmoney", "data_type": "broken-pool"},
        store=StoreContract(
            table="market_breadth",
            conflict_key="trade_date",
            update_columns=["broken_limit_count"],
            update_skip_null=True,
        ),
        has_normalize=True,
        dedup_keys=["trade_date"],
        required_fields=["trade_date", "broken_limit_count"],
    ),
    SpiderContract(
        name="eastmoney_global_index",
        cls=EastmoneyGlobalIndexCollector,
        config={"source": "eastmoney", "data_type": "global_index"},
        store=StoreContract(
            table="quote_global_index_daily",
            conflict_key="index_code, trade_date",
            update_columns=[
                "open",
                "high",
                "low",
                "close",
                "change_pct",
                "volume",
                "amount",
                "source",
            ],
        ),
        has_normalize=False,
        dedup_keys=["index_code", "trade_date"],
        required_fields=["index_code", "trade_date", "close"],
    ),
    SpiderContract(
        name="tushare_us_yield",
        cls=TushareUsYieldCollector,
        config={"source": "tushare", "data_type": "global_index", "api_key": "token"},
        store=StoreContract(
            table="quote_global_index_daily",
            conflict_key="index_code, trade_date",
            update_columns=["close", "change_pct", "source"],
            update_skip_null=True,
        ),
        has_normalize=False,
        dedup_keys=["index_code", "trade_date"],
        required_fields=["index_code", "trade_date", "close"],
    ),
]


@pytest.mark.unit
class TestSpiderPipelineContract:
    @pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.name)
    def test_pipeline_steps(self, contract: SpiderContract) -> None:
        collector = contract.cls(contract.config)
        steps = collector.pipeline.steps

        idx = 0
        if contract.has_normalize:
            assert isinstance(steps[idx], NormalizeStep)
            idx += 1
        if contract.dedup_keys is not None:
            assert isinstance(steps[idx], DeduplicateStep)
            assert steps[idx].key_fields == contract.dedup_keys
            idx += 1
        if contract.required_fields is not None:
            assert isinstance(steps[idx], ValidateStep)
            assert steps[idx].required_fields == contract.required_fields
            idx += 1
        assert len(steps) == idx


@pytest.mark.unit
class TestSpiderStoreContract:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.name)
    async def test_store_upsert_args(self, contract: SpiderContract) -> None:
        collector = contract.cls(contract.config)
        pipeline = MagicMock()
        pipeline.process = AsyncMock(side_effect=lambda items: items)
        collector.pipeline = pipeline

        insert_many = AsyncMock(return_value=len(contract.store_items))
        with patch.object(PostgresExporter, "insert_many", insert_many):
            stored = await collector.store(list(contract.store_items))

        assert stored == len(contract.store_items)
        insert_many.assert_awaited_once()
        call = insert_many.await_args
        assert call.args[0] == contract.store.table
        assert call.args[1] == contract.store_items
        assert call.kwargs["conflict_key"] == contract.store.conflict_key
        if contract.store.update_columns is not None:
            assert call.kwargs["update_columns"] == contract.store.update_columns
        else:
            assert "update_columns" not in call.kwargs
        if contract.store.update_skip_null:
            assert call.kwargs["update_skip_null"] is True
        else:
            assert "update_skip_null" not in call.kwargs


@pytest.mark.unit
class TestFinancialStatementStoreContract:
    """eastmoney_financial_statement：单条数据拆写三张表（特例，不迁移基类）。"""

    @pytest.mark.asyncio
    async def test_store_splits_three_tables(self) -> None:
        import datetime

        collector = EastmoneyFinancialStatementCollector(
            {"source": "eastmoney", "data_type": "financial-statement"}
        )
        items = [
            {
                "stock_code": "000001",
                "report_date": datetime.date(2024, 3, 31),
                "report_type": "q1",
                "balance": {"total_assets": 1},
                "income": {"total_revenue": 2},
                "cash": {"cash_flow_from_operations": 3},
            }
        ]

        insert_many = AsyncMock(return_value=1)
        with patch.object(PostgresExporter, "insert_many", insert_many):
            stored = await collector.store(items)

        assert stored == 3
        tables = [call.args[0] for call in insert_many.await_args_list]
        assert tables == ["financial_balance_sheet", "financial_income_statement", "financial_cash_flow_statement"]
        for call in insert_many.await_args_list:
            assert call.kwargs["conflict_key"] == "stock_code, report_date"
