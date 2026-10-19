"""K 线家族任务声明：股票/指数/ETF/A50/板块指数日 K 与新鲜度自愈。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="kline",
        label="K 线",
        description="采集股票日/周/月 K 线并入库，供个股图表与复盘分析使用",
        data_type="kline_{period}",
        # 仅 sina：ths_kline 实际走东财 push2his /kline/get（已被 WAF
        # 路径级封死），保留只会让 fallback 每次多一次注定失败的尝试。
        collectors={
            "sina": "collector.spiders.sina_kline:SinaKlineCollector",
        },
        config_params=("period",),
        # end_date 仅作「显式日期 = 手动补跑」预检豁免信号（spider 拉最近
        # N 根，不按区间裁剪）；声明进 run_params 才能到达 runner 预检 kwargs
        run_params=("end_date",),
        defaults={"period": "daily"},
    ),
    TaskSpec(
        name="watchlist-kline-daily",
        label="自选股日 K 补采",
        description="每日补采全部自选股日 K，保证自选页图表数据完整",
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
        description="采集指数日 K 线，支撑指数走势图与复盘基准",
        data_type="index_kline",
        collectors={
            "sina": "collector.spiders.sina_index_kline:SinaIndexKlineCollector",
        },
        # 同 kline：end_date 作手动补跑豁免信号
        run_params=("end_date",),
    ),
    TaskSpec(
        name="etf-kline",
        label="ETF 日 K",
        description="采集 ETF 日 K 线，用于 ETF 走势展示与分析",
        data_type="etf_kline",
        collectors={
            "sina": "collector.spiders.sina_etf_kline:SinaEtfKlineCollector",
        },
    ),
    TaskSpec(
        name="a50-kline",
        label="富时 A50 日 K",
        description="采集富时 A50 期指日 K，反映隔夜外盘情绪",
        data_type="a50_kline",
        # 东财 push2his kline 路径被 WAF 路径级封死，sina（全球期货 CHA50CFD）
        # 为主渠道；eastmoney 保留为兜底，仅 sina 失败时才会被尝试
        collectors={
            "sina": "collector.spiders.sina_a50_kline:SinaA50KlineCollector",
            "eastmoney": "collector.spiders.eastmoney_a50_kline:EastmoneyA50KlineCollector",
        },
    ),
    TaskSpec(
        name="sector-kline",
        label="板块指数日 K",
        description="采集同花顺行业/概念板块指数日 K，供板块详情页走势图",
        data_type="sector_kline",
        # 同花顺板块指数（行业/概念），板块详情页真实 K 线；名称桥接东财体系
        collectors={
            "ths": "collector.spiders.ths_sector_kline:ThsSectorKlineCollector",
        },
        run_params=("lookback_days",),
        # 定时路径入口对 run_params 键恒显式传参（缺省 None 会覆盖 spider
        # 签名默认值），缺省必须在声明表兜底
        defaults={"lookback_days": 10},
    ),
    TaskSpec(
        name="hk-kline",
        label="港股日 K",
        description="采集港股日 K（东财 secid=116，前复权），缺省宇宙=全市场港股",
        data_type="hk_kline",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_hk_kline:EastmoneyHkKlineCollector",
        },
        # 全市场约 2600 股 × 全局限速 1s，单轮约 45 分钟，走 heavy 队列
        queue="heavy",
        soft_time_limit=7200,
        run_params=("lookback_days",),
        # 定时路径入口对 run_params 键恒显式传参（缺省 None 会覆盖 spider
        # 签名默认值），缺省必须在声明表兜底；大跨度回填走手动传大值
        defaults={"lookback_days": 5},
    ),
    TaskSpec(
        name="kline-freshness",
        label="日K新鲜度自愈",
        description="检测日 K 数据缺口并自动补采自愈，保障图表数据新鲜",
        data_type="kline_freshness",
        collectors={
            "internal": "collector.spiders.kline_freshness:KlineFreshnessCollector",
        },
    ),
)
