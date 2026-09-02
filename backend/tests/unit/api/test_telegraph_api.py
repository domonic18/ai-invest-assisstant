"""财联社电报查询 API 端点与 HTML 剥离测试。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.telegraph import TelegraphResponse, strip_html


def _item_mock(**overrides: object) -> MagicMock:
    item = MagicMock()
    item.cls_msg_id = 1899921
    item.title = "快讯标题"
    item.content = "<p>宁德时代获机构增持</p>"
    item.category = "公司"
    item.importance = 3
    item.shared = -1
    item.stock_codes = ["sz300750"]
    item.publish_time = datetime(2026, 9, 2, 7, 0, tzinfo=timezone.utc)
    for key, value in overrides.items():
        setattr(item, key, value)
    return item


@pytest.mark.unit
class TestStripHtml:
    def test_strips_tags_and_unescapes_entities(self) -> None:
        assert (
            strip_html("<p>正文第一段</p><p>第二段 &amp; 补充</p>")
            == "正文第一段第二段 & 补充"
        )

    def test_plain_text_passthrough(self) -> None:
        assert strip_html("纯文本") == "纯文本"

    def test_none_and_empty(self) -> None:
        assert strip_html(None) is None
        assert strip_html("") is None
        assert strip_html("<br/>  ") is None

    def test_response_validator_applies(self) -> None:
        response = TelegraphResponse.model_validate(_item_mock())
        assert response.content == "宁德时代获机构增持"
        assert response.title == "快讯标题"


@pytest.mark.unit
class TestTelegraphEndpoint:
    @patch(
        "app.api.v1.telegraph.telegraph_service.list_telegraph",
        new_callable=AsyncMock,
    )
    async def test_list_paginated(self, mock_list: AsyncMock, client) -> None:
        mock_list.return_value = ([_item_mock()], 42)
        response = client.get("/api/v1/telegraph", params={"page": 2, "page_size": 30})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 42
        assert data["page"] == 2
        assert data["page_size"] == 30
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["cls_msg_id"] == 1899921
        assert item["content"] == "宁德时代获机构增持"  # 已剥 HTML
        assert item["stock_codes"] == ["sz300750"]
        assert item["publish_time"] == "2026-09-02T07:00:00Z"
        mock_list.assert_awaited_once_with(
            mock_list.await_args.args[0],
            page=2,
            page_size=30,
            category=None,
            min_importance=None,
        )

    @patch(
        "app.api.v1.telegraph.telegraph_service.list_telegraph",
        new_callable=AsyncMock,
    )
    async def test_list_with_filters(self, mock_list: AsyncMock, client) -> None:
        mock_list.return_value = ([], 0)
        response = client.get(
            "/api/v1/telegraph",
            params={"category": "宏观", "min_importance": 2},
        )

        assert response.status_code == 200
        assert response.json()["items"] == []
        kwargs = mock_list.await_args.kwargs
        assert kwargs["category"] == "宏观"
        assert kwargs["min_importance"] == 2

    async def test_page_bounds(self, client) -> None:
        assert (
            client.get("/api/v1/telegraph", params={"page": 0}).status_code == 422
        )
        assert (
            client.get(
                "/api/v1/telegraph", params={"page_size": 101}
            ).status_code
            == 422
        )
