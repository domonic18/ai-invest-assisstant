"""Unit tests for admin news service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.news_announcement import NewsAnnouncementCreate, NewsAnnouncementUpdate
from app.services.admin_news_service import AdminNewsService


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
        data = NewsAnnouncementCreate(
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

        result = await service.update_news(1, NewsAnnouncementUpdate(title="Updated"))

        assert result == news
        assert news.title == "Updated"

    @pytest.mark.asyncio
    async def test_delete_news(self, service: AdminNewsService) -> None:
        news = MagicMock()
        service.session.get.return_value = news

        await service.delete_news(1)

        service.session.delete.assert_awaited_once_with(news)
