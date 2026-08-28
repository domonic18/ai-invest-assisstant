"""行情数据业务服务。"""

from app.services.market import (  # noqa: F401 — 子模块 re-export，供子域内互引
    financial_service,
    hotspot_service,
    index_quotation_service,
    index_technical_service,
    limit_pool_service,
    market_stats_service,
    sector_fund_flow_service,
    sector_service,
    trade_calendar_service,
)
from app.services.market.auction_service import (
    get_auction_by_code,
    get_index_auction_trend,
)
from app.services.market.fund_flow_service import get_fund_flow
from app.services.market.intraday_service import get_stock_intraday
from app.services.market.kline_service import get_kline_by_code, get_stock_kline
from app.services.market.stock_service import (
    get_stock_by_code,
    get_stock_quote,
    get_stock_sectors,
    search_stocks,
)

__all__ = [
    "get_auction_by_code",
    "get_fund_flow",
    "get_index_auction_trend",
    "get_kline_by_code",
    "get_stock_by_code",
    "get_stock_intraday",
    "get_stock_kline",
    "get_stock_quote",
    "get_stock_sectors",
    "search_stocks",
]
