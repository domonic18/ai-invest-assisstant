"""build_proxy_url 组装契约测试。"""

import pytest

from app.utils.proxy import build_proxy_url

pytestmark = pytest.mark.unit


def test_no_credentials() -> None:
    assert build_proxy_url("http", "175.27.167.123", 17890) == (
        "http://175.27.167.123:17890"
    )


def test_with_credentials() -> None:
    url = build_proxy_url("http", "proxy.example.com", 8080, "user", "pass")
    assert url == "http://user:pass@proxy.example.com:8080"


def test_username_only() -> None:
    url = build_proxy_url("socks5", "127.0.0.1", 1080, "user")
    assert url == "socks5://user@127.0.0.1:1080"


def test_special_characters_are_quoted() -> None:
    url = build_proxy_url("http", "p.example.com", 8080, "u@ser", "p:ass/w?rd")
    assert url == "http://u%40ser:p%3Aass%2Fw%3Frd@p.example.com:8080"
