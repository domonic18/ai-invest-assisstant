"""AdminStockService 股票管理契约测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.stock import AdminStockCreate, AdminStockUpdate
from app.services.admin.stocks import AdminStockService


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestAdminStockService:
    @pytest.fixture
    def service(self) -> AdminStockService:
        session = AsyncMock()
        session.add = MagicMock()
        return AdminStockService(session)

    @pytest.mark.asyncio
    async def test_list_stocks(self, service: AdminStockService) -> None:
        mock_stock = MagicMock()
        service.session.execute.return_value = _result_mock([mock_stock])
        service.session.scalar.return_value = 1

        items, total = await service.list_stocks()

        assert items == [mock_stock]
        assert total == 1

    @pytest.mark.asyncio
    async def test_create_stock(self, service: AdminStockService) -> None:
        data = AdminStockCreate(
            stock_code="000001",
            stock_name="平安银行",
            market="sz",
        )
        result = await service.create_stock(data)

        assert result.stock_code == "000001"
        service.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stock(self, service: AdminStockService) -> None:
        stock = MagicMock()
        service.session.get.return_value = stock

        result = await service.update_stock(
            1, AdminStockUpdate(stock_name="New Name")
        )

        assert result == stock
        assert stock.stock_name == "New Name"

    @pytest.mark.asyncio
    async def test_delete_stock(self, service: AdminStockService) -> None:
        stock = MagicMock()
        service.session.get.return_value = stock

        await service.delete_stock(1)

        service.session.delete.assert_awaited_once_with(stock)
