"""领域子代理声明：复用主助手工具子集，经 deepagents 内置 task 工具派发。

子代理系统提示词放 ``prompts/agents/subagent_*.yaml``（PromptLoader 加载），
与项目"禁止硬编码 Prompt"约定一致。
"""

from typing import Any, cast

from deepagents.middleware.subagents import SubAgent

from app.agent.core.prompt_loader import PromptLoader
from app.agent.runtime.assistant_tools import (
    get_auction_summary,
    get_market_overview,
    get_sector_fund_flow,
    get_stock_kline,
    get_stock_quote,
    query_financial_data,
    search_news,
    search_vector_kb,
)
from app.core.config import get_settings


def _prompt(prompt_id: str) -> str:
    config = PromptLoader(get_settings().prompts_dir).load("agents", prompt_id)
    return config.system_prompt


def build_subagents() -> list[SubAgent]:
    """三个领域子代理：行情 / 基本面 / 资讯情报。"""
    # SubAgent 为 TypedDict，可选键在类型层标记为必填，此处用 dict 构造后过 cast
    specs: list[dict[str, Any]] = [
        {
            "name": "market-analyst",
            "description": (
                "行情与技术面分析：个股行情快照、日K走势、大盘概览、集合竞价表现。"
                "需要任何行情数字时委派。"
            ),
            "system_prompt": _prompt("subagent_market"),
            "tools": [
                get_stock_quote,
                get_stock_kline,
                get_market_overview,
                get_auction_summary,
            ],
        },
        {
            "name": "fundamental-analyst",
            "description": (
                "基本面分析：财务指标（毛利率/营收同比/研发占比等）与研报知识库"
                "检索解读。财务与研报问题委派。"
            ),
            "system_prompt": _prompt("subagent_fundamental"),
            "tools": [query_financial_data, search_vector_kb],
        },
        {
            "name": "news-scout",
            "description": (
                "资讯情报收集：近期新闻/公告/研报标题检索与板块资金流向。"
                "热点、消息面、资金流向问题委派。"
            ),
            "system_prompt": _prompt("subagent_news"),
            "tools": [search_news, search_vector_kb, get_sector_fund_flow],
        },
    ]
    return [cast(SubAgent, spec) for spec in specs]
