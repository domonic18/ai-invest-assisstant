"""SystemOneAdapter 契约测试：wire 形状、双形状错误信封、异常翻译（探针实证）。"""

import json

import httpx
import pytest

from app.core.decision_model import (
    DecisionModelRequestError,
    DecisionModelResponseError,
    DecisionModelUnavailableError,
    JudgeNoul,
    JudgeNoulAnswer,
    JudgeNoulCriteria,
    JudgeScore,
    SystemOneAdapter,
)

pytestmark = pytest.mark.unit

# 2026-09-28 探针①（OpenRouter typesafe/jev-1.13）真实响应体——三题型齐全
_PROBE_BODY = {
    "model": "typesafe/jev-1.13-20260917",
    "answers": {
        "should_trade": {"type": "noul", "noul": 0.14},
        "position_size": {
            "type": "choice",
            "choice": "zero",
            "probabilities": {"normal": 0, "zero": 0.73, "light": 0.27},
            "confidence": 0.6,
        },
        "sentiment_score": {
            "type": "score",
            "score": 0.03,
            "legend": {"0": "冰点", "1": "退潮", "2": "修复", "3": "发酵", "4": "高涨"},
            "probabilities": {"0": 0.97, "1": 0.03, "2": 0, "3": 0, "4": 0},
            "confidence": 0.97,
        },
    },
    "usage": {"input_tokens": 591, "output_tokens": 72, "cost": 2.4822e-05},
    "id": "gen-dec-1790570927-zDNXVlOrApey7U8SXJ8N",
    "provider": "TypeSafe",
}

_STATE = {"trade_date": "2026-09-28", "limit_up_count": 87}

_QUESTIONS = {
    "should_trade": JudgeNoul(
        instructions="今日是否适合建仓",
        criteria=JudgeNoulCriteria(criterion_true="情绪与量价共振", criterion_false="不满足"),
    ),
    "sentiment_score": JudgeScore(
        instructions="评估情绪周期位置", criteria=["冰点", "退潮", "修复", "发酵", "高涨"]
    ),
}


def _adapter(handler, *, base_url: str = "https://openrouter.ai/api") -> SystemOneAdapter:
    return SystemOneAdapter(
        base_url=base_url,
        api_key="sk-or-test",
        model="jev-latest",
        timeout_seconds=2.0,
        config_id=7,
        transport=httpx.MockTransport(handler),
    )


class TestHappyPath:
    async def test_probe_fixture_parses_all_three_answer_types(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_PROBE_BODY)

        response = await _adapter(handler).ask(_STATE, _QUESTIONS)

        assert response.model == "typesafe/jev-1.13-20260917"
        assert response.request_id == "gen-dec-1790570927-zDNXVlOrApey7U8SXJ8N"
        assert response.config_id == 7
        assert response.latency_ms >= 0
        assert response.usage.input_tokens == 591
        assert response.usage.output_tokens == 72
        assert response.usage.cost == pytest.approx(2.4822e-05)

        assert isinstance(response.answers["should_trade"], JudgeNoulAnswer)
        assert response.answers["should_trade"].noul == pytest.approx(0.14)

        choice = response.answers["position_size"]
        assert choice.choice == "zero"
        assert choice.confidence == pytest.approx(0.6)

        score = response.answers["sentiment_score"]
        assert score.score == pytest.approx(0.03)
        assert score.legend["0"] == "冰点"
        assert score.confidence == pytest.approx(0.97)

    async def test_request_body_shape(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["auth"] = request.headers.get("authorization")
            captured["payload"] = json.loads(request.read())
            return httpx.Response(200, json=_PROBE_BODY)

        await _adapter(handler).ask(_STATE, _QUESTIONS)

        assert captured["path"] == "/api/v1/systemone"
        assert captured["auth"] == "Bearer sk-or-test"
        payload = captured["payload"]
        assert payload["model"] == "jev-latest"  # pin 原样透传，不做客户端前缀改写
        assert payload["state"] == _STATE
        questions = payload["questions"]
        assert set(questions) == {"should_trade", "sentiment_score"}  # 键控对象而非数组
        assert questions["should_trade"]["type"] == "noul"
        assert questions["should_trade"]["criteria"] == {
            "true": "情绪与量价共振",
            "false": "不满足",
        }
        assert questions["sentiment_score"]["criteria"] == [
            "冰点", "退潮", "修复", "发酵", "高涨",
        ]

    async def test_full_endpoint_base_url_is_normalized(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == "https://openrouter.ai/api/v1/systemone"
            return httpx.Response(200, json=_PROBE_BODY)

        await _adapter(
            handler, base_url="https://openrouter.ai/api/v1/systemone/"
        ).ask(_STATE, _QUESTIONS)


class TestErrorEnvelopes:
    async def test_openrouter_error_envelope_maps_by_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                402, json={"error": {"message": "Insufficient credits", "code": 402}}
            )

        with pytest.raises(DecisionModelUnavailableError, match="Insufficient credits") as exc_info:
            await _adapter(handler).ask(_STATE, _QUESTIONS)
        assert exc_info.value.status_code == 402

    async def test_detail_dict_envelope_direct_vendor(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={
                    "detail": {
                        "error_type": "authentication_error",
                        "message": "invalid api key",
                    }
                },
            )

        with pytest.raises(DecisionModelRequestError, match="authentication_error: invalid api key"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_422_validation_list_envelope(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                422,
                json={"detail": [{"loc": ["body", "questions"], "msg": "Field required"}]},
            )

        with pytest.raises(DecisionModelRequestError, match="校验失败"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_detail_str_envelope(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "No endpoint found for jev-1.13.0"})

        with pytest.raises(DecisionModelRequestError, match="No endpoint found"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_429_maps_to_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})

        with pytest.raises(DecisionModelUnavailableError) as exc_info:
            await _adapter(handler).ask(_STATE, _QUESTIONS)
        assert exc_info.value.status_code == 429

    async def test_500_maps_to_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="upstream exploded")

        with pytest.raises(DecisionModelUnavailableError, match="upstream exploded"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_non_json_error_body_falls_back_to_text(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="<html>bad gateway</html>")

        with pytest.raises(DecisionModelUnavailableError, match="bad gateway"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_connect_timeout_maps_to_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        with pytest.raises(DecisionModelUnavailableError, match="超时"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_connect_error_maps_to_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with pytest.raises(DecisionModelUnavailableError, match="网络不可达"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)


class TestResponseShapeErrors:
    async def test_missing_answers(self) -> None:
        body = {"model": "jev", "usage": _PROBE_BODY["usage"]}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        with pytest.raises(DecisionModelResponseError, match="answers"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_missing_model(self) -> None:
        body = {"answers": _PROBE_BODY["answers"], "usage": _PROBE_BODY["usage"]}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        with pytest.raises(DecisionModelResponseError, match="model"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_missing_usage(self) -> None:
        body = {"model": "jev", "answers": _PROBE_BODY["answers"]}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        with pytest.raises(DecisionModelResponseError, match="usage"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_answer_discriminator_mismatch(self) -> None:
        body = {
            "model": "jev",
            "answers": {"q": {"type": "unknown_kind", "value": 1}},
            "usage": _PROBE_BODY["usage"],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        with pytest.raises(DecisionModelResponseError, match="answers 形状不符"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)

    async def test_non_json_success_body(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>proxy</html>")

        with pytest.raises(DecisionModelResponseError, match="非 JSON"):
            await _adapter(handler).ask(_STATE, _QUESTIONS)
