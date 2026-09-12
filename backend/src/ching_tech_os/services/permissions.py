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

from fastapi import Depends, HTTPException, Request, status

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
# 往來對象 → vendor-management，物料／庫存／採購 → inventory-management
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
    "list_library_folders": "file-manager",
    "archive_to_library": "file-manager",

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

    # 專案模組工具（migration 028；建立專案不開放給 bot，網頁做）
    "find_project": "project-management",
    "get_project": "project-management",
    "list_overdue_milestones": "project-management",
    "list_tasks": "project-management",
    "create_task": "project-management",
    "update_task": "project-management",
    "create_milestone": "project-management",
    "complete_milestone": "project-management",
    "add_project_member": "project-management",

    # 往來對象工具（往來與物料模組，migration 030）
    "find_party": "vendor-management",
    "get_party": "vendor-management",
    "create_party": "vendor-management",
    "update_party": "vendor-management",
    "add_party_contact": "vendor-management",
    "add_party_address": "vendor-management",
    "update_party_contact": "vendor-management",
    "delete_party_contact": "vendor-management",
    "update_party_address": "vendor-management",
    "delete_party_address": "vendor-management",
    "merge_parties": "vendor-management",
    "extract_party_from_document": "vendor-management",
    "summarize_party": "vendor-management",

    # 物料、庫存與採購工具
    "find_item": "inventory-management",
    "get_item": "inventory-management",
    "create_item": "inventory-management",
    "update_item": "inventory-management",
    "get_stock": "inventory-management",
    "adjust_stock": "inventory-management",
    "transfer_stock": "inventory-management",
    "create_purchase_order": "inventory-management",
    "get_purchase_order": "inventory-management",
    "list_purchase_orders": "inventory-management",
    "receive_purchase_order": "inventory-management",
    "cancel_purchase_order": "inventory-management",
    "extract_purchase_order_from_document": "inventory-management",
    "summarize_item": "inventory-management",

    # 分享連結工具（issue #205）：建立對外公開連結，等同把內部資料送出去
    "create_share_link": "share-manager",
    "share_knowledge_attachment": "share-manager",

    # 排程工具（issue #210）：會持久化、之後自動執行，對到排程管理 app
    "list_scheduled_tasks": "task-scheduler",
    "manage_scheduled_task": "task-scheduler",

    # Skill script 執行（issue #210）：等同讓對話端跑伺服器上的程式
    "run_skill_script": "ai-assistant",

    # 生圖工具（issue #210）：reference_images 會讀 NAS 根目錄底下的檔案並送到外部服務
    "codex_image_tool": "file-manager",

    # 通用工具（不需要特定權限）
    "get_message_attachments": None,  # 基礎訊息功能
    "summarize_chat": None,           # 群組對話摘要
    "download_web_image": None,       # 下載網路圖片
    "download_web_file": "file-manager",  # 下載網路文件（歸檔用）
    "text_to_speech": None,           # 語音回覆（基礎對話功能）
    "browse_webpage": None,           # 讀公開網頁
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
    # ai_prompts / ai_agents 是全域表，一個人改就影響所有人，預設關閉，由管理員逐人開放
    "prompt-editor": False,
    "agent-settings": False,
    "ai-log": False,  # AI log 含所有人的 prompt 與 system prompt，預設關閉，由管理員逐人開放
    "knowledge-base": True,
    "linebot": True,
    "memory-manager": True,
    "share-manager": False,  # 已綁定使用者可把任何 global／project 知識條目或 NAS 檔案發布成免帳號公開連結（issue #217），預設關閉，由管理員逐人開放
    "md2ppt": True,
    "md2doc": True,
    "printer": True,
    "settings": True,
}

# ============================================================
# 未綁定 CTOS 帳號的使用者強制擋下的 app（issue #201）
# ============================================================

