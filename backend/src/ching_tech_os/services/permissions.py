"""使用者功能權限系統

提供：
- 預設權限常數
- 權限檢查函數
- 權限合併邏輯
- MCP 工具與 App 權限對應
- FastAPI 權限檢查 dependency
"""

import logging
from typing import Any, Callable

from fastapi import Depends, HTTPException, status

from ..database import get_connection

logger = logging.getLogger(__name__)


# ============================================================
# 已停用的 MCP 工具（已移除）
# ============================================================

# 原有的專案/廠商/物料管理工具已完全移除（遷移至 ERPNext）
# 保留此結構以供未來使用
DEPRECATED_TOOLS: dict[str, str] = {}

# ERPNext 工具對應指引（已整合至 AI Agent Prompt）
ERPNEXT_GUIDANCE: dict[str, str] = {}


def is_tool_deprecated(tool_name: str) -> tuple[bool, str | None]:
    """檢查工具是否已停用

    Args:
        tool_name: 工具名稱

    Returns:
        (is_deprecated, error_message): 若停用則返回 True 和錯誤訊息
    """
    # 目前無停用工具（已移除的工具不再存在）
    return False, None


# ============================================================
# MCP 工具與 App 權限對應
# ============================================================

# 工具名稱對應需要的 App 權限
# None 表示不需要特定權限（基礎功能）
# 注意：專案/廠商/物料管理工具已移除（遷移至 ERPNext）
TOOL_APP_MAPPING: dict[str, str | None] = {
    # 知識庫工具
    "search_knowledge": "knowledge-base",
    "get_knowledge_item": "knowledge-base",
    "update_knowledge_item": "knowledge-base",
    "delete_knowledge_item": "knowledge-base",
    "add_attachments_to_knowledge": "knowledge-base",
    "get_knowledge_attachments": "knowledge-base",
    "update_knowledge_attachment": "knowledge-base",
    "read_knowledge_attachment": "knowledge-base",
    "add_note": "knowledge-base",
    "add_note_with_attachments": "knowledge-base",

    # 檔案管理工具
    "search_nas_files": "file-manager",
    "get_nas_file_info": "file-manager",
    "read_document": "file-manager",
    "send_nas_file": "file-manager",
    "prepare_file_message": "file-manager",
    "convert_pdf_to_images": "file-manager",

    # 記憶管理工具
    "get_memories": "memory-manager",
    "add_memory": "memory-manager",
    "update_memory": "memory-manager",
    "delete_memory": "memory-manager",

    # 簡報/文件生成工具
    "generate_presentation": "md2ppt",
    "generate_md2ppt": "md2ppt",
    "generate_md2doc": "md2doc",

    # 列印前置處理工具
    "prepare_print_file": "printer",

    # 通用工具（不需要特定權限）
    "get_message_attachments": None,  # 基礎訊息功能
    "summarize_chat": None,           # 群組對話摘要
    "create_share_link": None,        # 分享連結（基礎功能）
    "share_knowledge_attachment": None,  # 分享知識庫附件（基礎功能）
    "download_web_image": None,       # 下載網路圖片
}

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
    "inventory-management": True,
    "vendor-management": True,
    "ai-assistant": True,
    "prompt-editor": True,
    "agent-settings": True,
    "ai-log": True,
    "knowledge-base": True,
    "linebot": True,
    "memory-manager": True,
    "share-manager": True,
    "tenant-admin": False,      # 管理功能，預設關閉
    "md2ppt": True,
    "md2doc": True,
    "printer": True,
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
    "inventory-management": "物料管理",
    "vendor-management": "廠商管理",
    "ai-assistant": "AI 助手",
    "prompt-editor": "Prompt 編輯器",
    "agent-settings": "Agent 設定",
    "ai-log": "AI Log",
    "knowledge-base": "知識庫",
    "linebot": "Line Bot",
    "memory-manager": "記憶管理",
    "share-manager": "分享管理",
    "tenant-admin": "租戶管理",
    "platform-admin": "平台管理",
    "md2ppt": "簡報生成",
    "md2doc": "文件生成",
    "printer": "列印",
    "settings": "系統設定",
}

# 租戶管理員預設權限
# 租戶管理員預設開啟大部分功能，但高風險功能預設關閉
DEFAULT_TENANT_ADMIN_APP_PERMISSIONS: dict[str, bool] = {
    "file-manager": True,
    "terminal": False,          # 高風險，預設關閉
    "code-editor": False,       # 高風險，預設關閉
    "project-management": True,
    "inventory-management": True,
    "vendor-management": True,
    "ai-assistant": True,
    "prompt-editor": True,
    "agent-settings": True,
    "ai-log": True,
    "knowledge-base": True,
    "linebot": True,
    "memory-manager": True,
    "share-manager": True,
    "tenant-admin": True,       # 租戶管理員可以管理租戶
    "platform-admin": False,    # 永遠禁止
    "md2ppt": True,
    "md2doc": True,
    "settings": True,
}

