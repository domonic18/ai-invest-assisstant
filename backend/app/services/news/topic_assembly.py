"""热点主题聚类纯函数层：候选裁剪、热度合成、主题卡拼装、标题词云。

无 IO（jieba 分词除外，属纯计算）；编排与落库在 ``topic_service``，
读取富化在 ``topic_query``。
"""

import json
from collections import Counter
from typing import Any

import structlog

from app.core.clock import now_cn
from app.repositories.news import topic_repository

logger = structlog.get_logger(__name__)

_INTRADAY_CUTOFF_HOUR = 15
_CONTENT_CHARS = 200
_INPUT_CHAR_CAP = 12000
_MIN_ITEMS_PER_TOPIC = 3

# 热度合成权重：资讯量 / 板块涨幅 / 主力资金净流入
_HEAT_W_NEWS = 0.4
_HEAT_W_CHANGE = 0.3
_HEAT_W_FLOW = 0.3

# 板块涨幅 10% / 主力净流入 10 亿 → 各自分项满分
_CHANGE_FULL_PCT = 10.0
_FLOW_FULL_YUAN = 1e9

_WORDCLOUD_TOP = 40

# jieba 词性白名单：名词类 + 动名词/形容词 + 英文词（滤掉动词/虚词等噪音）
_WORDCLOUD_POS = frozenset({"n", "nr", "ns", "nt", "nz", "vn", "an", "nx", "eng"})

# 财经标题高频但无区分度的通用词（分词后再滤一道）
_WORDCLOUD_STOPWORDS = frozenset(
    """
    公司 相关 表示 认为 报道 消息 发布 公告 数据 显示 预计 预期 可能 继续
    以及 进行 召开 举行 实现 提出 开展 获批 签署 达成 亿元 万元 今日 昨日
    明日 今年 去年 明年 目前 近期 记者 了解 获悉 通知 要求 工作 有关 旗下
    消息面 公告称 报道称 表示将 上述 方面 情况 问题 发展 影响 新股
    股份 行业 板块 机构 企业 产品 股东 市场 业务 领域 项目
    """.split()
)


def resolve_session(session_key: str | None) -> str:
    """未显式指定时按北京时间判定：15 点前盘中跑，之后盘后跑。"""
    if session_key in ("intraday", "post"):
        return session_key
    return "intraday" if now_cn().hour < _INTRADAY_CUTOFF_HOUR else "post"


def candidate_payload(row: Any) -> dict[str, Any]:
    """(电报行, score) -> 聚类输入 payload（content 节选控 token）。"""
    telegraph, score = row
    return {
        "source": topic_repository.SOURCE_TELEGRAPH,
        "item_id": str(telegraph.cls_msg_id),
        "title": telegraph.title,
        "content": (telegraph.content or "")[:_CONTENT_CHARS],
        "category": telegraph.category,
        "stock_codes": telegraph.stock_codes or [],
        "score": score,
        "publish_time": telegraph.publish_time.isoformat(),
    }


def trim_to_cap(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """候选超出单轮字符上限时自尾部（最旧）裁剪，至少保留 1 条。"""
    total = sum(len(json.dumps(p, ensure_ascii=False)) for p in payload)
    while len(payload) > 1 and total > _INPUT_CHAR_CAP:
        removed = payload.pop()
        total -= len(json.dumps(removed, ensure_ascii=False))
    return payload


def build_wordcloud(titles: list[str | None]) -> list[dict[str, Any]]:
    """标题分词词频（jieba 词性白名单 + 停用词过滤），取 TOP N。

    bigram 会产出「公司/产品」类无语义切片，改真分词才有区分度。
    """
    import jieba.posseg

    counter: Counter[str] = Counter()
    for title in titles:
        if not title:
            continue
        for word, flag in jieba.posseg.cut(title):
            if len(word) < 2 or flag not in _WORDCLOUD_POS:
                continue
            if word in _WORDCLOUD_STOPWORDS:
                continue
            counter[word] += 1
    return [{"word": w, "count": c} for w, c in counter.most_common(_WORDCLOUD_TOP)]


def heat_score(
    *,
    news_count: int,
    max_news_count: int,
    sector_change_pct: float | None,
    fund_flow_net: float | None,
) -> float:
    """热度 0-100：0.4×资讯量占比 + 0.3×|板块涨幅| + 0.3×|主力净流入|。"""
    news_part = news_count / max_news_count * 100 if max_news_count else 0.0
    change_part = (
        min(100.0, abs(sector_change_pct) / _CHANGE_FULL_PCT * 100)
        if sector_change_pct is not None
        else 0.0
    )
    flow_part = (
        min(100.0, abs(fund_flow_net) / _FLOW_FULL_YUAN * 100)
        if fund_flow_net is not None
        else 0.0
    )
    return round(
        _HEAT_W_NEWS * news_part + _HEAT_W_CHANGE * change_part + _HEAT_W_FLOW * flow_part,
        1,
    )


def assemble_topic(
    draft: Any,
    valid_keys: set[str],
    factors_by_sector: dict[str, dict[str, Any]],
    max_news_count: int,
) -> dict[str, Any] | None:
    """LLM 草稿 + 库内板块因子 -> 主题卡 dict；幻觉过滤后不足 3 篇返回 None。"""
    item_ids = [i for i in draft.item_ids if i in valid_keys]
    if len(item_ids) < _MIN_ITEMS_PER_TOPIC:
        logger.info("topic_below_threshold", title=draft.title, items=len(item_ids))
        return None

    sectors: list[dict[str, Any]] = []
    change_values: list[float] = []
    flow_values: list[float] = []
    as_of_dates: list[str] = []
    for name in draft.sector_names:
        factor = factors_by_sector.get(name)
        if factor is None:
            sectors.append({"name": name, "change_pct": None, "fund_flow": None})
            continue
        change_pct = factor.get("change_pct")
        flow = factor.get("main_net_inflow")
        # Numeric 列回传 Decimal，JSONB 序列化前必须收敛为 float
        sectors.append(
            {
                "name": name,
                "change_pct": None if change_pct is None else float(change_pct),
                "fund_flow": None if flow is None else float(flow),
            }
        )
        if change_pct is not None:
            change_values.append(float(change_pct))
        if flow is not None:
            flow_values.append(float(flow))
        trade_date = factor.get("trade_date")
        if trade_date is not None:
            as_of_dates.append(trade_date.isoformat())

    sector_change_pct = (
        sum(change_values) / len(change_values) if change_values else None
    )
    fund_flow_net = sum(flow_values) if flow_values else None
    return {
        "title": draft.title,
        "sentiment": draft.sentiment,
        "votes": draft.votes.model_dump(),
        "news_count": len(item_ids),
        "channel_counts": {topic_repository.SOURCE_TELEGRAPH: len(item_ids)},
        "heat": heat_score(
            news_count=len(item_ids),
            max_news_count=max_news_count,
            sector_change_pct=sector_change_pct,
            fund_flow_net=fund_flow_net,
        ),
        "factors": {
            "news_count": len(item_ids),
            "sector_change_pct": sector_change_pct,
            "fund_flow_net": fund_flow_net,
            "as_of_trade_date": max(as_of_dates) if as_of_dates else None,
        },
        "sectors": sectors,
        "chain": [step.model_dump() for step in draft.chain],
        "item_ids": item_ids,
    }
