"""K 线家族任务声明：股票/指数/ETF/A50 日 K 与新鲜度自愈。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="kline",
        label="K 线",
        data_type="kline_{period}",
        # 仅 sina：ths_kline 实际走东财 push2his /kline/get（已被 WAF
        # 路径级封死），保留只会让 fallback 每次多一次注定失败的尝试。
        collectors={
            "sina": "collector.spiders.sina_kline:SinaKlineCollector",
        },
        config_params=("period",),
        defaults={"period": "daily"},
    ),
    TaskSpec(
        name="watchlist-kline-daily",
        label="自选股日 K 补采",
        data_type="watchlist_kline_daily",
        # 缺省 symbols = 全部自选股（见 sina_kline._fetch_watchlist_codes）
        collectors={
            "sina": "collector.spiders.sina_kline:SinaKlineCollector",
        },
        config_params=("period",),
        defaults={"period": "daily"},
    ),
    TaskSpec(
        name="index-kline",
        label="指数 K 线",
        data_type="index_kline",
        collectors={
            "sina": "collector.spiders.sina_index_kline:SinaIndexKlineCollector",
        },
    ),
    TaskSpec(
        name="etf-kline",
        label="ETF 日 K",
        data_type="etf_kline",
        collectors={
            "sina": "collector.spiders.sina_etf_kline:SinaEtfKlineCollector",
        },
    ),
    TaskSpec(
        name="a50-kline",
        label="富时 A50 日 K",
        data_type="a50_kline",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_a50_kline:EastmoneyA50KlineCollector",
        },
    ),
    TaskSpec(
        name="kline-freshness",
        label="日K新鲜度自愈",
        data_type="kline_freshness",
        collectors={
            "internal": "collector.spiders.kline_freshness:KlineFreshnessCollector",
        },
    ),
)