# 這些 app 的 MCP 工具（讀與寫）會回員工姓名、往來對象聯絡方式，或 NAS／圖書館
# 內部檔案內容，即使 DEFAULT_APP_PERMISSIONS 預設開放，未綁定 CTOS 帳號的
# LINE／Telegram 使用者（`ctos_user_id is None`）與帳號已不存在的使用者
# （`ctos_user_id` 查無此人）一律拒絕，不做「只讀公開欄位」的折衷。
#
# 查證結論（見 mcp-unbound-guard/report.md 第 3 點）：
# - project-management／vendor-management／inventory-management：`get_project`／
#   `find_party`／`get_stock` 等工具回員工成員清單、外部聯絡人姓名電話 email、
#   採購資料。
# - file-manager：`search_nas_files`／`read_document` 等工具搜尋並讀出 NAS
#   共用區（projects／circuits／library）的實際檔案內容，屬內部檔案外流。
# - knowledge-base 不在此集合：`search_knowledge` 等工具已在條目層級只放行
#   `scope=global` 且 `is_public` 的公司整理文件，維持現狀。
# - memory-manager：`memory_tools.py` 的工具完全不呼叫
#   `check_mcp_tool_permission`（直接吃 `line_group_id`／`line_user_id`），加進
#   這個集合不會有任何效果，需要另外的程式改動，不在本次修復範圍內。
# - share-manager（issue #205）：`create_share_link`／`share_knowledge_attachment`
#   會把知識條目或 NAS 檔案變成不需要帳號就打得開的公開連結。未綁定者沒有任何
#   可歸屬的身分，也就沒有「他讀得到什麼」可以比對，一律拒絕。已綁定者除了這道
#   app 權限，還要通過 `services/share.py` 的 `check_resource_access()`：讀不到
#   的資源不能分享。
# - printer（issue #210）：`prepare_print_file` 會把檔案推進公司印表機佇列，
#   是「送到實體世界」的動作。預設權限維持 True（內部員工既有用法），但未綁定者
#   沒有可歸屬的身分，一律拒絕。
# - task-scheduler（issue #210）：`manage_scheduled_task` 會持久化一條之後自動執行的
#   任務（executor 可以是 agent 或 skill script），未綁定者不得留下會自己跑的東西。
#   這個 app 由 `modules.py` 的 task-scheduler 模組提供，預設權限本來就是 False。
APPS_REQUIRE_BOUND_USER: set[str] = {
    "project-management",
    "vendor-management",
    "inventory-management",
    "file-manager",
    "share-manager",
    "printer",
    "task-scheduler",
}

# 未綁定／帳號不存在時，若工具屬於 APPS_REQUIRE_BOUND_USER，一律回這則訊息。
# 綁定流程對照 `services/bot/identity_router.py` 的 BINDING_PROMPT_LINE／
# BINDING_PROMPT_TELEGRAM：登入 CTOS 系統 → Bot 管理頁面 → 點擊「綁定帳號」
# 產生驗證碼 → 把驗證碼傳給我完成綁定（沒有「輸入『綁定』」這個指令）。
BOUND_USER_REQUIRED_MESSAGE = (
    "此功能需要先綁定 CTOS 帳號，請登入 CTOS 系統，"
    "在 Bot 管理頁面點擊「綁定帳號」產生驗證碼，並將驗證碼傳送給我完成綁定"
)

# 讀群組對話／附件時沒有任何可用身分（issue #209）。
# 注意：只有 bot 走的路徑（有 `CTOS_BOT_*` 注入）身分才是伺服器驗過的；
# 網頁聊天沒有注入，`ctos_user_id` 本身就是模型帶進來的值，
# 這則訊息擋得住「沒身分」，擋不住「宣稱別人的身分」——真正的解是 issue #231。
BOT_IDENTITY_REQUIRED_MESSAGE = (
    "無法確認你的身分，這個功能只能讀你自己參與的對話"
)

# 有 CTOS 身分，但跟指定的群組／個人對話沒有既有關聯（issue #209）。
BOT_GROUP_SCOPE_DENIED_MESSAGE = (
    "你沒有參與這個群組的對話，無法讀取它的訊息"
)

# ============================================================
# 工具層級的未綁定自檢（issue #207）
# ============================================================

# 這些工具所屬的 app 沒有整包擋（knowledge-base 的讀取端靠條目層級控管，
# 只放行 scope=global 且 is_public 的條目），但工具本身會「憑空建立」條目，
# 沒有既有條目可以做條目層級檢查，因此在工具內部自檢 `ctos_user_id is None`
# 一律拒絕（不做強制 personal 的折衷——未綁定者根本沒有 personal 可歸屬）。
#
# 實作入口：`services/mcp/server.py` 的 `require_bound_user()`；
# 這份 registry 同時是 `docs/mcp-tool-access-matrix.md` 的來源，
# 改了工具卻忘了改 registry，矩陣測試會紅。
#
# issue #210 追加：文件生成三支會把檔案寫進 NAS 的 ai-generated 目錄，
# `generate_md2ppt`／`generate_md2doc` 還會建立不需帳號就打得開的分享連結
# （帶密碼、24 小時到期）。對到的 app（md2ppt／md2doc）預設開放給內部員工，
# 所以不整包擋，改用工具層自檢要求已綁定。`run_skill_script` 則是讓對話端
# 跑伺服器上的程式，同理。
TOOLS_REQUIRE_BOUND_USER: set[str] = {
    "add_note",
    "add_note_with_attachments",
    "generate_presentation",
    "generate_md2ppt",
    "generate_md2doc",
    "run_skill_script",
}


