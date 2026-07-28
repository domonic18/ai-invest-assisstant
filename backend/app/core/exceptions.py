"""统一应用异常层次。

service 层抛出本模块中的异常（或子类），由 main.py 注册的全局
exception_handler 统一转换为 JSONResponse `{detail: message}`，
其格式与 FastAPI HTTPException 一致，前端 axios 已适配。

约定:
- 业务「找不到」→ ``NotFoundError``
- 业务「参数语义错误」（如非交易日、未知分区）→ ``BadRequestError``
- 业务「状态冲突」（如锁占用、生成中）→ ``ConflictError``
- 业务「语义无法处理」（如 PDF 不可用）→ ``UnprocessableEntityError``
- 业务「服务器内部错误」（如 LLM 未配置、AI 执行失败）→ ``InternalError``
"""


class AppError(Exception):
    """Base application exception. Carries an HTTP status code & message."""

    status_code: int = 500
    default_message: str = "Internal Server Error"

    def __init__(self, message: str | None = None, status_code: int | None = None):
        self.message = message or self.default_message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    default_message = "Resource not found"


class UnauthorizedError(AppError):
    status_code = 401
    default_message = "Unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    default_message = "Forbidden"


class BadRequestError(AppError):
    status_code = 400
    default_message = "Bad request"


class ConflictError(AppError):
    status_code = 409
    default_message = "Conflict"


class UnprocessableEntityError(AppError):
    status_code = 422
    default_message = "Unprocessable entity"


class InternalError(AppError):
    status_code = 500
    default_message = "Internal server error"
