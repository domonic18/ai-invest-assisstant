"""Tests for credential encryption utilities."""


import pytest

from app.utils.crypto import decrypt_token, encrypt_token, mask_token

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "a-32-byte-secret-key-for-tests!")


def test_encrypt_decrypt_roundtrip() -> None:
    original = "sk-test-api-key-12345"
    encrypted = encrypt_token(original)
    assert encrypted != original
    assert decrypt_token(encrypted) == original


def test_mask_token() -> None:
    token = "sk-abcdefghijklmnopqrstuvwxyz"
    assert mask_token(token) == f"sk-a{'*' * (len(token) - 8)}wxyz"
    assert mask_token("short") == "*****"
    assert mask_token("") == ""


def test_different_plaintexts_produce_different_ciphertexts() -> None:
    encrypted_a = encrypt_token("key-a")
    encrypted_b = encrypt_token("key-b")
    assert encrypted_a != encrypted_b
