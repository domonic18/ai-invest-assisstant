"""跨模块共享常量。"""

# 大盘指数代码（新浪格式） -> 名称；collector 指数 K 线采集与
# market 服务共用此清单，新增指数只改这一处
INDEX_CODES: dict[str, str] = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
}

# 指数 K 线图扩展标的（仅 K 线展示与 AI 技术分析，不进指数快照/分钟线/顶部行情卡）。
# sh510300 = 沪深300ETF（新浪 ETF 日 K）；CN00Y = 富时A50期指当月连续（东财日 K）
KLINE_CHART_EXTRA_CODES: dict[str, str] = {
    "sh510300": "沪深300ETF",
    "CN00Y": "富时A50",
}

# 全球跟踪指标清单（quote_global_index_daily 的 index_code 域）。
# eastmoney：push2delay ulist 实时快照（secid）；tushare：us_tycr 列名（date/y1..y30）
GLOBAL_INDEX_CODES: dict[str, dict[str, str]] = {
    "GC00Y": {"name": "COMEX 黄金", "data_source": "eastmoney", "secid": "101.GC00Y"},
    "DXY": {"name": "美元指数", "data_source": "eastmoney", "secid": "100.UDI"},
    "US2Y": {"name": "美债 2Y 收益率", "data_source": "tushare", "field": "y2"},
    "US10Y": {"name": "美债 10Y 收益率", "data_source": "tushare", "field": "y10"},
}
