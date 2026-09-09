"""资讯任务声明：新闻/财联社电报/投资日历/订阅命中扫描。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="news",
        label="新闻",
        data_type="news",
        collectors={"sina": "collector.spiders.sina_news:SinaNewsCollector"},
    ),
    TaskSpec(
        name="news-subscription-match",
        label="订阅关键词命中扫描",
        data_type="news_subscription_hit",
        collectors={
            "internal": "collector.spiders.news_subscription_match:NewsSubscriptionMatchCollector",
        },
    ),
    TaskSpec(
        name="cls-telegraph-backfill",
        label="财联社电报回补",
        data_type="news_telegraph",
        queue="realtime",
        collectors={
            "cls": "collector.spiders.cls_telegraph:ClsTelegraphCollector",
        },
        run_params=("rn",),
        defaults={"rn": 20},
    ),
    TaskSpec(
        name="cls-investkalendar",
        label="财联社投资日历",
        data_type="invest_calendar",
        collectors={
            "cls": "collector.spiders.cls_investkalendar:ClsInvestkalendarCollector",
        },
    ),
)