# ============================================================
# 有意對未綁定者開放的工具（issue #210）
# ============================================================

# 這些工具刻意不做 app 權限檢查，理由逐支寫在這裡，矩陣會原樣列出。
# 規則：不在這份 registry、又沒呼叫 `check_mcp_tool_permission` 的工具，
# 矩陣測試會紅——「忘了決定」和「決定要開放」必須分得出來。
TOOLS_INTENTIONALLY_OPEN: dict[str, str] = {
    "add_memory": "記憶是 bot 的基礎功能；範圍由伺服器注入的連線身分決定（issue #204），未綁定者只寫得到自己這條對話的記憶。",
    "get_memories": "記憶是 bot 的基礎功能；只讀得到注入身分底下的記憶（issue #204）。",
    "update_memory": "記憶是 bot 的基礎功能；SQL 帶注入身分的擁有者條件，改不到別人的記憶（issue #204）。",
    "delete_memory": "記憶是 bot 的基礎功能；SQL 帶注入身分的擁有者條件，刪不到別人的記憶（issue #204）。",
    "summarize_chat": "群組摘要是 bot 的基礎功能；bot 路徑有身分注入，只讀得到自己這個群組。沒有注入（網頁聊天）時要求 `ctos_user_id` 並驗群組關聯，但那個值本身是模型帶的，只是提高門檻，真正的解是 issue #231（issue #209）。",
    "get_message_attachments": "附件查詢是 bot 的基礎功能；與 summarize_chat 同一條身分解析，同樣只有 bot 路徑靠注入擋死（issue #209、#231）。",
    "download_web_image": "只把外部 URL 的圖片抓進 /tmp 暫存區回給同一條對話，不讀也不寫 NAS、知識庫或使用者資料。",
    "text_to_speech": "語音回覆是基礎對話功能；語音設定用伺服器注入的 CTOS_USER_ID／CTOS_GROUP_ID 查，模型參數影響不到，輸出只有音檔。",
    "browse_webpage": "只讀公開的 HTTPS 網頁並回傳文字。`web_tools.check_public_http_target()` 會拒絕 loopback／私有／link-local／CGNAT／unique-local 位址、無點主機名稱與 .local／.internal／.lan 這類內網後綴（DNS 解析結果有任何一個非公開就拒絕），並套在三個地方：最初的 URL、`page.route()` 攔到的每一個 request URL（擋重新導向與 subresource）、以及 `page.goto()` 之後真正落地的 `page.url`。未封死：本地檢查與瀏覽器是兩次獨立 DNS 解析，中間換答案（DNS rebinding）仍有空隙。",
}

# ============================================================
# 寫入型工具（存取矩陣用）
# ============================================================

# 「寫入」＝會建立／修改／刪除資料，或產生檔案、對外送出內容。
# 這份 registry 是 `docs/mcp-tool-access-matrix.md` 的來源；
# 新增工具卻沒分類，矩陣測試（動詞啟發式的負控制）會紅。
WRITE_TOOLS: frozenset[str] = frozenset({
    # 知識庫
    "add_note",
    "add_note_with_attachments",
    "add_attachments_to_knowledge",
    "update_knowledge_item",
    "update_knowledge_attachment",
    "delete_knowledge_item",
    # 記憶
    "add_memory",
    "update_memory",
    "delete_memory",
    # 往來對象
    "create_party",
    "update_party",
    "add_party_contact",
    "update_party_contact",
    "delete_party_contact",
    "add_party_address",
    "update_party_address",
    "delete_party_address",
    "merge_parties",
    # 物料、庫存與採購
    "create_item",
    "update_item",
    "adjust_stock",
    "transfer_stock",
    "create_purchase_order",
    "receive_purchase_order",
    "cancel_purchase_order",
    # 專案
    "create_task",
    "update_task",
    "create_milestone",
    "complete_milestone",
    "add_project_member",
    # NAS 檔案（送出＝對外揭露內部檔案）
    "archive_to_library",
    "send_nas_file",
    "prepare_file_message",
    # 媒體／下載（會在 NAS 產生檔案）
    "convert_pdf_to_images",
    "download_web_image",
    "download_web_file",
    # 文件生成與列印
    "generate_presentation",
    "generate_md2ppt",
    "generate_md2doc",
    "prepare_print_file",
    # 排程
    "manage_scheduled_task",
    # 分享（建立對外連結）
    "create_share_link",
    "share_knowledge_attachment",
    # 語音與生圖（會產生檔案）
    "text_to_speech",
    "codex_image_tool",
})

