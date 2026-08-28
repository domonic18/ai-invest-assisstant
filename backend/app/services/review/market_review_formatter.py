"""AI 大盘综述响应组装与格式化（纯函数，无 IO）。"""

from dataclasses import dataclass
from datetime import date, datetime

from app.agent.core.prompt_loader import PromptSection
from app.schemas.market import MarketReviewResponse, MarketReviewSection


@dataclass
class BaseReview:
    """共享 base 记录（含数据库主键，用于用户编辑副本关联）。"""

    id: int
    response: MarketReviewResponse


def build_response(
    trade_date: date,
    contents: dict[str, str],
    sections: list[PromptSection],
    model: str | None,
    generated_at: datetime,
    cached: bool,
    edited: bool,
) -> MarketReviewResponse:
    """按 YAML 声明的分区顺序组装响应（未声明的内容键丢弃，缺失分区补空串）。"""
    return MarketReviewResponse(
        trade_date=trade_date,
        sections=[
            MarketReviewSection(
                key=section.key,
                title=section.title,
                content=contents.get(section.key, ""),
            )
            for section in sections
        ],
        model=model,
        generated_at=generated_at,
        cached=cached,
        edited=edited,
    )


def format_amount(amount: float | None) -> str:
    if amount is None:
        return "未知"
    if amount >= 1e12:
        return f"{amount / 1e12:.2f} 万亿元"
    return f"{amount / 1e8:.0f} 亿元"
