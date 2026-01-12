"""使用者功能權限系統

提供：
- 預設權限常數
- 權限檢查函數
- 權限合併邏輯
"""

import logging
from typing import Any

from ..config import settings
from ..database import get_connection

logger = logging.getLogger(__name__)


# ============================================================
# 預設權限常數
# ============================================================

# 應用程式預設權限
# True = 預設開放，False = 預設關閉（需管理員開放）
DEFAULT_APP_PERMISSIONS: dict[str, bool] = {
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
}

# 知識庫預設權限
DEFAULT_KNOWLEDGE_PERMISSIONS: dict[str, bool] = {
    "global_write": False,      # 預設關閉，需管理員開放
    "global_delete": False,     # 預設關閉，需管理員開放
}

# 完整預設權限結構
DEFAULT_PERMISSIONS: dict[str, dict[str, bool]] = {
    "apps": DEFAULT_APP_PERMISSIONS.copy(),
    "knowledge": DEFAULT_KNOWLEDGE_PERMISSIONS.copy(),
}

# 應用程式 ID 對應的顯示名稱
APP_DISPLAY_NAMES: dict[str, str] = {
    "file-manager": "檔案管理",
    "terminal": "終端機",
    "code-editor": "VSCode",
    "project-management": "專案管理",
    "ai-assistant": "AI 助手",
    "prompt-editor": "Prompt 編輯器",
    "agent-settings": "Agent 設定",
    "ai-log": "AI Log",
    "knowledge-base": "知識庫",
    "linebot": "Line Bot",
    "settings": "系統設定",
}


# ============================================================
# 權限檢查函數
# ============================================================

def is_admin(username: str) -> bool:
    """檢查是否為管理員

    管理員帳號由環境變數 ADMIN_USERNAME 設定
    """
    return username == settings.admin_username


