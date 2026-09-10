"""报告文件存储占用统计 schema。"""

from pydantic import Field

from app.schemas.base import CamelModel


class ReportStorageTypeSummary(CamelModel):
    """单个文件类型的存储占用。"""

    file_type: str
    file_count: int
    size_bytes: int = Field(0, ge=0)


class ReportStorageSummary(CamelModel):
    """全部报告文件的存储占用汇总。"""

    items: list[ReportStorageTypeSummary]
    total_size_bytes: int = Field(0, ge=0)
    total_file_count: int = Field(0, ge=0)
