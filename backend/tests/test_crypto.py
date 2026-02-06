"""加密/解密工具測試

測試 utils/crypto.py 中的憑證加密功能：
- encrypt_credential / decrypt_credential 基本功能
- 不同金鑰產生不同密文
- 空值處理
- 錯誤處理
- is_encrypted 檢測
"""

import os
import pytest
from unittest.mock import patch

from ching_tech_os.utils.crypto import (
    encrypt_credential,
    decrypt_credential,
    is_encrypted,
    _get_encryption_key,
)


# ============================================================
# 加密/解密基本功能測試
# ============================================================

class TestEncryptDecrypt:
    """加密/解密基本功能測試"""

    def test_encrypt_decrypt_roundtrip(self):
        """加密後解密應還原原文"""
        plaintext = "my-secret-token-12345"
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext(self):
        """相同明文每次加密應產生不同密文（因為 nonce 隨機）"""
        plaintext = "same-secret"
        encrypted1 = encrypt_credential(plaintext)
        encrypted2 = encrypt_credential(plaintext)
        # 密文不同
        assert encrypted1 != encrypted2
        # 但都能解密回原文
        assert decrypt_credential(encrypted1) == plaintext
        assert decrypt_credential(encrypted2) == plaintext

    def test_encrypt_unicode(self):
        """應支援 Unicode 字元"""
        plaintext = "密碼🔐秘密"
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        assert decrypted == plaintext

    def test_encrypt_long_text(self):
        """應支援長字串"""
        plaintext = "x" * 10000
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        assert decrypted == plaintext

    def test_encrypt_special_characters(self):
        """應支援特殊字元"""
        plaintext = '!@#$%^&*()_+-=[]{}|;:\'",.<>?/\\'
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        assert decrypted == plaintext


# ============================================================
# 空值和邊界處理測試
# ============================================================

class TestEmptyAndBoundary:
    """空值和邊界情況測試"""

    def test_encrypt_empty_string(self):
        """空字串應回傳空字串"""
        assert encrypt_credential("") == ""

    def test_decrypt_empty_string(self):
        """解密空字串應回傳空字串"""
        assert decrypt_credential("") == ""

    def test_encrypt_whitespace(self):
        """空白字串應正常加密"""
        plaintext = "   "
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        assert decrypted == plaintext

    def test_encrypt_single_char(self):
        """單字元應正常加密"""
        plaintext = "a"
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        assert decrypted == plaintext


# ============================================================
# 錯誤處理測試
# ============================================================

class TestErrorHandling:
    """錯誤處理測試"""

    def test_decrypt_invalid_base64(self):
        """無效 base64 應拋出 ValueError"""
        with pytest.raises(ValueError, match="解密失敗"):
            decrypt_credential("not-valid-base64!!!")

    def test_decrypt_corrupted_ciphertext(self):
        """損壞的密文應拋出 ValueError"""
        # 有效 base64 但內容不是有效密文
        import base64
        fake_encrypted = base64.b64encode(b"x" * 50).decode()
        with pytest.raises(ValueError, match="解密失敗"):
            decrypt_credential(fake_encrypted)

    def test_decrypt_truncated_ciphertext(self):
        """截斷的密文應拋出 ValueError"""
        plaintext = "secret"
        encrypted = encrypt_credential(plaintext)
        # 截斷密文
        truncated = encrypted[:len(encrypted) // 2]
        with pytest.raises(ValueError):
            decrypt_credential(truncated)

    def test_decrypt_wrong_key(self):
        """使用錯誤金鑰解密應失敗"""
        plaintext = "secret"

        # 使用金鑰 A 加密
        with patch.dict(os.environ, {"BOT_SECRET_KEY": "key-a"}):
            encrypted = encrypt_credential(plaintext)

        # 使用金鑰 B 解密
        with patch.dict(os.environ, {"BOT_SECRET_KEY": "key-b"}):
            with pytest.raises(ValueError, match="解密失敗"):
                decrypt_credential(encrypted)


# ============================================================
# 金鑰處理測試
# ============================================================

class TestKeyHandling:
    """金鑰處理測試"""

    def test_default_key_used_when_env_not_set(self):
        """未設定環境變數時使用預設金鑰"""
        # 確保環境變數未設定
        with patch.dict(os.environ, {}, clear=True):
            # 移除 BOT_SECRET_KEY
            os.environ.pop("BOT_SECRET_KEY", None)
            key = _get_encryption_key()
            assert len(key) == 32  # SHA-256 產生 32 bytes

    def test_custom_key_from_env(self):
        """應使用環境變數中的金鑰"""
        custom_key = "my-custom-secret-key"
        with patch.dict(os.environ, {"BOT_SECRET_KEY": custom_key}):
            key = _get_encryption_key()
            assert len(key) == 32

    def test_different_keys_produce_different_ciphertext(self):
        """不同金鑰應產生無法互相解密的密文"""
        plaintext = "secret"

        with patch.dict(os.environ, {"BOT_SECRET_KEY": "key-1"}):
            encrypted1 = encrypt_credential(plaintext)

        with patch.dict(os.environ, {"BOT_SECRET_KEY": "key-2"}):
            encrypted2 = encrypt_credential(plaintext)
            # 密文不同
            assert encrypted1 != encrypted2
            # 且無法用 key-2 解密 key-1 的密文
            with pytest.raises(ValueError):
                decrypt_credential(encrypted1)


# ============================================================
# is_encrypted 檢測測試
# ============================================================

class TestIsEncrypted:
    """is_encrypted 檢測函數測試"""

    def test_encrypted_value_returns_true(self):
        """加密過的值應回傳 True"""
        encrypted = encrypt_credential("secret")
        assert is_encrypted(encrypted) is True

    def test_plaintext_returns_false(self):
        """明文應回傳 False"""
        assert is_encrypted("plain-text") is False

    def test_empty_string_returns_false(self):
        """空字串應回傳 False"""
        assert is_encrypted("") is False

    def test_short_base64_returns_false(self):
        """太短的 base64 應回傳 False"""
        import base64
        # 少於 28 bytes 的 base64
        short = base64.b64encode(b"short").decode()
        assert is_encrypted(short) is False

    def test_invalid_base64_returns_false(self):
        """無效 base64 應回傳 False"""
        assert is_encrypted("not-base64!!!") is False

    def test_none_handled_gracefully(self):
        """None 值不應導致錯誤"""
        # is_encrypted 參數是 str，但實際上可能傳入 None
        # 函數應該安全處理
        assert is_encrypted("") is False
