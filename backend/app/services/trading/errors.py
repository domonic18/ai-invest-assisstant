"""模拟盘 sidecar 异常层次（service 层抛出，main.py 全局 handler 统一转 HTTP）。

- 未配置 / 凭据失效 → ``PaperTradeNotConfiguredError``（503，前端展示引导卡）
- sidecar 或柜台错误 → ``PaperTradeGatewayError``（502，携带柜台报错原文）
"""

from app.core.exceptions import AppError


class PaperTradeNotConfiguredError(AppError):
    """模拟盘功能未配置（paper_trade_url 为空）或 sidecar 凭据缺失/无效。"""

    status_code = 503
    default_message = "模拟盘功能未配置"


class PaperTradeGatewayError(AppError):
    """sidecar 在线但柜台请求失败（网络不可达、柜台报错、响应异常）。"""

    status_code = 502
    default_message = "模拟盘网关错误"
