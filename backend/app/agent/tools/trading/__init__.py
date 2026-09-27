"""交易 Agent 专属工具集（与人工侧边栏助手工具隔离，D18）。

批次 5：账户总览 + 下单/撤单（服务层下单出口共用，风控硬校验内聚）；
批次 7 追加只读读取与交易计划工具；批次 9 追加记忆工具。
写操作返回值嵌 ``paper_trading.complete`` 页面事件，驱动交易 Agent 页刷新。
工具经 ``make_*`` 工厂按 agent_key 闭包绑定（多 Agent 基座 D24）。
"""

from typing import cast

from langchain_core.tools import BaseTool

from app.agent.tools.interaction_tools import ask_user
from app.agent.tools.trading.account import make_get_account_tool
from app.agent.tools.trading.orders import make_cancel_order_tool, make_place_order_tool
from app.agent.tools.trading.plans import (
    make_cancel_plan_tool,
    make_list_plans_tool,
    make_make_plan_tool,
)
from app.agent.tools.trading.reads import make_get_review_tool, make_get_selections_tool

#: 工具集版本：每次增删工具时 +1（agent 实例缓存键组成部分，保证热更新）
TOOLS_VERSION = 4


def build_trading_tools(agent_key: str) -> list[BaseTool]:
    """指定 Agent 的工具清单（对话路径；定时执行直调服务层不经工具）。

    ask_user 是写操作确认底座（prompt 纪律「下单/撤单/制定计划前必确认」
    的执行手段）。
    """
    return cast(
        list[BaseTool],
        [
            make_get_account_tool(agent_key),
            ask_user,
            make_place_order_tool(agent_key),
            make_cancel_order_tool(agent_key),
            make_get_review_tool(agent_key),
            make_get_selections_tool(agent_key),
            make_make_plan_tool(agent_key),
            make_list_plans_tool(agent_key),
            make_cancel_plan_tool(agent_key),
        ],
    )
