"""大盘总览服务（facade）。

历史为单文件 1038 行 6 职责；阶段 2.3 已拆分为 7 个职责服务：
- ``trade_calendar_service`` — 交易日判定
- ``index_quotation_service`` — 指数分时 / 快照 / K 线
- ``market_stats_service`` — 涨跌统计 + 情绪温度
- ``limit_pool_service`` — 涨停池
- ``sector_service`` — 板块热力图 + 资金流
- ``watchlist_quote_service`` — 自选股行情
- ``market_dispatch_service`` — 补采派发

本模块仅作 facade re-export，保持原调用点（API 路由、limit_up_ai_service、
market_review_service、test_market_service 等）不破。新代码请直接 import 子服务。
"""

from app.core.constants import INDEX_CODES  # noqa: F401 — 测试与旧调用点仍引用
from app.services.collector import market_dispatch_service
from app.services.collector.market_dispatch_service import (  # noqa: F401
    NonTradingDayError,
)
from app.services.market import (
    index_quotation_service,
    limit_pool_service,
    market_stats_service,
    sector_service,
    trade_calendar_service,
)
from app.services.user import watchlist_quote_service

# 交易日工具
resolve_latest_trade_date = trade_calendar_service.resolve_latest_trade_date
is_trading_day = trade_calendar_service.is_trading_day

# 指数行情
get_index_intraday = index_quotation_service.get_index_intraday
get_index_quotes = index_quotation_service.get_index_quotes
get_index_kline = index_quotation_service.get_index_kline

# 涨跌统计 / 情绪温度
get_market_stats = market_stats_service.get_market_stats

# 涨停池
get_limit_up = limit_pool_service.get_limit_up
get_limit_up_intraday = limit_pool_service.get_limit_up_intraday

# 板块
get_sector_overview = sector_service.get_sector_overview

# 自选股行情
get_watchlist_quotes = watchlist_quote_service.get_watchlist_quotes

# 补采
backfill_trade_date = market_dispatch_service.backfill_trade_date

# 测试中直接调用的私有 API（thin re-export；新代码请直接 import 子服务）。
_index_spot = index_quotation_service._index_spot
_db_index_spot = index_quotation_service._db_index_spot
_historical_index_quotes = index_quotation_service._historical_index_quotes
_amount_pair = market_stats_service._amount_pair
_live_breadth = market_stats_service._live_breadth
_historical_breadth = market_stats_service._historical_breadth
_limit_up_rates = market_stats_service._limit_up_rates
_emotion_score = market_stats_service._emotion_score
