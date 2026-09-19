"""LLM 结构化输出 schema 契约钉死测试：字段禁带默认值。

默认值不进 JSON schema 的 required，模型会静默省略该字段
（news-score reason 全空事故）；无数据由模型显式输出空串/空列表/null。
"""

import pytest
from pydantic import BaseModel

from app.schemas.chain import ChainAlertItem, ChainAnalysisResult, ChainNode
from app.schemas.kb import (
    ChapterNodeDraft,
    ChapterTreeDraft,
    EpisodeOutline,
    EpisodeOutlinePoint,
    ImageUnderstanding,
    KbExtractionResult,
    KbPointDraft,
)
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


def test_kb_extraction_schemas_all_required() -> None:
    _assert_all_fields_required(KbExtractionResult)
    _assert_all_fields_required(KbPointDraft)
    # 可空字段必须显式输出 null（required 内），而非静默省略
    schema = KbPointDraft.model_json_schema()
    for field in ("term_definition", "applicable_scene", "start_ms", "end_ms"):
        assert field in schema["required"], f"KbPointDraft.{field} 不在 required"


def test_kb_outline_and_image_schemas_all_required() -> None:
    _assert_all_fields_required(EpisodeOutline)
    _assert_all_fields_required(EpisodeOutlinePoint)
    _assert_all_fields_required(ChapterTreeDraft)
    _assert_all_fields_required(ChapterNodeDraft)
    _assert_all_fields_required(ImageUnderstanding)
    # 自引用 children 必须在 required 内（目录树空节点显式输出 []）；
    # 自引用模型顶层是 $ref，required 在 $defs 定义体内
    node_schema = ChapterNodeDraft.model_json_schema()
    node_required = node_schema.get("required") or next(
        iter(node_schema["$defs"].values())
    )["required"]
    assert "children" in node_required