def get_full_permissions() -> dict[str, dict[str, bool]]:
    """取得完整權限（所有權限都開啟）

    用於管理員帳號
    """
    return {
        "apps": {app_id: True for app_id in DEFAULT_APP_PERMISSIONS},
        "knowledge": {perm: True for perm in DEFAULT_KNOWLEDGE_PERMISSIONS},
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """深度合併兩個 dict

    override 中的值會覆蓋 base 中的值
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_user_permissions(preferences: dict | None) -> dict[str, dict[str, bool]]:
    """取得使用者權限（合併預設值）

    Args:
        preferences: 使用者的 preferences JSONB 欄位

    Returns:
        合併後的權限結構
    """
    if preferences is None:
        return DEFAULT_PERMISSIONS.copy()

    user_perms = preferences.get("permissions", {})
    return deep_merge(DEFAULT_PERMISSIONS.copy(), user_perms)


def get_user_permissions_for_admin(username: str, preferences: dict | None) -> dict[str, dict[str, bool]]:
    """取得使用者權限，管理員返回完整權限

    Args:
        username: 使用者帳號
        preferences: 使用者的 preferences JSONB 欄位

    Returns:
        權限結構
    """
    if is_admin(username):
        return get_full_permissions()
    return get_user_permissions(preferences)


def check_app_permission(username: str, preferences: dict | None, app_id: str) -> bool:
    """檢查應用程式權限

    Args:
        username: 使用者帳號
        preferences: 使用者的 preferences JSONB 欄位
        app_id: 應用程式 ID

    Returns:
        是否有權限使用該應用程式
    """
    if is_admin(username):
        return True

    perms = get_user_permissions(preferences)
    return perms.get("apps", {}).get(app_id, True)


def check_knowledge_permission(
    username: str,
    preferences: dict | None,
    knowledge_owner: str | None,
    knowledge_scope: str,
    action: str,
) -> bool:
    """檢查知識庫權限（同步版本，不支援專案知識）

    Args:
        username: 使用者帳號
        preferences: 使用者的 preferences JSONB 欄位
        knowledge_owner: 知識的擁有者（None 表示全域知識）
        knowledge_scope: 知識的範圍（global 或 personal）
        action: 操作類型（read、write、delete）

    Returns:
        是否有權限執行該操作

    注意：專案知識（scope=project）請使用 check_knowledge_permission_async
    """
    # 管理員擁有所有權限
    if is_admin(username):
        return True

    # 擁有全域權限的使用者可以編輯/刪除任何知識（用於管理目的）
    perms = get_user_permissions(preferences)
    knowledge_perms = perms.get("knowledge", {})

    if action == "write" and knowledge_perms.get("global_write", False):
        return True
    if action == "delete" and knowledge_perms.get("global_delete", False):
        return True

    # 個人知識：擁有者完全控制
    if knowledge_scope == "personal" and knowledge_owner == username:
        return True

    # 全域知識：依權限設定
    if knowledge_scope == "global":
        if action == "read":
            return True  # 全域知識所有人可讀
        # write/delete 已在上方全域權限檢查處理
        return False

    # 專案知識：同步版本不支援，需使用 async 版本
    if knowledge_scope == "project":
        if action == "read":
            return True  # 專案知識所有人可讀
        # write/delete 需要 async 檢查專案成員，這裡拒絕
        return False

    # 其他情況：拒絕
    return False


async def is_project_member(user_id: int | None, project_id: str | None) -> bool:
    """檢查使用者是否為專案成員

    Args:
        user_id: CTOS 使用者 ID
        project_id: 專案 UUID

    Returns:
        是否為該專案的成員
    """
    if not user_id or not project_id:
        return False

    try:
        from uuid import UUID as UUID_type
        async with get_connection() as conn:
            result = await conn.fetchval(
                """
                SELECT 1 FROM project_members
                WHERE project_id = $1 AND user_id = $2
                LIMIT 1
                """,
                UUID_type(project_id),
                user_id,
            )
            return result is not None
    except Exception as e:
        logger.error(f"檢查專案成員權限時發生錯誤: {e}")
        return False


async def check_knowledge_permission_async(
    username: str,
    preferences: dict | None,
    knowledge_owner: str | None,
    knowledge_scope: str,
    action: str,
    user_id: int | None = None,
    project_id: str | None = None,
) -> bool:
    """檢查知識庫權限（async 版本，支援專案知識）

    Args:
        username: 使用者帳號
        preferences: 使用者的 preferences JSONB 欄位
        knowledge_owner: 知識的擁有者（None 表示全域知識）
        knowledge_scope: 知識的範圍（global、personal 或 project）
        action: 操作類型（read、write、delete）
        user_id: CTOS 使用者 ID（檢查專案成員時需要）
        project_id: 專案 UUID（專案知識時需要）

    Returns:
        是否有權限執行該操作
    """
    # 管理員擁有所有權限
    if is_admin(username):
        return True

    # 擁有全域權限的使用者可以編輯/刪除任何知識（用於管理目的）
    perms = get_user_permissions(preferences)
    knowledge_perms = perms.get("knowledge", {})

    if action == "write" and knowledge_perms.get("global_write", False):
        return True
    if action == "delete" and knowledge_perms.get("global_delete", False):
        return True

    # 個人知識：擁有者完全控制
    if knowledge_scope == "personal" and knowledge_owner == username:
        return True

    # 全域知識：依權限設定
    if knowledge_scope == "global":
        if action == "read":
            return True  # 全域知識所有人可讀
        # write/delete 已在上方全域權限檢查處理
        return False

    # 專案知識：專案成員可以編輯/刪除
    if knowledge_scope == "project":
        if action == "read":
            return True  # 專案知識所有人可讀

        # 檢查是否為專案成員
        if await is_project_member(user_id, project_id):
            return True
        return False

    # 其他情況：拒絕
    return False


def get_default_permissions() -> dict[str, dict[str, bool]]:
    """取得預設權限設定

    用於前端顯示和 API 回應
    """
    # 深拷貝以避免外部修改影響原始值
    return {
        "apps": DEFAULT_APP_PERMISSIONS.copy(),
        "knowledge": DEFAULT_KNOWLEDGE_PERMISSIONS.copy(),
    }


def get_app_display_names() -> dict[str, str]:
    """取得應用程式顯示名稱對照表"""
    return APP_DISPLAY_NAMES.copy()
