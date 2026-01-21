"""為現有租戶管理員初始化 App 權限

Revision ID: 059
Revises: 058
Create Date: 2026-01-21

初始化現有租戶管理員的 permissions.apps 欄位為預設值。
這確保權限控制系統能正確套用到現有的租戶管理員。
"""

from alembic import op
from sqlalchemy import text
import json

# revision identifiers
revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None

# 租戶管理員預設 App 權限
DEFAULT_TENANT_ADMIN_APP_PERMISSIONS = {
    "file-manager": True,
    "terminal": False,          # 高風險，預設關閉
    "code-editor": False,       # 高風險，預設關閉
    "project-management": True,
    "ai-assistant": True,
    "prompt-editor": True,
    "agent-settings": True,
    "ai-log": True,
    "knowledge-base": True,
    "linebot": True,
    "settings": True,
    "inventory": True,
    "platform-admin": False,    # 永遠禁止
}

DEFAULT_TENANT_ADMIN_PERMISSIONS = {
    "apps": DEFAULT_TENANT_ADMIN_APP_PERMISSIONS,
    "knowledge": {
        "global_write": True,   # 租戶管理員預設可編輯全域知識
        "global_delete": True,  # 租戶管理員預設可刪除全域知識
    },
}


def upgrade() -> None:
    # 取得所有租戶管理員
    connection = op.get_bind()
    result = connection.execute(
        text("SELECT id, preferences FROM users WHERE role = 'tenant_admin'")
    )

    for row in result:
        user_id = row[0]
        preferences = row[1] or {}

        # 如果是字串，解析為 dict
        if isinstance(preferences, str):
            try:
                preferences = json.loads(preferences)
            except json.JSONDecodeError:
                preferences = {}

        # 如果尚未設定 permissions，初始化為預設值
        if "permissions" not in preferences or not preferences.get("permissions", {}).get("apps"):
            preferences["permissions"] = DEFAULT_TENANT_ADMIN_PERMISSIONS.copy()

            # 更新到資料庫
            connection.execute(
                text("UPDATE users SET preferences = CAST(:prefs AS jsonb) WHERE id = :user_id"),
                {"prefs": json.dumps(preferences), "user_id": user_id}
            )


def downgrade() -> None:
    # 不需要還原操作 - 權限資料保留即可
    pass
