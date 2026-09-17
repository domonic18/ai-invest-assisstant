"""AdminNewsService 新闻管理契约测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.news_document import NewsDocumentCreate, NewsDocumentUpdate
from app.services.admin.news import AdminNewsService


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestAdminNewsService:
    @pytest.fixture
    def service(self) -> AdminNewsService:
        session = AsyncMock()
        session.add = MagicMock()
        return AdminNewsService(session)

    @pytest.mark.asyncio
    async def test_list_news(self, service: AdminNewsService) -> None:
        mock_news = MagicMock()
        service.session.execute.return_value = _result_mock([mock_news])
        service.session.scalar.return_value = 1

        items, total = await service.list_news()

        assert items == [mock_news]
        assert total == 1

    @pytest.mark.asyncio
    async def test_create_news(self, service: AdminNewsService) -> None:
        data = NewsDocumentCreate(
            doc_type="news",
            title="Test News",
        )
        result = await service.create_news(data)

        assert result.title == "Test News"
        service.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_news(self, service: AdminNewsService) -> None:
        news = MagicMock()
        service.session.get.return_value = news

        result = await service.update_news(1, NewsDocumentUpdate(title="Updated"))

        assert result == news
        assert news.title == "Updated"

    @pytest.mark.asyncio
    async def test_delete_news(self, service: AdminNewsService) -> None:
        news = MagicMock()
        service.session.get.return_value = news

        await service.delete_news(1)

        service.session.delete.assert_awaited_once_with(news)

    @pytest.mark.asyncio
    async def test_flash_news_display_defaults_visible(
        self, service: AdminNewsService
    ) -> None:
        service.session.get.return_value = None
        assert await service.get_flash_news_display() is True

    @pytest.mark.asyncio
    async def test_flash_news_display_reads_setting(
        self, service: AdminNewsService
    ) -> None:
        service.session.get.return_value = SimpleNamespace(value=False)
        assert await service.get_flash_news_display() is False

    @pytest.mark.asyncio
    async def test_set_flash_news_display_inserts_and_commits(
        self, service: AdminNewsService
    ) -> None:
        service.session.get.return_value = None

        assert await service.set_flash_news_display(False) is False

        added = service.session.add.call_args.args[0]
        assert added.value is False
        service.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_flash_news_display_updates_existing(
        self, service: AdminNewsService
    ) -> None:
        row = SimpleNamespace(value=True)
        service.session.get.return_value = row

        assert await service.set_flash_news_display(False) is False
        assert row.value is False
        service.session.commit.assert_awaited_once()
