"""使用者相關資料模型"""

from datetime import datetime
from pydantic import BaseModel


class UserInfo(BaseModel):
    """使用者資訊"""

    id: int
    username: str
    display_name: str | None
    created_at: datetime
    last_login_at: datetime | None


class UpdateUserRequest(BaseModel):
    """更新使用者請求"""

    display_name: str | None = None
