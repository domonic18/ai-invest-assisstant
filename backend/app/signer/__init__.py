"""抖音页面签名 sidecar（独立 ASGI 服务，入口 ``app.signer.main:app``）。"""

from app.signer.settings import SignerSettings

__all__ = ["SignerSettings"]