# 工具名稱開頭是這些動詞就一定是寫入型；矩陣測試用它當漂移的負控制
WRITE_TOOL_NAME_PREFIXES: tuple[str, ...] = (
    "add_",
    "create_",
    "update_",
    "delete_",
    "adjust_",
    "transfer_",
    "receive_",
    "cancel_",
    "merge_",
    "archive_",
    "complete_",
    "generate_",
    "prepare_",
    "send_",
    "download_",
    "manage_",
    "convert_",
)

# 知識庫預設權限
DEFAULT_KNOWLEDGE_PERMISSIONS: dict[str, bool] = {
    "global_write": False,      # 預設關閉，需管理員開放
    "global_delete": False,     # 預設關閉，需管理員開放
}

# 共用來源預設權限
DEFAULT_SHARED_SOURCE_PERMISSIONS: dict[str, bool] = {
    "projects": True,
    "circuits": True,
    "library": True,
}

# 完整預設權限結構
DEFAULT_PERMISSIONS: dict[str, dict[str, bool]] = {
    "apps": DEFAULT_APP_PERMISSIONS.copy(),
    "knowledge": DEFAULT_KNOWLEDGE_PERMISSIONS.copy(),
    "shared_sources": DEFAULT_SHARED_SOURCE_PERMISSIONS.copy(),
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
    "md2ppt": "簡報生成",
    "md2doc": "文件生成",
    "printer": "列印",
    "settings": "系統設定",
}


def get_effective_app_permissions() -> dict[str, bool]:
    """取得有效的 App 權限（排除停用模組，合併 Skill 擴充）。"""

    perms = DEFAULT_APP_PERMISSIONS.copy()
    try:
        from ..modules import get_module_registry, is_module_enabled

        registry = get_module_registry()
        for info in registry.values():
            for app_id, default_value in (info.get("permission_defaults") or {}).items():
                if isinstance(app_id, str):
                    perms.setdefault(app_id, bool(default_value))

        for module_id, info in registry.items():
            if is_module_enabled(module_id):
                continue
            for app_id in info.get("app_ids", []):
                perms.pop(app_id, None)
    except Exception as e:
        logger.warning("計算有效 App 權限失敗，使用預設值: %s", e)
    return perms


def _build_default_permissions() -> dict[str, dict[str, bool]]:
    """建立預設權限快照。"""
    return {
        "apps": get_effective_app_permissions(),
        "knowledge": DEFAULT_KNOWLEDGE_PERMISSIONS.copy(),
        "shared_sources": DEFAULT_SHARED_SOURCE_PERMISSIONS.copy(),
    }

# ============================================================
# 權限檢查函數
# ============================================================


