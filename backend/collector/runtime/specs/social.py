"""社媒大 V 情绪任务声明：抖音视频采集与 LLM 情绪判断（F-SOC 一期）。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="social-video",
        label="抖音大V视频采集",
        data_type="social_video",
        collectors={
            "douyin": "collector.spiders.social_video:SocialVideoCollector",
        },
        run_params=("account_id", "backfill"),
        defaults={"account_id": None, "backfill": False},
        converters={"account_id": int},
        # 媒体流水线（拉流→ffmpeg→ASR）单轮可达 200 条，BATCH 默认 300s 必超
        soft_time_limit=3600,
        hard_time_limit=4200,
    ),
    TaskSpec(
        name="social-sentiment",
        label="大V情绪判断",
        data_type="ai_social_sentiment",
        collectors={
            "internal": "collector.spiders.social_sentiment:SocialSentimentCollector",
        },
    ),
)
