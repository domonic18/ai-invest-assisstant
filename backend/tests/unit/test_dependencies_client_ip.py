"""共享 client_ip 依赖测试：XFF 首跳优先、缺失回退直连地址（审计/限流正确性）。"""

import pytest
from fastapi import Request

from app.dependencies import client_ip

pytestmark = pytest.mark.unit


def _request(headers: dict[str, str] | None = None, host: str | None = "1.2.3.4") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "query_string": b"",
        "client": (host, 12345) if host else None,
    }
    return Request(scope)


def test_forwarded_for_first_hop_wins() -> None:
    req = _request({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
    assert client_ip(req) == "203.0.113.7"


def test_forwarded_for_whitespace_stripped() -> None:
    req = _request({"X-Forwarded-For": " 203.0.113.7 , 10.0.0.1"})
    assert client_ip(req) == "203.0.113.7"


def test_falls_back_to_direct_client() -> None:
    assert client_ip(_request()) == "1.2.3.4"


def test_no_client_and_no_header_returns_none() -> None:
    assert client_ip(_request(host=None)) is None