def get_full_permissions() -> dict[str, dict[str, bool]]:
    """取得完整權限（所有權限都開啟）

    用於管理員帳號
    """
    app_permissions = get_effective_app_permissions()
    return {
        "apps": {app_id: True for app_id in app_permissions},
        "knowledge": {perm: True for perm in DEFAULT_KNOWLEDGE_PERMISSIONS},
        "shared_sources": {source: True for source in DEFAULT_SHARED_SOURCE_PERMISSIONS},
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
    default_permissions = _build_default_permissions()
    if preferences is None:
        return default_permissions

    user_perms = preferences.get("permissions", {})
    return deep_merge(default_permissions, user_perms)


def get_user_permissions_for_role(role: str, preferences: dict | None) -> dict[str, dict[str, bool]]:
    """根據角色取得使用者權限

    Args:
        role: 使用者角色（admin, user）
        preferences: 使用者的 preferences JSONB 欄位

    Returns:
        權限結構
    """
    # 管理員擁有所有權限
    if role == "admin":
        return get_full_permissions()

    # 一般使用者使用預設權限合併個人設定
    return get_user_permissions(preferences)


def has_app_permission(
    role: str,
    permissions: dict[str, dict[str, bool]] | None,
    app_id: str,
) -> bool:
    """基於角色和權限設定檢查 App 權限

    Args:
        role: 使用者角色（admin, user）
        permissions: 使用者的 permissions 設定
        app_id: 應用程式 ID

    Returns:
        是否有權限使用該應用程式
    """
    # 管理員擁有所有權限
    if role == "admin":
        return app_id in get_effective_app_permissions()

    # 一般使用者：檢查 permissions，預設使用 DEFAULT_APP_PERMISSIONS
    if permissions and "apps" in permissions:
        app_perms = permissions["apps"]
        if app_id in app_perms:
            return app_perms[app_id]

    return get_effective_app_permissions().get(app_id, False)


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

    effective_defaults = get_effective_app_permissions()
    if not row:
        return effective_defaults.copy()

    role = row["role"] or "user"
    preferences = row["preferences"] or {}
    permissions = preferences.get("permissions", {})

    # 管理員擁有所有權限
    if role == "admin":
        return {app_id: True for app_id in effective_defaults}

    # 一般使用者使用預設權限合併個人設定
    base_perms = effective_defaults.copy()
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
        role: 使用者角色（admin, user）
        user_data: 使用者資料（包含 preferences）

    Returns:
        App 權限設定 dict
    """
    effective_defaults = get_effective_app_permissions()

    # 管理員擁有所有權限
    if role == "admin":
        return {app_id: True for app_id in effective_defaults}

    # 一般使用者使用預設權限合併個人設定
    base_perms = effective_defaults.copy()
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
        role: 使用者角色（admin, user）
        permissions: 使用者的 permissions 設定
        all_tool_names: 所有可用的工具名稱列表

    Returns:
        過濾後的工具名稱列表
    """
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
        role: 使用者角色（admin, user）
        permissions: 使用者權限設定

    Returns:
        是否有權限使用該工具
    """
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
        role: 使用者角色（admin, user）
        username: 使用者帳號（用於檢查個人知識擁有者）
        preferences: 使用者的 preferences JSONB 欄位
        knowledge_owner: 知識的擁有者（None 表示全域知識）
        knowledge_scope: 知識的範圍（global 或 personal）
        action: 操作類型（read、write、delete）

    Returns:
        是否有權限執行該操作

    注意：專案知識（scope=project）請使用 check_knowledge_permission_async
    """
    # 管理員擁有所有權限
    if role == "admin":
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
        role: 使用者角色（admin, user）
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
    # 管理員擁有所有權限
    if role == "admin":
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
    return _build_default_permissions()


def get_app_display_names() -> dict[str, str]:
    """取得應用程式顯示名稱對照表"""
    names = APP_DISPLAY_NAMES.copy()
    try:
        from ..modules import get_module_registry

        for info in get_module_registry().values():
            for app in info.get("app_manifest", []):
                app_id = app.get("id")
                app_name = app.get("name")
                if isinstance(app_id, str) and isinstance(app_name, str) and app_name:
                    names.setdefault(app_id, app_name)

            for app_id, display_name in (info.get("permission_display_names") or {}).items():
                if isinstance(app_id, str) and isinstance(display_name, str) and display_name:
                    names[app_id] = display_name
    except Exception as e:
        logger.warning("讀取模組 App 顯示名稱失敗，使用預設值: %s", e)
    return names


# ============================================================
# FastAPI 權限檢查 Dependency
# ============================================================


def require_app_permission(app_id: str, allow_query_token: bool = False) -> Callable:
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
        allow_query_token: 是否允許從 query parameter 取 token
            （供 <img src>、window.open 等無法設定 header 的請求使用）

    Returns:
        FastAPI Depends 用的函數
    """
    # 延遲 import 避免循環依賴
    from ..api.auth import get_current_session, get_session_from_token_or_query
    from ..models.auth import SessionData

    session_dependency = (
        get_session_from_token_or_query if allow_query_token else get_current_session
    )

    async def checker(
        request: Request,
        session: SessionData = Depends(session_dependency),
    ) -> SessionData:
        """檢查使用者是否有指定的 App 權限"""
        # 唯讀 API token：拒絕寫入操作
        if session.read_only and request.method not in ("GET", "HEAD", "OPTIONS"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="此 API token 為唯讀，無法執行寫入操作",
            )

        # 管理員擁有所有權限
        if session.role == "admin":
            return session

        # 一律走 has_app_permission：session 的權限快取沒帶到這個 app_id 時，
        # 回退到 get_effective_app_permissions() 的預設值，與其他呼叫端一致。
        permissions = {"apps": session.app_permissions} if session.app_permissions else None
        if has_app_permission(session.role, permissions, app_id):
            return session

        # 無權限
        app_name = get_app_display_names().get(app_id, app_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"無「{app_name}」功能權限",
        )

    return checker
