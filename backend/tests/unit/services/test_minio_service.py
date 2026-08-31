"""MinIOService 客户端构建契约测试：预签名回落、virtual-host 与 region/secure 传参。"""

from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.common import minio_service
from app.services.common.minio_service import MinIOService


def make_settings(**overrides: str | bool | None) -> Settings:
    values: dict[str, str | bool | None] = {
        "minio_endpoint": "minio:9000",
        "minio_access_key": "ak",
        "minio_secret_key": "sk",
        "minio_bucket": "invest-files",
        "minio_secure": False,
        "minio_region": "us-east-1",
        "minio_virtual_host": False,
        "minio_public_endpoint": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def build_service(**setting_overrides: str | bool | None) -> tuple[MinIOService, MagicMock]:
    settings = make_settings(**setting_overrides)
    with (
        patch.object(minio_service, "Minio") as mock_minio,
        patch.object(minio_service, "get_settings", return_value=settings),
    ):
        mock_minio.side_effect = lambda endpoint, **kwargs: MagicMock()
        service = MinIOService()
    return service, mock_minio


@pytest.mark.unit
class TestMinIOServiceClients:
    def test_presign_falls_back_to_main_client_when_public_endpoint_unset(self) -> None:
        """MINIO_PUBLIC_ENDPOINT 与主 endpoint 相同（生产 COS）时可省略整行配置。"""
        service, mock_minio = build_service()

        assert mock_minio.call_count == 1
        assert service._presign_client is service.client

    def test_presign_client_uses_public_endpoint_when_set(self) -> None:
        service, mock_minio = build_service(minio_public_endpoint="localhost:9002")

        assert mock_minio.call_count == 2
        assert mock_minio.call_args_list[0].args[0] == "minio:9000"
        assert mock_minio.call_args_list[1].args[0] == "localhost:9002"
        assert service._presign_client is not service.client

    def test_virtual_host_applies_to_both_clients(self) -> None:
        service, _ = build_service(
            minio_virtual_host=True,
            minio_public_endpoint="cos.ap-beijing.myqcloud.com",
        )

        main_client = cast(MagicMock, service.client)
        presign_client = cast(MagicMock, service._presign_client)
        main_client.enable_virtual_style_endpoint.assert_called_once()
        presign_client.enable_virtual_style_endpoint.assert_called_once()

    def test_no_virtual_host_by_default(self) -> None:
        service, _ = build_service()

        cast(MagicMock, service.client).enable_virtual_style_endpoint.assert_not_called()

    def test_region_and_secure_passed_to_client(self) -> None:
        _, mock_minio = build_service(minio_secure=True, minio_region="ap-beijing")

        kwargs = mock_minio.call_args.kwargs
        assert kwargs["secure"] is True
        assert kwargs["region"] == "ap-beijing"
