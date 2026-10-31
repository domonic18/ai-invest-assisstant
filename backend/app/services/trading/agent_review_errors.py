"""复盘域错误类型（多入口共用的稳定契约）。"""

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError


class PaperTradeReviewLockedError(ConflictError):
    """其他实例正在生成同周期的模拟盘复盘。"""

    default_message = "模拟盘复盘正在生成中，请稍后重试"


class TradingReviewNotFoundError(NotFoundError):
    """请求的复盘尚未生成。"""


class ReviewWindowNotReadyError(BadRequestError):
    """手动触发的窗口末日盘后同步尚未落库（直接失败，不排队重试）。"""
