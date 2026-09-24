"""API 契约测试共享 fixture。"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _skip_quota_precheck():
    """AI 端点配额预检与被测契约无关，统一打桩放行（gate 专项测试自行覆写）。"""
    with patch("app.services.quota.quota_service.precheck", AsyncMock()):
        yield
