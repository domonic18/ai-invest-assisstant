"""社媒大 V 情绪域共享常量（F-SOC：模型校验、采集与判断任务的单一来源）。"""

from enum import Enum


class SocialPlatform(str, Enum):
    """内容平台（一期仅抖音，模型按平台字段设计可扩展）。"""

    DOUYIN = "douyin"


class SocialCategory(str, Enum):
    """追踪账号分类（前端筛选 chips 与账号卡的维度）。"""

    MACRO_POLICY = "macro_policy"
    FINANCE_KOL = "finance_kol"
    INDUSTRY = "industry"


class SentimentStance(str, Enum):
    """LLM 多空立场。"""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SocialTargetType(str, Enum):
    """影响标的市场对象类型。"""

    INDEX = "index"
    SECTOR = "sector"
    STOCK = "stock"
    COMMODITY = "commodity"


#: 仅看强信号的置信度阈值（feed strongOnly 过滤）
SOCIAL_STRONG_CONFIDENCE = 0.8

#: 情绪判断单轮批量上限（10 分钟一轮，消化小时级增量足够）
SOCIAL_JUDGE_BATCH_SIZE = 20

#: 临时文稿滞留上限（天），超过即清（防文稿长期滞留）
SOCIAL_TRANSCRIPT_STALE_DAYS = 7

#: 判断任务 redis 锁键
SOCIAL_SENTIMENT_LOCK_KEY = "social-sentiment-judge"

#: 作品列表最大续拉页数（单页起，has_more 且本地缺视频时续拉，防长尾）
SOCIAL_MAX_LIST_PAGES = 3

#: 回填采集深翻页上限（每页约 20 条 × 10 页封顶；每条走 ASR 转写，
#: 成本与时长随深度线性增长，管理端 Popconfirm 已提示）
SOCIAL_BACKFILL_MAX_LIST_PAGES = 10

#: 账号轮询间隔下限（分钟），管理端登记校验
SOCIAL_MIN_POLL_INTERVAL_MINUTES = 5
