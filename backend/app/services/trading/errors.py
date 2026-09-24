"""模拟盘 sidecar 异常层次（service 层抛出，main.py 全局 handler 统一转 HTTP）。

- 未配置 / 凭据失效 → ``PaperTradeNotConfiguredError``（503，前端展示引导卡）
- sidecar 或柜台错误 → ``PaperTradeGatewayError``（502，携带柜台报错原文）
"""

from app.core.exceptions import AppError


class PaperTradeNotConfiguredError(AppError):
    """模拟盘功能未配置（paper_trade_url 为空）或 sidecar 凭据缺失/无效。"""

    status_code = 503
    default_message = "模拟盘功能未配置"


class PaperTradeTokenInvalidError(PaperTradeNotConfiguredError):
    """柜台 token 已失效（sidecar 503 且报文含「token 无效」）。

    继承 NotConfigured 以保留前端引导卡/overview enabled:false 行为，
    仅在前端凭 detail 前缀做定向提示（去账户配置更新 token）。
    """

    default_message = (
        "掘金仿真 token 已失效，请在「账户配置」中更新"
        "（掘金客户端或 sim.myquant.cn 个人中心可重置）"
    )


class PaperTradeGatewayError(AppError):
    """sidecar 在线但柜台请求失败（网络不可达、柜台报错、响应异常）。"""

    status_code = 502
    default_message = "模拟盘网关错误"
