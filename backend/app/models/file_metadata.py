"""文件元数据的 SQLAlchemy ORM 模型。"""

from datetime import date, datetime

from sqlalchemy import BIGINT, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FileMetadata(Base):
    """文件元数据表，用于研报、财报、公告等文件管理。"""

    __tablename__ = "file_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    report_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    broker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    md5_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
