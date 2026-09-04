"""基于 Fernet 对称加密的凭据加密工具。

加密密钥优先取 ``CREDENTIAL_ENCRYPTION_KEY``，为空时回退到 ``SECRET_KEY``
以便开发环境使用。生产环境（``DEBUG=False``）缺少专用凭据密钥时只告警一次：
JWT 密钥泄露不应波及已存储的凭据。
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings

_jwt_fallback_warned = False


def _load_fernet() -> Fernet:
    """加载 Fernet 实例，从配置的密钥派生加密密钥。"""
    global _jwt_fallback_warned

    settings = get_settings()
    secret = settings.credential_encryption_key
    if not secret:
        secret = settings.secret_key
        if secret and not settings.debug and not _jwt_fallback_warned:
            # 延迟导入，避免循环依赖问题。
            import structlog

            logger = structlog.get_logger()
            logger.warning(
                "credential_encryption_key_missing",
                message=(
                    "Production environment is missing CREDENTIAL_ENCRYPTION_KEY; "
                    "falling back to SECRET_KEY. Configure a dedicated encryption key "
                    "and re-encrypt stored credentials."
                ),
            )
            _jwt_fallback_warned = True
    if not secret:
        raise RuntimeError(
            "No encryption key available: set CREDENTIAL_ENCRYPTION_KEY or SECRET_KEY"
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_token(plain: str) -> str:
    """加密明文字符串并返回 base64 编码的 token。"""
    return _load_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_token(cipher: str) -> str:
    """解密 base64 编码的 token 并返回明文字符串。"""
    return _load_fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")


def mask_token(token: str) -> str:
    """掩码展示 token，保留前 4 位与后 4 位。"""
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
