"""研报域摘要业务异常（子域唯一来源，研报/财报摘要共用）。"""

from app.core.exceptions import ConflictError, UnprocessableEntityError


class SummaryUnavailableError(UnprocessableEntityError):
    """PDF 不可用（无 MinIO 文件且无法从来源下载），无法生成摘要。"""


class SummaryInProgressError(ConflictError):
    """其他请求正在生成该文档的摘要。"""
