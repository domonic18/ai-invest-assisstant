"""社交情绪查询助手工具（抖音大V散户情绪，供复盘情绪面取数）。"""

from typing import Any

from langchain_core.tools import tool

from app.agent.tools.market_tools import _parse_trade_date
from app.core.database import AsyncSessionLocal
from app.services.social import feed_service


@tool
async def get_social_sentiment(trade_date: str) -> dict[str, Any]:
    """获取当日抖音大V散户情绪聚合：多空中性分布与净多空、近 7 日净多空走势、代表性观点。

    散户情绪作反向指标解读：显著净看多且升温=情绪亢奋、风险积聚；净看空/冰点=情绪低位、
    机会大于风险。样本量不足时返回值会标注 sample_insufficient，此时结论不足为凭。

    Args:
        trade_date: 交易日期，ISO 格式如 "2026-09-17"。
    """
    day, error = _parse_trade_date(trade_date)
    if error or day is None:
        return {"error": "trade_date 须为 YYYY-MM-DD 格式"}
    async with AsyncSessionLocal() as session:
        return await feed_service.get_review_sentiment(session, day)