# 完整租戶管理員預設權限結構
DEFAULT_TENANT_ADMIN_PERMISSIONS: dict[str, dict[str, bool]] = {
    "apps": DEFAULT_TENANT_ADMIN_APP_PERMISSIONS.copy(),
    "knowledge": {
        "global_write": True,   # 租戶管理員預設可編輯全域知識
        "global_delete": True,  # 租戶管理員預設可刪除全域知識
    },
}


# ============================================================
# 權限檢查函數
# ============================================================


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


def get_user_permissions_for_role(role: str, preferences: dict | None) -> dict[str, dict[str, bool]]:
    """根據角色取得使用者權限

    Args:
        role: 使用者角色（platform_admin, tenant_admin, user）
        preferences: 使用者的 preferences JSONB 欄位

    Returns:
        權限結構
    """
    # 平台管理員擁有所有權限
    if role == "platform_admin":
        return get_full_permissions()

    # 租戶管理員使用預設租戶管理員權限
    if role == "tenant_admin":
        return deep_merge(DEFAULT_TENANT_ADMIN_PERMISSIONS.copy(), preferences.get("permissions", {}) if preferences else {})

    # 一般使用者使用預設權限合併個人設定
    return get_user_permissions(preferences)


def has_app_permission(
    role: str,
    permissions: dict[str, dict[str, bool]] | None,
    app_id: str,
) -> bool:
    """基於角色和權限設定檢查 App 權限

    這是新版的權限檢查函數，支援角色階層。

    Args:
        role: 使用者角色（platform_admin, tenant_admin, user）
        permissions: 使用者的 permissions 設定
        app_id: 應用程式 ID

    Returns:
        是否有權限使用該應用程式
    """
    # 平台管理員擁有所有權限
    if role == "platform_admin":
        return True

    # 租戶管理員：除了 platform-admin 外，檢查 permissions
    if role == "tenant_admin":
        if app_id == "platform-admin":
            return False  # 永遠禁止

        # 如果有明確設定，使用設定值
        if permissions and "apps" in permissions:
            app_perms = permissions["apps"]
            if app_id in app_perms:
                return app_perms[app_id]

        # 否則使用租戶管理員預設值
        return DEFAULT_TENANT_ADMIN_APP_PERMISSIONS.get(app_id, True)

    # 一般使用者：檢查 permissions，預設使用 DEFAULT_APP_PERMISSIONS
    if permissions and "apps" in permissions:
        app_perms = permissions["apps"]
        if app_id in app_perms:
            return app_perms[app_id]

    return DEFAULT_APP_PERMISSIONS.get(app_id, False)


async def get_user_app_permissions(user_id: int) -> dict[str, bool]:
    """從資料庫取得使用者的 App 權限

    Args:
        user_id: 使用者 ID

    Returns:
        App 權限設定 dict
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT role, preferences
            FROM users
            WHERE id = $1
            """,
            user_id,
        )

    if not row:
        return DEFAULT_APP_PERMISSIONS.copy()

    role = row["role"] or "user"
    preferences = row["preferences"] or {}
    permissions = preferences.get("permissions", {})

    # 根據角色決定基礎權限
    if role == "platform_admin":
        return {app_id: True for app_id in DEFAULT_APP_PERMISSIONS}

    if role == "tenant_admin":
        base_perms = DEFAULT_TENANT_ADMIN_APP_PERMISSIONS.copy()
    else:
        base_perms = DEFAULT_APP_PERMISSIONS.copy()

    # 合併使用者自訂權限
    user_app_perms = permissions.get("apps", {})
    base_perms.update(user_app_perms)

    return base_perms


def get_user_app_permissions_sync(
    role: str,
    user_data: dict | None,
) -> dict[str, bool]:
    """同步版本：根據角色和使用者資料取得 App 權限

    用於登入流程（不需要額外查詢資料庫）

    Args:
        role: 使用者角色（user, tenant_admin, platform_admin）
        user_data: 使用者資料（包含 preferences）

    Returns:
        App 權限設定 dict
    """
    # 平台管理員擁有所有權限
    if role == "platform_admin":
        return {app_id: True for app_id in DEFAULT_APP_PERMISSIONS}

    # 取得基礎權限
    if role == "tenant_admin":
        base_perms = DEFAULT_TENANT_ADMIN_APP_PERMISSIONS.copy()
    else:
        base_perms = DEFAULT_APP_PERMISSIONS.copy()

    # 合併使用者自訂權限（如果有的話）
    if user_data:
        preferences = user_data.get("preferences") or {}
        permissions = preferences.get("permissions", {})
        user_app_perms = permissions.get("apps", {})
        base_perms.update(user_app_perms)

    return base_perms


