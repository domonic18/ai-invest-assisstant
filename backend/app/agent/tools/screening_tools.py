"""问财选股助手工具（仅助手对话路径注入）。

核心查询与整形在 ``iwencai_service.screen()``（与 /screening 直查端点共用）；
本工具只负责 agent 叙述文本与 ``__event__`` 事件搭车。结果零落库。
"""

from typing import Any

from langchain_core.tools import tool

from app.agent.tools.page_event import page_event
from app.services.market import iwencai_service
from app.services.market.iwencai_service import IwencaiError


@tool
async def screen_stocks(query: str, limit: int = 30) -> dict[str, Any]:
    """使用同花顺问财按自然语言条件即席筛选 A 股股票，结果不落库、以临时表格回写到 /screening 页。

    适用：用户给出任意选股条件组合（技术面 / 涨停特征 / 财务质量 / 资金面等）
    需要一份股票清单时调用。答复中必须标注数据来源于同花顺问财。

    Args:
        query: 问财自然语言问句。组织问句时遵守：
            1. 日期必须显式年份（说"2026年8月19日"，不要说"8月19日"）。
            2. 主动向用户确认排除项：非ST、非北交所、非次新股，除非用户明确要包含。
            3. 财务比率类条件注意负值陷阱：如"扣非净利润/净利润≥0.7"在净利润为负时
               双负得正产生误命中，应同时加"净利润大于0"。
            4. 条件宜精不宜多：命中远超预期时引导用户收敛条件；未命中时逐步放宽
               或拆分条件，再用调整后的问句重新调用本工具。
        limit: 返回明细行数上限，最大 100。命中数远超 limit 时向用户说明并建议
            收敛条件或提高 limit（上限 100），不要默认拉满。
    """
    try:
        payload = await iwencai_service.screen(query, limit=limit)
    except IwencaiError as exc:
        return {"error": str(exc)}

    total = int(payload["total"])
    truncated = bool(payload["truncated"])
    stocks = list(payload["stocks"])
    if not stocks:
        text = (
            "问财未命中任何股票（原问句与自动放宽改写均为空）。"
            "可建议用户：放宽或拆分条件、确认日期带显式年份、减少排除项，"
            "然后用调整后的问句重新调用本工具。"
        )
    elif truncated:
        text = (
            f"问财命中 {total} 只，已返回前 100 条明细（数据来源于同花顺问财）。"
            "命中数远超返回量，建议用户收敛筛选条件，或确认是否需要提高 limit。"
        )
    else:
        text = f"问财命中 {total} 只（数据来源于同花顺问财）。"

    return {
        "summary": text,
        "total": total,
        "returned": len(stocks),
        "truncated": truncated,
        "chunks_info": payload["chunks_info"],
        "__event__": page_event("stock_screening.complete", **payload),
    }
