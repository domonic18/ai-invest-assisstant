"""资讯任务声明：新闻/财联社电报/投资日历/订阅命中扫描。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="news",
        label="新闻",
        description="采集东财快讯新闻流，作为资讯中心的基础数据源",
        data_type="news",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_flash_news:EastmoneyFlashNewsCollector",
        },
    ),
    TaskSpec(
        name="news-subscription-match",
        label="订阅关键词命中扫描",
        description="扫描用户订阅关键词并命中资讯，生成推送提醒数据",
        data_type="news_subscription_hit",
        collectors={
            "internal": "collector.spiders.news_subscription_match:NewsSubscriptionMatchCollector",
        },
    ),
    TaskSpec(
        name="cls-telegraph-backfill",
        label="财联社电报回补",
        description="回补财联社电报流水，保证电报视图数据连续",
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
        description="采集财联社投资日历（财经事件），供投资日历页",
        data_type="invest_calendar",
        collectors={
            "cls": "collector.spiders.cls_investkalendar:ClsInvestkalendarCollector",
        },
    ),
)
