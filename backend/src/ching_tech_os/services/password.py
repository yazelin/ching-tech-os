"""密碼管理服務

提供密碼雜湊、驗證和安全相關功能
"""

import secrets
import string
import bcrypt


def hash_password(password: str) -> str:
    """
    使用 bcrypt 產生密碼雜湊

    Args:
        password: 明文密碼

    Returns:
        bcrypt 雜湊字串
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    驗證密碼是否正確

    Args:
        password: 明文密碼
        password_hash: bcrypt 雜湊字串

    Returns:
        密碼是否正確
    """
    try:
        password_bytes = password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def generate_temporary_password(length: int = 12) -> str:
    """
    產生隨機臨時密碼

    Args:
        length: 密碼長度（預設 12）

    Returns:
        隨機密碼字串（包含大小寫字母和數字）
    """
    # 確保至少包含一個大寫、一個小寫、一個數字
    password_chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]

    # 剩餘字元從所有允許的字元中隨機選取
    all_chars = string.ascii_letters + string.digits
    password_chars.extend(
        secrets.choice(all_chars) for _ in range(length - 3)
    )

    # 隨機打亂順序
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


def generate_reset_token(length: int = 64) -> str:
    """
    產生密碼重設 token

    Args:
        length: token 長度（預設 64）

    Returns:
        隨機 token 字串（URL safe）
    """
    return secrets.token_urlsafe(length)


def validate_password_strength(password: str, min_length: int = 8) -> tuple[bool, str | None]:
    """
    驗證密碼強度

    Args:
        password: 密碼
        min_length: 最小長度（預設 8）

    Returns:
        (是否通過, 錯誤訊息或 None)
    """
    if len(password) < min_length:
        return False, f"密碼需至少 {min_length} 個字元"

    # 可以在這裡新增更多規則，例如：
    # - 必須包含大小寫
    # - 必須包含數字
    # - 必須包含特殊字元

    return True, None
