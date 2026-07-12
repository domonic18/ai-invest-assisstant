"""Industry chain analysis related Pydantic schemas."""

from pydantic import BaseModel, Field


class ChainCompany(BaseModel):
    """产业链节点中的公司。"""

    code: str
    name: str


class ChainNode(BaseModel):
    """产业链节点。"""

    name: str
    type: str = Field(..., pattern="^(upstream|midstream|downstream)$")
    companies: list[ChainCompany]
    avg_gross_margin: float
    revenue_growth: float
    bargaining_power: float


class ChainEdge(BaseModel):
    """产业链边。"""

    source: str
    target: str
    relation: str
    strength: float
    description: str = ""


class ChainAnalysisRequest(BaseModel):
    """产业链分析请求。"""

    industry: str = Field(..., min_length=1, max_length=100)
    focus: str | None = None


class ChainAnalysisResult(BaseModel):
    """产业链分析结果。"""

    nodes: list[ChainNode]
    edges: list[ChainEdge]
    summary: str
    opportunities: list[str]
    risks: list[str]
