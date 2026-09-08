"""财联社电报查询 API 端点与 HTML 剥离测试。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_user
from app.main import app
from app.schemas.telegraph import TelegraphResponse, strip_html


def _item_mock(**overrides: Any) -> SimpleNamespace:
    item = SimpleNamespace(
        cls_msg_id=1899921,
        title="快讯标题",
        content="<p>宁德时代获机构增持</p>",
        category="公司",
        importance=3,
        shared=-1,
        stock_codes=["sz300750"],
        publish_time=datetime(2026, 9, 2, 7, 0, tzinfo=timezone.utc),
    )
    for key, value in overrides.items():
        setattr(item, key, value)
    return item


@pytest.fixture
def normal_user():
    return type(
        "User",
        (object,),
        {"id": 3, "username": "user", "role": "user", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, normal_user):
    app.dependency_overrides[get_current_user] = lambda: normal_user
    yield client
    app.dependency_overrides.clear()


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
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/v1/telegraph").status_code in (401, 403)

    @patch(
        "app.api.v1.telegraph.telegraph_service.enrich_and_respond",
        new_callable=AsyncMock,
    )
    @patch(
        "app.api.v1.telegraph.telegraph_service.list_telegraph",
        new_callable=AsyncMock,
    )
    async def test_list_paginated(
        self, mock_list: AsyncMock, mock_enrich: AsyncMock, auth_client
    ) -> None:
        scored_at = datetime(2026, 9, 2, 7, 5, tzinfo=timezone.utc)
        rows = [(_item_mock(), 82, scored_at)]
        mock_list.return_value = (rows, 42)
        mock_enrich.side_effect = telegraph_items_stub
        response = auth_client.get(
            "/api/v1/telegraph", params={"page": 2, "page_size": 30}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 42
        assert data["page"] == 2
        assert data["pageSize"] == 30
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["clsMsgId"] == 1899921
        assert item["content"] == "宁德时代获机构增持"  # 已剥 HTML
        assert item["stockCodes"] == ["sz300750"]
        assert item["publishTime"] == "2026-09-02T07:00:00Z"
        assert item["aiScore"] == 82
        assert item["aiScoredAt"] == "2026-09-02T07:05:00Z"
        mock_list.assert_awaited_once_with(
            mock_list.await_args.args[0],
            page=2,
            page_size=30,
            category=None,
            min_importance=None,
            min_ai_score=None,
            subscription_only=False,
            user_id=3,
        )

    @patch(
        "app.api.v1.telegraph.telegraph_service.enrich_and_respond",
        new_callable=AsyncMock,
    )
    @patch(
        "app.api.v1.telegraph.telegraph_service.list_telegraph",
        new_callable=AsyncMock,
    )
    async def test_list_with_filters(
        self, mock_list: AsyncMock, mock_enrich: AsyncMock, auth_client
    ) -> None:
        mock_list.return_value = ([], 0)
        mock_enrich.return_value = []
        response = auth_client.get(
            "/api/v1/telegraph",
            params={
                "category": "宏观",
                "min_importance": 2,
                "min_ai_score": 70,
                "subscription_only": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["items"] == []
        kwargs = mock_list.await_args.kwargs
        assert kwargs["category"] == "宏观"
        assert kwargs["min_importance"] == 2
        assert kwargs["min_ai_score"] == 70
        assert kwargs["subscription_only"] is True
        assert kwargs["user_id"] == 3

    async def test_page_bounds(self, auth_client) -> None:
        assert (
            auth_client.get("/api/v1/telegraph", params={"page": 0}).status_code
            == 422
        )
        assert (
            auth_client.get(
                "/api/v1/telegraph", params={"page_size": 101}
            ).status_code
            == 422
        )


def telegraph_items_stub(session: Any, rows: list, *, user_id: int) -> list[TelegraphResponse]:
    """enrich_and_respond 替身：直接走共享映射保持响应形状。"""
    from app.services.market import telegraph_service

    return telegraph_service.to_responses(rows)
