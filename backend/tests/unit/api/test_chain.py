"""Unit tests for industry chain API endpoints."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.schemas.chain import (
    ChainAnalysisResult,
    ChainAnalyzeResponse,
    ChainCompareResult,
    ChainVersionDetail,
    ChainVersionSummary,
)
from app.services.chain_service import ChainAnalysisFailedError
from app.services.llm_config_service import LLMConfigNotConfiguredError


def _summary(version_id: int = 1, version_no: int = 1) -> ChainVersionSummary:
    return ChainVersionSummary(
        id=version_id,
        industry_level_1="半导体",
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
    def test_analyze_success(self, mock_analyze, client) -> None:
        mock_analyze.return_value = ChainAnalyzeResponse(
            version_id=1, version_no=1, status="success", result=_result()
        )
        response = client.post(
            "/api/v1/chain/analyze", json={"industry": "半导体"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version_id"] == 1
        assert data["result"]["summary"] == "s"

    @patch("app.api.v1.chain.chain_service.analyze_and_persist")
    def test_analyze_llm_not_configured(self, mock_analyze, client) -> None:
        mock_analyze.side_effect = LLMConfigNotConfiguredError("未配置默认 LLM")
        response = client.post(
            "/api/v1/chain/analyze", json={"industry": "半导体"}
        )
        assert response.status_code == 503

    @patch("app.api.v1.chain.chain_service.analyze_and_persist")
    def test_analyze_failed(self, mock_analyze, client) -> None:
        mock_analyze.side_effect = ChainAnalysisFailedError("llm timeout")
        response = client.post(
            "/api/v1/chain/analyze", json={"industry": "半导体"}
        )
        assert response.status_code == 502


@pytest.mark.unit
class TestVersionEndpoints:
    @patch("app.api.v1.chain.chain_service.get_latest_detail")
    def test_get_latest(self, mock_latest, client) -> None:
        mock_latest.return_value = ChainVersionDetail(
            version=_summary(), result=_result()
        )
        response = client.get("/api/v1/chain/半导体/latest")
        assert response.status_code == 200
        assert response.json()["version"]["version_no"] == 1

    @patch("app.api.v1.chain.chain_service.get_latest_detail")
    def test_get_latest_not_found(self, mock_latest, client) -> None:
        mock_latest.return_value = None
        response = client.get("/api/v1/chain/半导体/latest")
        assert response.status_code == 404

    @patch("app.api.v1.chain.chain_service.list_versions")
    def test_list_versions(self, mock_list, client) -> None:
        mock_list.return_value = [_summary(2, 2), _summary(1, 1)]
        response = client.get("/api/v1/chain/半导体/versions")
        assert response.status_code == 200
        assert [item["version_no"] for item in response.json()] == [2, 1]

    @patch("app.api.v1.chain.chain_service.get_version_detail")
    def test_get_version(self, mock_get, client) -> None:
        mock_get.return_value = ChainVersionDetail(
            version=_summary(), result=_result()
        )
        response = client.get("/api/v1/chain/versions/1")
        assert response.status_code == 200

    @patch("app.api.v1.chain.chain_service.get_version_detail")
    def test_get_version_not_found(self, mock_get, client) -> None:
        mock_get.return_value = None
        response = client.get("/api/v1/chain/versions/99")
        assert response.status_code == 404

    @patch("app.api.v1.chain.chain_service.compare_versions")
    def test_compare(self, mock_compare, client) -> None:
        mock_compare.return_value = ChainCompareResult(
            base_version=_summary(1, 1),
            target_version=_summary(2, 2),
            added_nodes=["封装测试"],
        )
        response = client.get("/api/v1/chain/versions/compare?base_id=1&target_id=2")
        assert response.status_code == 200
        assert response.json()["added_nodes"] == ["封装测试"]

    @patch("app.api.v1.chain.chain_service.compare_versions")
    def test_compare_not_found(self, mock_compare, client) -> None:
        mock_compare.return_value = None
        response = client.get("/api/v1/chain/versions/compare?base_id=1&target_id=2")
        assert response.status_code == 404
