"""交易 Agent 专属工具集（与人工侧边栏助手工具隔离，D18）。

批次 5：账户总览 + 下单/撤单（服务层下单出口共用，风控硬校验内聚）；
批次 7 追加只读读取与交易计划工具；批次 9 追加记忆工具。
写操作返回值嵌 ``paper_trading.complete`` 页面事件，驱动交易 Agent 页刷新。
"""

from typing import cast

from langchain_core.tools import BaseTool

from app.agent.tools.interaction_tools import ask_user
from app.agent.tools.trading.account import get_paper_trade_account
from app.agent.tools.trading.orders import cancel_paper_trade_order, place_paper_trade_order
from app.agent.tools.trading.plans import cancel_trade_plan, list_trade_plans, make_trade_plan
from app.agent.tools.trading.reads import get_daily_review, get_stock_selections

#: 工具集版本：每次增删工具时 +1（agent 实例缓存键组成部分，保证热更新）
TOOLS_VERSION = 3


def build_trading_tools() -> list[BaseTool]:
    """交易 Agent 工具清单（对话路径；定时执行直调服务层不经工具）。

    ask_user 是写操作确认底座（prompt 纪律「下单/撤单/制定计划前必确认」
    的执行手段）。
    """
    return cast(
        list[BaseTool],
        [
            get_paper_trade_account,
            ask_user,
            place_paper_trade_order,
            cancel_paper_trade_order,
            get_daily_review,
            get_stock_selections,
            make_trade_plan,
            list_trade_plans,
            cancel_trade_plan,
        ],
    )
