"""产业链 API 端点契约测试。"""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.dependencies import get_current_user
from app.main import app
from app.schemas.chain import (
    ChainAlertResponse,
    ChainAnalysisResult,
    ChainAnalyzeResponse,
    ChainCompareResult,
    ChainVersionDetail,
    ChainVersionSummary,
)
from app.services.admin.llm_config_service import LLMConfigNotConfiguredError
from app.services.chain.chain_service import ChainAnalysisFailedError


@pytest.fixture
def user():
    return type(
        "User", (object,), {"id": 42, "username": "test", "role": "user", "is_active": True}
    )()


@pytest.fixture
def auth_client(client, user):
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.clear()


def _summary(version_id: int = 1, version_no: int = 1) -> ChainVersionSummary:
    return ChainVersionSummary(
        id=version_id,
        industry="半导体",
        version_no=version_no,
        label=None,
        status="success",
        model="gpt-4o",
        node_count=2,
        company_count=2,
        created_by="manual",
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


def _result() -> ChainAnalysisResult:
    return ChainAnalysisResult(nodes=[], edges=[], summary="s")


@pytest.mark.unit
class TestAnalyzeEndpoint:
    @patch("app.api.v1.chain.chain_service.analyze_and_persist")
    def test_analyze_success(self, mock_analyze, auth_client, user) -> None:
        mock_analyze.return_value = ChainAnalyzeResponse(
            version_id=1, version_no=1, status="success", result=_result()
        )
        response = auth_client.post(
            "/api/v1/chain/analyze", json={"industry": "半导体"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["versionId"] == 1
        assert data["result"]["summary"] == "s"
        assert mock_analyze.call_args.kwargs["user_id"] == user.id

    @patch("app.api.v1.chain.chain_service.analyze_and_persist")
    def test_analyze_llm_not_configured(self, mock_analyze, auth_client) -> None:
        mock_analyze.side_effect = LLMConfigNotConfiguredError("未配置默认 LLM")
        response = auth_client.post(
            "/api/v1/chain/analyze", json={"industry": "半导体"}
        )
        assert response.status_code == 500

    @patch("app.api.v1.chain.chain_service.analyze_and_persist")
    def test_analyze_failed(self, mock_analyze, auth_client) -> None:
        mock_analyze.side_effect = ChainAnalysisFailedError("llm timeout")
        response = auth_client.post(
            "/api/v1/chain/analyze", json={"industry": "半导体"}
        )
        assert response.status_code == 500


@pytest.mark.unit
class TestVersionEndpoints:
    @patch("app.api.v1.chain.chain_service.get_latest_detail")
    def test_get_latest(self, mock_latest, auth_client, user) -> None:
        mock_latest.return_value = ChainVersionDetail(
            version=_summary(), result=_result()
        )
        response = auth_client.get("/api/v1/chain/半导体/latest")
        assert response.status_code == 200
        assert response.json()["version"]["versionNo"] == 1
        assert mock_latest.call_args.kwargs["user_id"] == user.id

    @patch("app.api.v1.chain.chain_service.get_latest_detail")
    def test_get_latest_not_found(self, mock_latest, auth_client) -> None:
        mock_latest.return_value = None
        response = auth_client.get("/api/v1/chain/半导体/latest")
        assert response.status_code == 404

    @patch("app.api.v1.chain.chain_service.list_versions")
    def test_list_versions(self, mock_list, auth_client, user) -> None:
        mock_list.return_value = [_summary(2, 2), _summary(1, 1)]
        response = auth_client.get("/api/v1/chain/半导体/versions")
        assert response.status_code == 200
        assert [item["versionNo"] for item in response.json()] == [2, 1]
        assert mock_list.call_args.kwargs["user_id"] == user.id

    @patch("app.api.v1.chain.chain_service.get_version_detail")
    def test_get_version(self, mock_get, auth_client, user) -> None:
        mock_get.return_value = ChainVersionDetail(
            version=_summary(), result=_result()
        )
        response = auth_client.get("/api/v1/chain/versions/1")
        assert response.status_code == 200
        assert mock_get.call_args.kwargs["user_id"] == user.id

    @patch("app.api.v1.chain.chain_service.get_version_detail")
    def test_get_version_not_found(self, mock_get, auth_client) -> None:
        mock_get.return_value = None
        response = auth_client.get("/api/v1/chain/versions/99")
        assert response.status_code == 404

    @patch("app.api.v1.chain.chain_service.compare_versions")
    def test_compare(self, mock_compare, auth_client, user) -> None:
        mock_compare.return_value = ChainCompareResult(
            base_version=_summary(1, 1),
            target_version=_summary(2, 2),
            added_nodes=["封装测试"],
        )
        response = auth_client.get("/api/v1/chain/versions/compare?base_id=1&target_id=2")
        assert response.status_code == 200
        assert response.json()["addedNodes"] == ["封装测试"]
        assert mock_compare.call_args.kwargs["user_id"] == user.id

    @patch("app.api.v1.chain.chain_service.compare_versions")
    def test_compare_not_found(self, mock_compare, auth_client) -> None:
        mock_compare.return_value = None
        response = auth_client.get("/api/v1/chain/versions/compare?base_id=1&target_id=2")
        assert response.status_code == 404


@pytest.mark.unit
class TestDeleteVersionEndpoint:
    @patch("app.api.v1.chain.chain_service.delete_version")
    def test_delete_version_success(self, mock_delete, auth_client, user) -> None:
        mock_delete.return_value = True
        response = auth_client.delete("/api/v1/chain/versions/3")

        assert response.status_code == 204
        assert response.content == b""
        assert mock_delete.call_args.args[1] == 3
        assert mock_delete.call_args.kwargs["user_id"] == user.id

    @patch("app.api.v1.chain.chain_service.delete_version")
    def test_delete_version_not_found(self, mock_delete, auth_client) -> None:
        mock_delete.return_value = False
        response = auth_client.delete("/api/v1/chain/versions/99")

        assert response.status_code == 404

    def test_delete_version_requires_auth(self, client) -> None:
        response = client.delete("/api/v1/chain/versions/3")
        assert response.status_code in (401, 403)


@pytest.mark.unit
class TestIndustriesEndpoint:
    @patch("app.api.v1.chain.chain_service.list_industries")
    def test_list_industries(self, mock_list, auth_client, user) -> None:
        mock_list.return_value = ["半导体", "机器人", "新能源汽车"]
        response = auth_client.get("/api/v1/chain/industries")
        assert response.status_code == 200
        assert response.json() == ["半导体", "机器人", "新能源汽车"]
        assert mock_list.call_args.args[1] == user.id

    @patch("app.api.v1.chain.chain_service.list_industries")
    def test_list_industries_empty(self, mock_list, auth_client, user) -> None:
        mock_list.return_value = []
        response = auth_client.get("/api/v1/chain/industries")
        assert response.status_code == 200
        assert response.json() == []
        assert mock_list.call_args.args[1] == user.id


@pytest.mark.unit
class TestAlertsEndpoint:
    @patch("app.api.v1.chain.chain_service.list_alerts")
    def test_list_alerts(self, mock_list, auth_client) -> None:
        mock_list.return_value = [
            ChainAlertResponse(
                industry="半导体",
                alert_type="财报异动",
                severity=3,
                title="毛利率异动",
                description="环节毛利率同比 -6pct",
                affected_segments=["硅材料"],
                related_stock_codes=["600703"],
                signal_date=date(2026, 9, 4),
                created_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            )
        ]
        response = auth_client.get("/api/v1/chain/alerts?industry=半导体&days=30")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["alertType"] == "财报异动"
        assert data[0]["severity"] == 3
        assert data[0]["affectedSegments"] == ["硅材料"]
        assert data[0]["signalDate"].startswith("2026-09-04")
        assert mock_list.call_args.args[1] == "半导体"
        assert mock_list.call_args.kwargs["days"] == 30

    @patch("app.api.v1.chain.chain_service.list_alerts")
    def test_list_alerts_empty(self, mock_list, auth_client) -> None:
        mock_list.return_value = []
        response = auth_client.get("/api/v1/chain/alerts?industry=半导体")
        assert response.status_code == 200
        assert response.json() == []

    @patch("app.api.v1.chain.chain_service.list_alerts")
    def test_list_alerts_requires_industry(self, mock_list, auth_client) -> None:
        response = auth_client.get("/api/v1/chain/alerts")
        assert response.status_code == 422
        mock_list.assert_not_called()

    @patch("app.api.v1.chain.chain_service.list_alerts")
    def test_list_alerts_requires_auth(self, mock_list, client) -> None:
        response = client.get("/api/v1/chain/alerts?industry=半导体")
        assert response.status_code == 401
        mock_list.assert_not_called()
