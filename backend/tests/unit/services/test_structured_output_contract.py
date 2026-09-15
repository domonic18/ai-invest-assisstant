"""LLM 结构化输出 schema 契约钉死测试：字段禁带默认值。

默认值不进 JSON schema 的 required，模型会静默省略该字段
（news-score reason 全空事故）；无数据由模型显式输出空串/空列表/null。
"""

import pytest
from pydantic import BaseModel

from app.schemas.chain import ChainAlertItem, ChainAnalysisResult, ChainNode
from app.services.reports.financial_report_summarizer import (
    FinancialReportSummaryResult,
)
from app.services.reports.research_service import ResearchReportSummaryResult

pytestmark = pytest.mark.unit


def _assert_all_fields_required(model: type[BaseModel]) -> None:
    not_required = [
        name for name, field in model.model_fields.items() if not field.is_required()
    ]
    assert not_required == [], f"{model.__name__} 存在带默认值的输出字段: {not_required}"


def test_summarizer_output_schemas_all_required() -> None:
    _assert_all_fields_required(FinancialReportSummaryResult)
    _assert_all_fields_required(ResearchReportSummaryResult)


def test_chain_analysis_result_top_level_all_required() -> None:
    _assert_all_fields_required(ChainAnalysisResult)


def test_chain_nested_alert_fields_all_required() -> None:
    _assert_all_fields_required(ChainAlertItem)
    companies = ChainNode.model_fields["companies"]
    assert companies.is_required()
