"""个股分钟线共享基座：标的映射 / 默认采集范围 / 行变换。

sina（盘后校正）与 tencent（盘中主渠道）两个 ``stock-minute`` 渠道共用；
默认采集范围 = 目标日涨停池 ∪ 全部自选股 ∪ 交易 Agent 当日计划标的
（与 ``plan_stock_codes`` 同口径，保证 tick 分时输入的数据供给）。
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.pool_limit_up_stock import LimitUpPool
from app.models.watchlist import UserWatchlist
from collector.core.base import get_engine
from collector.core.parsing import to_float, to_int

CN_TZ = ZoneInfo("Asia/Shanghai")


def to_cn_symbol(code: str) -> str | None:
    """纯 6 位代码转交易所前缀 symbol（6→sh、0/3→sz）；北交所（4/8 开头）不支持返回 None。"""
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    return None


async def fetch_default_codes(target: date) -> list[str]:
    """默认采集范围：目标日涨停池 ∪ 全部自选股 ∪ 当日计划标的，去重升序。"""
    session_maker = async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        pool = await session.execute(
            select(LimitUpPool.stock_code)
            .where(LimitUpPool.trade_date == target)
            .order_by(LimitUpPool.stock_code)
        )
        watchlist = await session.execute(
            select(UserWatchlist.stock_code).distinct().order_by(UserWatchlist.stock_code)
        )
        codes = {row[0] for row in pool.all()} | {row[0] for row in watchlist.all()}
        # 延迟导入：避免 collector 导入链拉起 trading 服务依赖（判断模型/LLM 工厂）
        from app.services.trading.agent_intraday_service import plan_stock_codes

        codes |= await plan_stock_codes(session, trade_date=target)
        return sorted(codes)


def transform_minute_row(raw: dict[str, object]) -> dict[str, object]:
    """分钟 bar 标准行：volume 统一为股，amount 缺失置 NULL。"""
    return {
        "stock_code": str(raw["stock_code"]),
        "trade_time": raw["trade_time"],
        "open": to_float(raw.get("open")),
        "high": to_float(raw.get("high")),
        "low": to_float(raw.get("low")),
        "close": to_float(raw.get("close")),
        "volume": to_int(raw.get("volume")),
        "amount": to_float(raw.get("amount")),
    }


def parse_bar_datetime(value: str, fmt: str) -> datetime:
    """渠道时间字符串 → 目标日时区 aware datetime（Asia/Shanghai）。"""
    return datetime.strptime(value, fmt).replace(tzinfo=CN_TZ)
