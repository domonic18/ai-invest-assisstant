"""F-SOC schema 契约测试：LLM 判断契约全 required 无默认（铁律）+ wire camelCase + 合规边界。"""

import inspect

import pytest
from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticUndefined

from app.schemas.model_config import AsrConfigResponse
from app.schemas.social import (
    SocialAccountCreateRequest,
    SocialFeedItemResponse,
    SocialJudgmentResult,
    SocialTarget,
)

pytestmark = pytest.mark.unit


def _llm_contract_models() -> list[type]:
    """判断契约模型族（铁律约束面）。"""
    return [SocialJudgmentResult, SocialTarget]


class TestJudgmentContractNoDefaults:
    """结构化输出 schema 字段禁带默认值：带默认值不进 required，LLM 会静默省略。"""

    @pytest.mark.parametrize("model", _llm_contract_models())
    def test_all_fields_required(self, model: type) -> None:
        for name, field in model.model_fields.items():
            assert field.default is PydanticUndefined, f"{model.__name__}.{name} 不得带默认值"
            assert field.is_required(), f"{model.__name__}.{name} 必须进 required"

    def test_missing_any_field_rejected(self) -> None:
        payload: dict[str, object] = {
            "relevance": True,
            "stance": "bearish",
            "confidence": 0.9,
            "core_arguments": [],
            "targets": [],
            # summary 缺失
        }
        with pytest.raises(ValidationError):
            SocialJudgmentResult.model_validate(payload)

    def test_stance_literal_constrained(self) -> None:
        with pytest.raises(ValidationError):
            SocialJudgmentResult.model_validate(
                {
                    "relevance": True,
                    "stance": "bull",  # 非法枚举
                    "confidence": 0.9,
                    "core_arguments": [],
                    "targets": [],
                    "summary": "x",
                }
            )

    def test_confidence_range_constrained(self) -> None:
        with pytest.raises(ValidationError):
            SocialJudgmentResult.model_validate(
                {
                    "relevance": True,
                    "stance": "neutral",
                    "confidence": 1.5,
                    "core_arguments": [],
                    "targets": [],
                    "summary": "x",
                }
            )


class TestWireCamelCase:
    """自有 API wire 走 camelCase（CamelModel alias 单一真相源）。"""

    def _feed_item(self) -> dict[str, object]:
        return {
            "post_id": 1,
            "video_id": "7301234567890123456",
            "platform": "douyin",
            "account_id": 2,
            "account_alias": "财经老张",
            "category": "finance_kol",
            "topic_tags": ["A股", "新能源"],
            "published_at": "2026-09-15T03:00:00+00:00",
            "transcript_missing": False,
            "is_relevant": True,
            "stance": "bullish",
            "confidence": 0.85,
            "core_arguments": ["政策落地利好板块"],
            "targets": [{"target_type": "sector", "name": "新能源", "code": None}],
            "summary": "看好新能源",
        }

    def test_serializes_camel_case(self) -> None:
        dumped = SocialFeedItemResponse.model_validate(self._feed_item()).model_dump(by_alias=True)
        assert "postId" in dumped
        assert "videoId" in dumped
        assert "accountAlias" in dumped
        assert "publishedAt" in dumped
        assert "transcriptMissing" in dumped
        assert "coreArguments" in dumped
        assert "post_id" not in dumped  # 蛇形键不得出现

    def test_create_request_accepts_camel_input(self) -> None:
        req = SocialAccountCreateRequest.model_validate(
            {"platform": "douyin", "secUidOrUrl": "MS4wLjABAAAA", "alias": "老张"}
        )
        assert req.sec_uid_or_url == "MS4wLjABAAAA"


class TestComplianceBoundary:
    """transcript_text 是判后即清的临时缓存：任何响应模型不得包含该字段。"""

    def test_no_transcript_field_in_response_models(self) -> None:
        from app.schemas import social as social_schemas

        for name, obj in inspect.getmembers(social_schemas, inspect.isclass):
            if not (inspect.isclass(obj) and issubclass(obj, BaseModel)):
                continue
            if name in {"SocialTarget", "SocialJudgmentResult"}:
                continue  # LLM 契约不含文稿
            assert "transcript_text" not in obj.model_fields, f"{name} 泄漏 transcript_text"
            assert "transcriptText" not in obj.model_fields, f"{name} 泄漏 transcriptText"

    def test_asr_config_masks_key(self) -> None:
        fields = AsrConfigResponse.model_fields
        assert "api_key_masked" in fields
        assert "api_key" not in fields, "响应模型不得回传明文密钥"
        assert "api_key_encrypted" not in fields
