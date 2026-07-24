"""Industry chain analysis related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChainCompany(BaseModel):
    """产业链节点中的公司。"""

    code: str
    name: str


class ChainNode(BaseModel):
    """产业链节点，指标为百分比或 0-100 评分，缺失时为 None。"""

    name: str
    type: str = Field(..., pattern="^(upstream|midstream|downstream)$")
    description: str = ""
    companies: list[ChainCompany] = Field(default_factory=list)
    avg_gross_margin: float | None = None
    revenue_growth: float | None = None
    rd_ratio: float | None = None
    bargaining_power: float | None = None
    localization_rate: float | None = None
    tech_barrier: str | None = None
    bottleneck_indicators: list[str] = Field(default_factory=list)
    recent_breakthroughs: list[str] = Field(default_factory=list)


class ChainEdge(BaseModel):
    """产业链边。"""

    source: str
    target: str
    relation: str
    strength: float
    description: str = ""
    criticality: str | None = None


class ChainOpportunity(BaseModel):
    """投资机会，confidence 为 high/medium/low。"""

    title: str
    description: str = ""
    related_segment: str | None = None
    confidence: str | None = None


class ChainRisk(BaseModel):
    """风险提示，severity 为 high/medium/low。"""

    title: str
    description: str = ""
    related_segment: str | None = None
    severity: str | None = None


class ChainValueDistribution(BaseModel):
    """产业链价值分布（毛利率最高/最低环节）。"""

    highest_margin_segment: str | None = None
    highest_margin_value: float | None = None
    lowest_margin_segment: str | None = None
    lowest_margin_value: float | None = None


class KeyCompanySummary(BaseModel):
    """核心标的摘要，score 为 0-100 综合评分。"""

    code: str
    name: str
    chain_position: str | None = None
    score: float | None = None


class ChainAnalysisRequest(BaseModel):
    """产业链分析请求。"""

    industry: str = Field(..., min_length=1, max_length=100)
    focus: str | None = None


class ChainAnalysisResult(BaseModel):
    """产业链分析结果，对齐 skills/industry-chain-analysis/SKILL.md 输出。"""

    nodes: list[ChainNode]
    edges: list[ChainEdge]
    summary: str
    value_distribution: ChainValueDistribution | None = None
    opportunities: list[ChainOpportunity] = Field(default_factory=list)
    risks: list[ChainRisk] = Field(default_factory=list)
    key_companies_summary: list[KeyCompanySummary] = Field(default_factory=list)

    @field_validator("opportunities", mode="before")
    @classmethod
    def _coerce_opportunities(cls, value: object) -> object:
        """容忍 LLM 输出纯字符串列表，包装为对象。"""
        if isinstance(value, list):
            return [
                {"title": item} if isinstance(item, str) else item for item in value
            ]
        return value

    @field_validator("risks", mode="before")
    @classmethod
    def _coerce_risks(cls, value: object) -> object:
        """容忍 LLM 输出纯字符串列表，包装为对象。"""
        if isinstance(value, list):
            return [
                {"title": item} if isinstance(item, str) else item for item in value
            ]
        return value


class ChainAnalyzeResponse(BaseModel):
    """POST /chain/analyze 响应，带版本信息。"""

    version_id: int
    version_no: int
    status: str
    result: ChainAnalysisResult | None = None


class ChainVersionSummary(BaseModel):
    """版本列表项。"""

    id: int
    industry_level_1: str
    version_no: int
    label: str | None
    status: str
    model: str | None
    node_count: int | None
    company_count: int | None
    created_by: str
    created_at: datetime


class ChainVersionDetail(BaseModel):
    """版本详情，result 来自快照。"""

    version: ChainVersionSummary
    result: ChainAnalysisResult | None
    error_msg: str | None = None


class ChainCompareCompanyChange(BaseModel):
    """版本对比中的标的增删。"""

    code: str
    name: str
    node_name: str


class ChainCompareMetricChange(BaseModel):
    """版本对比中的节点指标变化。"""

    node_name: str
    field: str
    base_value: float | None
    target_value: float | None


class ChainCompareResult(BaseModel):
    """两个版本的差异。"""

    base_version: ChainVersionSummary
    target_version: ChainVersionSummary
    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    added_companies: list[ChainCompareCompanyChange] = Field(default_factory=list)
    removed_companies: list[ChainCompareCompanyChange] = Field(default_factory=list)
    metric_changes: list[ChainCompareMetricChange] = Field(default_factory=list)
