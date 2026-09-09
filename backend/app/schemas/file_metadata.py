"""文件元数据的 Pydantic schemas。"""

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import CamelModel


class FileMetadataBase(CamelModel):
    """文件元数据的基础字段。"""

    file_path: str = Field(..., max_length=500)
    original_name: str | None = Field(None, max_length=500)
    file_type: str = Field(..., max_length=20)
    stock_code: str | None = Field(None, max_length=10)
    report_date: date | None = None
    report_type: str | None = Field(None, max_length=20)
    broker: str | None = Field(None, max_length=100)
    file_size: int | None = None
    md5_hash: str | None = Field(None, max_length=32)
    download_url: str | None = None


class FileMetadataCreate(FileMetadataBase):
    """创建文件元数据的请求 schema。"""


class FileMetadataUpdate(CamelModel):
    """更新文件元数据的请求 schema。"""

    original_name: str | None = Field(None, max_length=500)
    file_type: str | None = Field(None, max_length=20)
    stock_code: str | None = Field(None, max_length=10)
    report_date: date | None = None
    report_type: str | None = Field(None, max_length=20)
    broker: str | None = Field(None, max_length=100)
    file_size: int | None = None
    md5_hash: str | None = Field(None, max_length=32)
    download_url: str | None = None


class FileMetadataResponse(FileMetadataBase):
    """文件元数据的响应 schema。"""

    id: int
    download_count: int
    created_at: datetime
    stock_name: str | None = None


class FinancialReportListRequest(CamelModel):
    """财报列表查询参数。"""

    stock_code: str | None = None
    q: str | None = None
    report_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class FinancialReportResponse(CamelModel):
    """财报中心列表/详情响应（title/has_summary 由服务层派生）。"""

    id: int
    stock_code: str | None = None
    stock_name: str | None = None
    title: str | None = None
    report_type: str | None = None
    report_date: date | None = None
    file_size: int | None = None
    summary: str | None = None
    has_summary: bool = False
    created_at: datetime


class FinancialReportCollectRequest(CamelModel):
    """触发单只股票财报采集的请求。"""

    stock_code: str = Field(..., min_length=1, max_length=10)
    report_types: list[str] | None = Field(None, max_length=10)
    start_date: date | None = None
    end_date: date | None = None


class FinancialReportCollectResponse(CamelModel):
    """采集任务已入队的响应。"""

    log_id: int
    status: str


class FinancialReportCollectLogResponse(CamelModel):
    """采集任务进度。"""

    log_id: int
    status: str
    records_count: int
    error_msg: str | None = None
    finished_at: datetime | None = None
