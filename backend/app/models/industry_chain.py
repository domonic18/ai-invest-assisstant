"""产业链分析的 SQLAlchemy ORM 模型。"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChainAnalysisVersion(Base):
    """产业链分析版本表，snapshot 存完整分析结果快照。"""

    __tablename__ = "industry_chain_analysis_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    industry: Mapped[str] = mapped_column(String(50), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ai_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_analysis_result.id", ondelete="SET NULL"), nullable=True
    )
    model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    node_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class ChainNode(Base):
    """产业链节点表，按版本复制，指标列随版本落库。"""

    __tablename__ = "industry_chain_node"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("industry_chain_analysis_version.id", ondelete="CASCADE"),
        nullable=True,
    )
    avg_gross_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    revenue_growth: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    research_and_development_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    bargaining_power: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    localization_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    technology_barrier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bottleneck_indicators: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    recent_breakthroughs: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class ChainEdge(Base):
    """产业链环节关系表。"""

    __tablename__ = "industry_chain_edge"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_node_id: Mapped[int] = mapped_column(
        ForeignKey("industry_chain_node.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[int] = mapped_column(
        ForeignKey("industry_chain_node.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relation_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    strength: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    criticality: Mapped[str | None] = mapped_column(String(10), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("industry_chain_analysis_version.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class ChainCompanyMapping(Base):
    """公司-产业链节点映射表。"""

    __tablename__ = "industry_chain_company_mapping"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    chain_node_id: Mapped[int] = mapped_column(
        ForeignKey("industry_chain_node.id", ondelete="CASCADE"), nullable=False
    )
    chain_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    revenue_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("industry_chain_analysis_version.id", ondelete="CASCADE"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
