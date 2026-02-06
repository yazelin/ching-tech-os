"""憑證加密/解密工具

使用 AES-256-GCM 對稱加密儲存敏感資料（如 Line Bot Channel Secret、Access Token）。
"""

import base64
import hashlib
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_encryption_key() -> bytes:
    """取得加密金鑰

    從環境變數 BOT_SECRET_KEY 讀取。
    如果未設定，使用預設金鑰（僅限開發環境）。
    """
    key_str = os.getenv("BOT_SECRET_KEY", "")
    if not key_str:
        # 開發環境預設金鑰（生產環境必須設定 BOT_SECRET_KEY）
        key_str = "ching-tech-os-default-dev-key-2024"

    # 使用 SHA-256 產生固定長度的金鑰（32 bytes = 256 bits）
    return hashlib.sha256(key_str.encode()).digest()


def encrypt_credential(plaintext: str) -> str:
    """加密憑證

    使用 AES-256-GCM 加密，回傳 base64 編碼的密文。
    格式：base64(nonce + ciphertext + tag)

    Args:
        plaintext: 要加密的明文

    Returns:
        加密後的 base64 字串
    """
    if not plaintext:
        return ""

    key = _get_encryption_key()
    aesgcm = AESGCM(key)

    # 產生 12 bytes 的 nonce（GCM 建議值）
    nonce = secrets.token_bytes(12)

    # 加密
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # nonce + ciphertext（包含 tag）
    encrypted = nonce + ciphertext

    return base64.b64encode(encrypted).decode("ascii")


def decrypt_credential(encrypted: str) -> str:
    """解密憑證

    Args:
        encrypted: base64 編碼的密文

    Returns:
        解密後的明文

    Raises:
        ValueError: 解密失敗
    """
    if not encrypted:
        return ""

    try:
        key = _get_encryption_key()
        aesgcm = AESGCM(key)

        # 解碼 base64
        data = base64.b64decode(encrypted.encode("ascii"))

        # 分離 nonce 和 ciphertext
        nonce = data[:12]
        ciphertext = data[12:]

        # 解密
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode("utf-8")
    except Exception as e:
        raise ValueError(f"解密失敗: {e}") from e


def is_encrypted(value: str) -> bool:
    """檢查值是否為加密格式

    簡易判斷：base64 格式且長度大於等於最小加密長度（nonce 12 + tag 16 = 28 bytes base64）
    """
    if not value:
        return False

    try:
        decoded = base64.b64decode(value.encode("ascii"))
        # 最小長度：12 (nonce) + 16 (tag) = 28 bytes
        return len(decoded) >= 28
    except Exception:
        return False
