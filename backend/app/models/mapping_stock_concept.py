"""股票-概念映射的 SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MappingStockConcept(Base):
    """股票-概念映射（同花顺概念成分股）。"""

    __tablename__ = "mapping_stock_concept"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    concept_code: Mapped[str] = mapped_column(String(20), nullable=False)
    concept_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="ths", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
