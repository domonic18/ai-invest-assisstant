"""后台 CRUD 端点契约测试。"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """返回已绕过管理员认证并注入 mock session 的客户端。"""
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.role = "admin"

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_admin_user] = lambda: mock_user
    yield client, mock_session
    app.dependency_overrides.clear()


def _user_mock() -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.username = "tester"
    user.email = "test@example.com"
    user.role = "user"
    user.is_active = True
    user.last_login_at = None
    user.created_at = datetime(2024, 1, 1, 0, 0, 0)
    return user


def _stock_mock() -> MagicMock:
    stock = MagicMock()
    stock.id = 1
    stock.stock_code = "000001"
    stock.stock_name = "平安银行"
    stock.market = "sz"
    stock.industry_level_1 = None
    stock.industry_level_2 = None
    stock.industry_level_3 = None
    stock.listing_date = None
    stock.full_name = None
    stock.legal_person = None
    stock.website = None
    stock.registered_capital = None
    stock.business_scope = None
    stock.province = None
    stock.city = None
    stock.created_at = datetime(2024, 1, 1, 0, 0, 0)
    return stock


def _report_mock() -> MagicMock:
    report = MagicMock()
    report.id = 1
    report.file_path = "s3://reports/1.pdf"
    report.original_name = "report.pdf"
    report.file_type = "pdf"
    report.stock_code = "000001"
    report.stock_name = None
    report.report_date = date(2024, 1, 1)
    report.report_type = "年报"
    report.broker = "Broker"
    report.file_size = 1024
    report.md5_hash = None
    report.download_url = None
    report.download_count = 0
    report.created_at = datetime(2024, 1, 1, 0, 0, 0)
    return report


def _news_mock() -> MagicMock:
    news = MagicMock()
    news.id = 1
    news.stock_code = "000001"
    news.doc_type = "news"
    news.title = "News Title"
    news.summary = None
    news.content = None
    news.source = None
    news.source_url = None
    news.publish_date = None
    news.sentiment = None
    news.keywords = None
    news.industry_tags = None
    news.elasticsearch_doc_id = None
    news.extra = {}
    news.created_at = datetime(2024, 1, 1, 0, 0, 0)
    return news


def _task_mock() -> MagicMock:
    task = MagicMock()
    task.id = 1
    task.task_name = "kline"
    task.task_type = "scheduled"
    task.source = "tushare"
    task.schedule = "0 9 * * *"
    task.is_active = True
    task.queue = None
    task.last_run_at = None
    task.last_status = "pending"
    task.last_error = None
    task.created_at = datetime(2024, 1, 1, 0, 0, 0)
    task.updated_at = datetime(2024, 1, 1, 0, 0, 0)
    return task


@pytest.mark.unit
class TestAdminUserEndpoints:
    @patch("app.api.v1.admin.users.AdminUserService")
    def test_list_users(self, mock_service, admin_client) -> None:
        mock_service.return_value.list_users = AsyncMock(
            return_value=([_user_mock()], 1)
        )
        client, _ = admin_client
        response = client.get("/api/v1/admin/users/")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    @patch("app.api.v1.admin.users.AdminUserService")
    def test_create_user(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_user = AsyncMock(return_value=_user_mock())
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/users/",
            json={
                "username": "tester",
                "email": "test@example.com",
                "password": "secret123",
            },
        )
        assert response.status_code == 201

    def test_get_user(self, admin_client) -> None:
        client, session = admin_client
        session.get.return_value = _user_mock()
        response = client.get("/api/v1/admin/users/1")
        assert response.status_code == 200
        assert response.json()["username"] == "tester"

    @patch("app.api.v1.admin.users.AdminUserService")
    def test_update_user(self, mock_service, admin_client) -> None:
        mock_service.return_value.update_user = AsyncMock(return_value=_user_mock())
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/users/1",
            json={"role": "admin"},
        )
        assert response.status_code == 200

    @patch("app.api.v1.admin.users.AdminUserService")
    def test_delete_user(self, mock_service, admin_client) -> None:
        mock_service.return_value.delete_user = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.delete("/api/v1/admin/users/1")
        assert response.status_code == 204

    @patch("app.api.v1.admin.users.AdminUserService")
    def test_reset_password(self, mock_service, admin_client) -> None:
        mock_service.return_value.reset_password = AsyncMock(return_value=_user_mock())
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/users/1/reset-password",
            json={"password": "newpassword"},
        )
        assert response.status_code == 200


@pytest.mark.unit
class TestAdminStockEndpoints:
    @patch("app.api.v1.admin.stocks.AdminStockService")
    def test_list_stocks(self, mock_service, admin_client) -> None:
        mock_service.return_value.list_stocks = AsyncMock(
            return_value=([_stock_mock()], 1)
        )
        client, _ = admin_client
        response = client.get("/api/v1/admin/stocks/")
        assert response.status_code == 200
        assert response.json()["items"][0]["stock_code"] == "000001"

    @patch("app.api.v1.admin.stocks.AdminStockService")
    def test_create_stock(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_stock = AsyncMock(return_value=_stock_mock())
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/stocks/",
            json={
                "stock_code": "000001",
                "stock_name": "平安银行",
                "market": "sz",
            },
        )
        assert response.status_code == 201

    def test_get_stock(self, admin_client) -> None:
        client, session = admin_client
        session.get.return_value = _stock_mock()
        response = client.get("/api/v1/admin/stocks/1")
        assert response.status_code == 200

    @patch("app.api.v1.admin.stocks.AdminStockService")
    def test_update_stock(self, mock_service, admin_client) -> None:
        mock_service.return_value.update_stock = AsyncMock(return_value=_stock_mock())
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/stocks/1",
            json={"stock_name": "New Name"},
        )
        assert response.status_code == 200

    @patch("app.api.v1.admin.stocks.AdminStockService")
    def test_delete_stock(self, mock_service, admin_client) -> None:
        mock_service.return_value.delete_stock = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.delete("/api/v1/admin/stocks/1")
        assert response.status_code == 204


@pytest.mark.unit
class TestAdminReportEndpoints:
    @patch("app.api.v1.admin.reports.AdminReportService")
    def test_list_reports(self, mock_service, admin_client) -> None:
        mock_service.return_value.list_reports = AsyncMock(
            return_value=([(_report_mock(), "平安银行")], 1)
        )
        client, _ = admin_client
        response = client.get("/api/v1/admin/reports/")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["stock_name"] == "平安银行"

    @patch("app.api.v1.admin.reports.AdminReportService")
    def test_create_report(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_report = AsyncMock(return_value=_report_mock())
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/reports/",
            json={
                "file_path": "s3://reports/1.pdf",
                "file_type": "pdf",
                "stock_code": "000001",
            },
        )
        assert response.status_code == 201

    def test_get_report(self, admin_client) -> None:
        client, session = admin_client
        session.get.return_value = _report_mock()
        response = client.get("/api/v1/admin/reports/1")
        assert response.status_code == 200

    @patch("app.api.v1.admin.reports.AdminReportService")
    def test_update_report(self, mock_service, admin_client) -> None:
        mock_service.return_value.update_report = AsyncMock(return_value=_report_mock())
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/reports/1",
            json={"broker": "New Broker"},
        )
        assert response.status_code == 200

    @patch("app.api.v1.admin.reports.AdminReportService")
    def test_delete_report(self, mock_service, admin_client) -> None:
        mock_service.return_value.delete_report = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.delete("/api/v1/admin/reports/1")
        assert response.status_code == 204


@pytest.mark.unit
class TestAdminNewsEndpoints:
    @patch("app.api.v1.admin.news.AdminNewsService")
    def test_list_news(self, mock_service, admin_client) -> None:
        mock_service.return_value.list_news = AsyncMock(
            return_value=([_news_mock()], 1)
        )
        client, _ = admin_client
        response = client.get("/api/v1/admin/news/")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    @patch("app.api.v1.admin.news.AdminNewsService")
    def test_create_news(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_news = AsyncMock(return_value=_news_mock())
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/news/",
            json={
                "doc_type": "news",
                "title": "News Title",
            },
        )
        assert response.status_code == 201

    def test_get_news(self, admin_client) -> None:
        client, session = admin_client
        session.get.return_value = _news_mock()
        response = client.get("/api/v1/admin/news/1")
        assert response.status_code == 200

    @patch("app.api.v1.admin.news.AdminNewsService")
    def test_update_news(self, mock_service, admin_client) -> None:
        mock_service.return_value.update_news = AsyncMock(return_value=_news_mock())
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/news/1",
            json={"title": "Updated"},
        )
        assert response.status_code == 200

    @patch("app.api.v1.admin.news.AdminNewsService")
    def test_delete_news(self, mock_service, admin_client) -> None:
        mock_service.return_value.delete_news = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.delete("/api/v1/admin/news/1")
        assert response.status_code == 204


@pytest.mark.unit
class TestAdminTaskEndpoints:
    @patch("app.api.v1.admin.tasks.AdminTaskService")
    def test_list_tasks(self, mock_service, admin_client) -> None:
        mock_service.return_value.list_tasks = AsyncMock(
            return_value=([_task_mock()], 1)
        )
        client, _ = admin_client
        response = client.get("/api/v1/admin/tasks/")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    @patch("app.api.v1.admin.tasks.AdminTaskService")
    def test_create_task(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_task = AsyncMock(return_value=_task_mock())
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/tasks/",
            json={
                "task_name": "kline",
                "task_type": "scheduled",
                "source": "tushare",
            },
        )
        assert response.status_code == 201

    def test_get_task(self, admin_client) -> None:
        client, session = admin_client
        session.get.return_value = _task_mock()
        response = client.get("/api/v1/admin/tasks/1")
        assert response.status_code == 200

    @patch("app.api.v1.admin.tasks.AdminTaskService")
    def test_update_task(self, mock_service, admin_client) -> None:
        mock_service.return_value.update_task = AsyncMock(return_value=_task_mock())
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/tasks/1",
            json={"is_active": False},
        )
        assert response.status_code == 200

    @patch("app.api.v1.admin.tasks.AdminTaskService")
    def test_delete_task(self, mock_service, admin_client) -> None:
        mock_service.return_value.delete_task = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.delete("/api/v1/admin/tasks/1")
        assert response.status_code == 204

    @patch("app.api.v1.admin.tasks.dispatch_collector_task")
    @patch("app.api.v1.admin.tasks.AdminTaskService")
    def test_pause_resume_trigger_task(self, mock_service, mock_dispatch, admin_client) -> None:
        mock_service.return_value.pause_task = AsyncMock(return_value=_task_mock())
        mock_service.return_value.resume_task = AsyncMock(return_value=_task_mock())
        mock_service.return_value.trigger_task = AsyncMock(return_value=_task_mock())
        mock_dispatch.return_value = AsyncMock()
        client, _ = admin_client

        assert client.post("/api/v1/admin/tasks/1/pause").status_code == 200
        assert client.post("/api/v1/admin/tasks/1/resume").status_code == 200
        assert client.post("/api/v1/admin/tasks/1/trigger").status_code == 200
