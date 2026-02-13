"""password 模組單元測試。"""

from __future__ import annotations

from ching_tech_os.services.password import (
    generate_reset_token,
    generate_temporary_password,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_hash_and_verify_password_roundtrip() -> None:
    password = "Abcd1234"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_verify_password_handles_invalid_hash() -> None:
    assert verify_password("anything", "not-a-valid-bcrypt-hash") is False


def test_generate_temporary_password_contains_required_charsets() -> None:
    temp_password = generate_temporary_password(12)

    assert len(temp_password) == 12
    assert any(ch.isupper() for ch in temp_password)
    assert any(ch.islower() for ch in temp_password)
    assert any(ch.isdigit() for ch in temp_password)


def test_generate_temporary_password_with_minimum_length() -> None:
    temp_password = generate_temporary_password(3)

    assert len(temp_password) == 3
    assert any(ch.isupper() for ch in temp_password)
    assert any(ch.islower() for ch in temp_password)
    assert any(ch.isdigit() for ch in temp_password)


def test_generate_reset_token_and_password_strength_validation() -> None:
    token = generate_reset_token(16)
    assert isinstance(token, str)
    assert len(token) > 0

    ok, err = validate_password_strength("123", min_length=8)
    assert ok is False
    assert err == "密碼需至少 8 個字元"

    ok, err = validate_password_strength("Strong123", min_length=8)
    assert ok is True
    assert err is None
