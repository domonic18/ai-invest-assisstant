"""签名 sidecar 的 wire 契约。

协议形状说明：本契约是纯服务间内部协议（消费方仅 ``app/adapters/douyin/signer_client.py``），
且参数名须与抖音页面 SDK 的 protocol-native 形状一致（a_bogus/verifyFp/uifid 等），
故用 snake_case 而非 CamelModel——同 assistant 透传契约的例外逻辑。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignRequest(BaseModel):
    """签名请求：query 必须是调用方将要发送的精确字节序列。"""

    path: str
    query: str
    user_agent: str
    cookies: str


class SignResponse(BaseModel):
    """SDK 追加参数原样透传；user_agent 回显供调用方核对一致性。"""

    params: dict[str, str]
    user_agent: str


class HealthResponse(BaseModel):
    """永远可答：浏览器缺失也是 200（启动事实，不是 crash）。"""

    status: str = "ok"
    driver: str | None = None
    warm_slots: int = 0
    in_use: int = 0
    last_error: str | None = Field(default=None, max_length=300)