def get_mcp_tools_for_user(
    role: str,
    permissions: dict[str, dict[str, bool]] | None,
    all_tool_names: list[str],
) -> list[str]:
    """根據使用者權限過濾可用的 MCP 工具

    Args:
        role: 使用者角色（platform_admin, tenant_admin, user）
        permissions: 使用者的 permissions 設定
        all_tool_names: 所有可用的工具名稱列表

    Returns:
        過濾後的工具名稱列表
    """
    # 平台管理員可以使用所有工具
    if role == "platform_admin":
        return all_tool_names

    allowed_tools = []
    for tool in all_tool_names:
        # 移除 MCP 前綴（如果有的話）
        tool_name = tool.replace("mcp__ching-tech-os__", "")

        # 查詢工具需要的 App 權限
        required_app = TOOL_APP_MAPPING.get(tool_name)

        # 不需要特定權限的工具
        if required_app is None:
            allowed_tools.append(tool)
            continue

        # 檢查使用者是否有對應 App 權限
        if has_app_permission(role, permissions, required_app):
            allowed_tools.append(tool)

    return allowed_tools


def check_tool_permission(
    tool_name: str,
    role: str,
    permissions: dict[str, dict[str, bool]] | None,
) -> bool:
    """檢查使用者是否有權限使用特定 MCP 工具

    Args:
        tool_name: 工具名稱（可含或不含 MCP 前綴）
        role: 使用者角色
        permissions: 使用者權限設定

    Returns:
        是否有權限使用該工具
    """
    # 平台管理員可以使用所有工具
    if role == "platform_admin":
        return True

    # 移除 MCP 前綴
    clean_name = tool_name.replace("mcp__ching-tech-os__", "")

    # 查詢工具需要的 App 權限
    required_app = TOOL_APP_MAPPING.get(clean_name)

    # 不需要特定權限的工具
    if required_app is None:
        return True

    # 檢查 App 權限
    return has_app_permission(role, permissions, required_app)


def check_knowledge_permission(
    role: str,
    username: str,
    preferences: dict | None,
    knowledge_owner: str | None,
    knowledge_scope: str,
    action: str,
) -> bool:
    """檢查知識庫權限（同步版本，不支援專案知識）

    Args:
        role: 使用者角色（platform_admin, tenant_admin, user）
        username: 使用者帳號（用於檢查個人知識擁有者）
        preferences: 使用者的 preferences JSONB 欄位
        knowledge_owner: 知識的擁有者（None 表示全域知識）
        knowledge_scope: 知識的範圍（global 或 personal）
        action: 操作類型（read、write、delete）

    Returns:
        是否有權限執行該操作

    注意：專案知識（scope=project）請使用 check_knowledge_permission_async
    """
    # 平台管理員和租戶管理員擁有所有權限
    if role in ("platform_admin", "tenant_admin"):
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
    role: str,
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
        role: 使用者角色（platform_admin, tenant_admin, user）
        username: 使用者帳號（用於檢查個人知識擁有者）
        preferences: 使用者的 preferences JSONB 欄位
        knowledge_owner: 知識的擁有者（None 表示全域知識）
        knowledge_scope: 知識的範圍（global、personal 或 project）
        action: 操作類型（read、write、delete）
        user_id: CTOS 使用者 ID（檢查專案成員時需要）
        project_id: 專案 UUID（專案知識時需要）

    Returns:
        是否有權限執行該操作
    """
    # 平台管理員和租戶管理員擁有所有權限
    if role in ("platform_admin", "tenant_admin"):
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


# ============================================================
# FastAPI 權限檢查 Dependency
# ============================================================


def require_app_permission(app_id: str) -> Callable:
    """建立要求特定 App 權限的 FastAPI dependency

    使用方式：
    ```python
    @router.get("/projects")
    async def list_projects(
        session: SessionData = Depends(require_app_permission("project-management"))
    ):
        ...
    ```

    Args:
        app_id: 應用程式 ID（如 "project-management"、"knowledge-base"）

    Returns:
        FastAPI Depends 用的函數
    """
    # 延遲 import 避免循環依賴
    from ..api.auth import get_current_session
    from ..models.auth import SessionData

    async def checker(session: SessionData = Depends(get_current_session)) -> SessionData:
        """檢查使用者是否有指定的 App 權限"""
        # 平台管理員擁有所有權限
        if session.role == "platform_admin":
            return session

        # 檢查 session 中的權限快取
        if session.app_permissions:
            if session.app_permissions.get(app_id, False):
                return session
        else:
            # Session 沒有權限快取，使用 has_app_permission 函數計算
            # 將 session.app_permissions 轉換為 permissions 格式
            permissions = {"apps": session.app_permissions} if session.app_permissions else None
            if has_app_permission(session.role, permissions, app_id):
                return session

        # 無權限
        app_name = APP_DISPLAY_NAMES.get(app_id, app_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"無「{app_name}」功能權限",
        )

    return checker
