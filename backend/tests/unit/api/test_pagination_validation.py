"""分页参数校验契约测试：越界 page/page_size 统一 422（请求校验层拦截），而非 500。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_user
from app.main import app

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("url", "service_path"),
    [
        ("/api/v1/kline/000001?page=0", "app.services.market.get_kline_by_code"),
        ("/api/v1/fund-flow/?page=0", "app.services.market.get_fund_flow"),
        ("/api/v1/auction/000001?page=0", "app.services.market.get_auction_by_code"),
        ("/api/v1/research/?page=0", "app.api.v1.research.research_service.list_reports"),
        (
            "/api/v1/financial-reports/?page=-1",
            "app.api.v1.financial_report.financial_report_service.list_reports",
        ),
    ],
)
def test_invalid_page_returns_422(url: str, service_path: str, client) -> None:
    with patch(service_path, AsyncMock(return_value=([], 0))):
        response = client.get(url)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_dead_letters_invalid_page_returns_422(client) -> None:
    """死信列表为 admin 端点：覆盖认证后分页校验仍 422。"""
    admin = SimpleNamespace(id=1, username="admin", role="admin", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.get("/api/v1/admin/collector/dead-letters?page=0")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("url", "service_path"),
    [
        ("/api/v1/fund-flow/", "app.services.market.get_fund_flow"),
        ("/api/v1/research/", "app.api.v1.research.research_service.list_reports"),
        (
            "/api/v1/financial-reports/",
            "app.api.v1.financial_report.financial_report_service.list_reports",
        ),
    ],
)
def test_valid_pagination_passes(url: str, service_path: str, client) -> None:
    with patch(service_path, AsyncMock(return_value=([], 0))):
        response = client.get(url)
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("url", "service_path"),
    [
        ("/api/v1/kline/000001", "app.services.market.get_kline_by_code"),
        ("/api/v1/auction/000001", "app.services.market.get_auction_by_code"),
    ],
)
def test_valid_pagination_reaches_handler(url: str, service_path: str, client) -> None:
    """kline/auction 空数据返 404（handler 已执行）——证明合法参数未被校验层拦截。"""
    with patch(service_path, AsyncMock(return_value=([], 0))):
        response = client.get(url)
    assert response.status_code == 404


def test_page_size_over_limit_returns_422(client) -> None:
    with patch(
        "app.services.market.get_kline_by_code", AsyncMock(return_value=([], 0))
    ):
        response = client.get("/api/v1/kline/000001?page=1&page_size=101")
    assert response.status_code == 422
