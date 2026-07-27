"""SQLAlchemy ORM models."""

from app.models.ai_analysis_result import AiAnalysisResult
from app.models.auction import AuctionData
from app.models.capital_fund_flow_sector import SectorFundFlow
from app.models.collector_channel_config import CollectorChannelConfig
from app.models.collector_channel_data_type import CollectorChannelDataType
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask
from app.models.file_metadata import FileMetadata
from app.models.financial_balance_sheet import BalanceSheet
from app.models.financial_cash_flow_statement import CashFlowStatement
from app.models.financial_income_statement import IncomeStatement
from app.models.fund_flow import FundFlow
from app.models.fund_holding import FundHoldings
from app.models.industry_chain import (
    ChainAnalysisVersion,
    ChainCompanyMapping,
    ChainEdge,
    ChainNode,
)
from app.models.ipo_info import IpoInfo
from app.models.kline import KlineDaily, KlineMinute
from app.models.llm_config import LLMConfig
from app.models.mapping_stock_concept import MappingStockConcept
from app.models.market_amount import MarketAmount
from app.models.market_breadth import MarketBreadth
from app.models.news_announcement import NewsAnnouncement
from app.models.pool_limit_up_stock import LimitUpPool
from app.models.quote_auction_index import IndexAuction
from app.models.stock import StockBasic
from app.models.user import User
from app.models.watchlist import UserWatchlist

__all__ = [
    "AiAnalysisResult",
    "AuctionData",
    "BalanceSheet",
    "CashFlowStatement",
    "ChainAnalysisVersion",
    "ChainCompanyMapping",
    "ChainEdge",
    "ChainNode",
    "CollectorChannelConfig",
    "CollectorChannelDataType",
    "CollectorLog",
    "CollectorTask",
    "FileMetadata",
    "FundFlow",
    "FundHoldings",
    "IncomeStatement",
    "IndexAuction",
    "IpoInfo",
    "KlineDaily",
    "KlineMinute",
    "LimitUpPool",
    "LLMConfig",
    "MappingStockConcept",
    "MarketAmount",
    "MarketBreadth",
    "NewsAnnouncement",
    "SectorFundFlow",
    "StockBasic",
    "User",
    "UserWatchlist",
]
