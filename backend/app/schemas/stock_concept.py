"""股票-概念映射管理 schemas（admin 题材映射页）。"""

from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class AdminStockConceptCreate(CamelModel):
    """新增股票-概念映射。"""

    stock_code: str = Field(..., min_length=6, max_length=10)
    concept_code: str = Field(..., min_length=1, max_length=20)
    concept_name: str = Field(..., min_length=1, max_length=100)


class AdminStockConceptUpdate(CamelModel):
    """更新股票-概念映射（None 字段不动；改 (stock_code, concept_code) 冲突时 409）。"""

    stock_code: str | None = Field(None, min_length=6, max_length=10)
    concept_code: str | None = Field(None, min_length=1, max_length=20)
    concept_name: str | None = Field(None, min_length=1, max_length=100)


class AdminStockConceptResponse(CamelModel):
    """股票-概念映射列表项（stock_name 由 stock_basic 左联富化）。"""

    id: int
    stock_code: str
    stock_name: str | None = None
    concept_code: str
    concept_name: str
    source: str
    updated_at: datetime
