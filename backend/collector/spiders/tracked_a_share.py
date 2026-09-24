"""用户自加 A 股跟踪标的的代码读取与指数/ETF 路由。

tracked_index_config 中用户自定义的 A 股指数/ETF（排除固定展示的
大盘标的）需纳入新浪日 K 定时采集，行情才能出现在行情卡；两类标的
走不同 akshare 接口，按代码前缀路由：
- 指数：sh000xxx/sh000688/sz399xxx 等 → ``stock_zh_index_daily``
- ETF：沪市 5xxxxx / 深市 15/16xxxx → ``fund_etf_hist_sina``
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.constants import INDEX_CODES, KLINE_CHART_EXTRA_CODES
from app.models.tracked_index import TrackedIndexConfig
from collector.core.base import get_engine

_ETF_CODE_RE = re.compile(r"^(sh5\d{5}|sz1[56]\d{4})$")
_FIXED_CODES = set(INDEX_CODES) | set(KLINE_CHART_EXTRA_CODES)


def is_etf_code(code: str) -> bool:
    """按前缀判定 ETF 代码（指数与 ETF 的采集接口不同）。"""
    return _ETF_CODE_RE.match(code) is not None


async def fetch_tracked_extra_codes() -> list[str]:
    """启用中的用户自加 A 股标的代码（排除固定展示标的），升序。"""
    session_maker = async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        rows = await session.execute(
            select(TrackedIndexConfig.index_code)
            .where(
                TrackedIndexConfig.market_category == "A股",
                TrackedIndexConfig.is_enabled.is_(True),
            )
            .order_by(TrackedIndexConfig.index_code)
        )
        return [row[0] for row in rows.all() if row[0] not in _FIXED_CODES]
