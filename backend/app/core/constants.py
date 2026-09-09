"""跨模块共享常量。"""

# 大盘指数代码（新浪格式） -> 名称；collector 指数 K 线采集与
# market 服务共用此清单，新增指数只改这一处
INDEX_CODES: dict[str, str] = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
}

# 指数/全球指标趋势缩略图取近 N 个收盘点（A 股与全球两路口径一致）
INDEX_TREND_DAYS = 30

# K 线周期词汇单一真相源：A 股 time_bucket 聚合（kline_repository.PERIOD_BUCKET，
# daily 直读不聚合）与全球指标 Python 聚合、API 路由校验共用，新增周期只改这一处
KLINE_PERIODS: tuple[str, ...] = (
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
)

# 指数 K 线图扩展标的（仅 K 线展示与 AI 技术分析，不进指数快照/分钟线/顶部行情卡）。
# sh510300 = 沪深300ETF（新浪 ETF 日 K）；CN00Y = 富时A50期指当月连续（东财日 K）
KLINE_CHART_EXTRA_CODES: dict[str, str] = {
    "sh510300": "沪深300ETF",
    "CN00Y": "富时A50",
}

# 全球跟踪指标清单（quote_global_index_daily 的 index_code 域）。
# eastmoney：push2delay ulist 实时快照（secid）；tushare：us_tycr 列名（date/y1..y30）；
# mof：日本财务省日债 CSV（历史回补 spider 自行解析）；yahoo：历史回填专用（symbol 供 spider 映射）
GLOBAL_INDEX_CODES: dict[str, dict[str, str]] = {
    "GC00Y": {"name": "COMEX 黄金", "data_source": "eastmoney", "secid": "101.GC00Y"},
    "DXY": {"name": "美元指数", "data_source": "eastmoney", "secid": "100.UDI"},
    "US2Y": {"name": "美债 2Y 收益率", "data_source": "tushare", "field": "y2"},
    "US10Y": {"name": "美债 10Y 收益率", "data_source": "tushare", "field": "y10"},
    "HSI": {"name": "恒生指数", "data_source": "eastmoney", "secid": "100.HSI"},
    "HSTECH": {"name": "恒生科技", "data_source": "eastmoney", "secid": "124.HSTECH"},
    "DJIA": {"name": "道琼斯", "data_source": "eastmoney", "secid": "100.DJIA"},
    "NDX": {"name": "纳斯达克", "data_source": "eastmoney", "secid": "100.NDX"},
    "SPX": {"name": "标普500", "data_source": "eastmoney", "secid": "100.SPX"},
    "N225": {"name": "日经225", "data_source": "eastmoney", "secid": "100.N225"},
    "JP10Y": {"name": "日本10Y国债", "data_source": "mof"},
    "US30Y": {"name": "美债 30Y 收益率", "data_source": "tushare", "field": "y30"},
    "USDCNY": {"name": "美元/人民币", "data_source": "yahoo"},
    "USDCNH": {"name": "美元/离岸人民币", "data_source": "eastmoney", "secid": "133.USDCNH"},
    "USDJPY": {"name": "美元/日元", "data_source": "eastmoney", "secid": "119.USDJPY"},
    "USDEUR": {"name": "美元/欧元", "data_source": "eastmoney", "secid": "119.USDEUR"},
    "B00Y": {"name": "布伦特原油", "data_source": "eastmoney", "secid": "112.B00Y"},
}

# ---- 资讯域共享标识 ----
# 电报源标识：news_ai_score.source 值、资讯渠道注册表 key、stream 驻留进程
# Redis 键的 <source> 段共用同一真相源；新增资讯源时在此登记标识
NEWS_SOURCE_TELEGRAPH = "cls_telegraph"
# stream 驻留进程 Redis 键模板（collector/runtime/stream 写入，渠道监控读取）
STREAM_CURSOR_KEY_TEMPLATE = "collector:stream:{source}:last_time"
STREAM_HEARTBEAT_KEY_TEMPLATE = "collector:stream:{source}:heartbeat"
