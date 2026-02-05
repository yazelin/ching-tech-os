"""Line Bot MCP Server

使用 FastMCP 定義工具，支援：
- Claude Code CLI（stdio 模式）
- Line Bot AI（直接呼叫）
- 其他 MCP 客戶端

工具只定義一次，Schema 自動從 type hints 和 docstring 生成。
"""

import asyncio
import logging
import uuid as uuid_module
from datetime import datetime, timedelta, timezone
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from ..database import get_connection, init_db_pool

logger = logging.getLogger("mcp_server")

# 台北時區 (UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))

# 知識庫「列出全部」的特殊查詢關鍵字
_LIST_ALL_KNOWLEDGE_QUERIES = {"*", "all", "全部", "列表", ""}


def to_taipei_time(dt: datetime) -> datetime:
    """將 datetime 轉換為台北時區"""
    if dt is None:
        return None
    # 如果是 naive datetime，假設為 UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TAIPEI_TZ)

# 建立 FastMCP Server 實例
mcp = FastMCP(
    "ching-tech-os",
    instructions="擎添工業 OS 的 AI 工具，可查詢專案、會議、成員等資訊。",
)


# ============================================================
# 資料庫連線輔助函數
# ============================================================


async def ensure_db_connection():
    """確保資料庫連線池已初始化（懶初始化）"""
    from ..database import _pool
    if _pool is None:
        logger.info("初始化資料庫連線池...")
        await init_db_pool()


# ============================================================
# 權限檢查輔助函數
# ============================================================


async def check_mcp_tool_permission(
    tool_name: str,
    ctos_user_id: int | None,
) -> tuple[bool, str]:
    """
    檢查使用者是否有權限使用 MCP 工具

    此函數用於 MCP 工具執行時的權限檢查，防止使用者繞過 prompt 過濾直接呼叫工具。

    Args:
        tool_name: 工具名稱（不含 mcp__ching-tech-os__ 前綴）
        ctos_user_id: CTOS 用戶 ID（None 表示未關聯帳號）

    Returns:
        (allowed, error_message): allowed=True 表示允許，False 表示拒絕並回傳錯誤訊息
    """
    from .permissions import (
        check_tool_permission,
        TOOL_APP_MAPPING,
        APP_DISPLAY_NAMES,
        DEFAULT_APP_PERMISSIONS,
        is_tool_deprecated,
    )

    # 檢查工具是否已停用（遷移至 ERPNext）
    is_deprecated, deprecated_message = is_tool_deprecated(tool_name)
    if is_deprecated:
        return (False, deprecated_message)

    # 不需要特定權限的工具，直接放行
    required_app = TOOL_APP_MAPPING.get(tool_name)
    if required_app is None:
        return (True, "")

    # 未關聯帳號的使用者，使用預設權限
    if ctos_user_id is None:
        # 檢查預設權限是否允許
        if DEFAULT_APP_PERMISSIONS.get(required_app, False):
            return (True, "")
        app_name = APP_DISPLAY_NAMES.get(required_app, required_app)
        return (False, f"需要「{app_name}」功能權限才能使用此工具")

    # 查詢使用者角色和權限
    await ensure_db_connection()
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT role, preferences FROM users WHERE id = $1",
            ctos_user_id,
        )

    if not row:
        # 使用者不存在，使用預設權限
        if DEFAULT_APP_PERMISSIONS.get(required_app, False):
            return (True, "")
        app_name = APP_DISPLAY_NAMES.get(required_app, required_app)
        return (False, f"需要「{app_name}」功能權限才能使用此工具")

    role = row["role"] or "user"
    preferences = row["preferences"] or {}
    permissions = {"apps": preferences.get("permissions", {}).get("apps", {})}

    # 使用 check_tool_permission 檢查
    if check_tool_permission(tool_name, role, permissions):
        return (True, "")

    app_name = APP_DISPLAY_NAMES.get(required_app, required_app)
    return (False, f"您沒有「{app_name}」功能權限，無法使用此工具")


async def check_project_member_permission(
    project_id: str,
    user_id: int,
) -> bool:
    """
    檢查用戶是否為專案成員

    Args:
        project_id: 專案 UUID 字串
        user_id: CTOS 用戶 ID

    Returns:
        True 表示用戶是專案成員，可以操作
    """
    from uuid import UUID as UUID_type
    await ensure_db_connection()
    async with get_connection() as conn:
        exists = await conn.fetchval(
            """
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = $1 AND pm.user_id = $2
            """,
            UUID_type(project_id),
            user_id,
        )
        return exists is not None


# ============================================================
# MCP 工具定義
# ============================================================


@mcp.tool()
async def search_knowledge(
    query: str,
    project: str | None = None,
    category: str | None = None,
    limit: int = 5,
    line_user_id: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    搜尋知識庫

    Args:
        query: 搜尋關鍵字（使用 * 或空字串可列出全部知識）
        project: 專案過濾（如：專案 ID 或名稱）
        category: 分類過濾（如：technical, process, tool）
        limit: 最大結果數量，預設 5
        line_user_id: Line 用戶 ID（從對話識別取得，用於搜尋個人知識）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於搜尋個人知識）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("search_knowledge", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from . import knowledge as kb_service

    # 處理特殊查詢：* 或空字串表示列出全部
    search_query: str | None = query
    if query in _LIST_ALL_KNOWLEDGE_QUERIES:
        search_query = None  # 不進行關鍵字搜尋，列出全部

    # 取得使用者名稱（用於搜尋個人知識）
    current_username: str | None = None
    if ctos_user_id:
        try:
            async with get_connection() as conn:
                user_row = await conn.fetchrow(
                    "SELECT username FROM users WHERE id = $1",
                    ctos_user_id,
                )
                if user_row:
                    current_username = user_row["username"]
        except Exception as e:
            logger.warning(f"取得使用者名稱失敗: {e}")

    try:
        result = kb_service.search_knowledge(
            query=search_query,
            project=project,
            category=category,
            current_username=current_username,
        )

        if not result.items:
            if search_query:
                return f"找不到包含「{query}」的知識"
            else:
                return "知識庫目前是空的"

        # 格式化結果
        items = result.items[:limit]
        if search_query:
            output = [f"搜尋「{query}」找到 {len(result.items)} 筆結果：\n"]
        else:
            output = [f"📚 知識庫共有 {len(result.items)} 筆知識：\n"]

        for item in items:
            tags_str = ", ".join(item.tags.topics) if item.tags.topics else "無標籤"
            output.append(f"📄 [{item.id}] {item.title}")
            output.append(f"   分類：{item.category} | 標籤：{tags_str}")
            if item.snippet:
                # 截取片段
                snippet = item.snippet[:100] + "..." if len(item.snippet) > 100 else item.snippet
                output.append(f"   摘要：{snippet}")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"搜尋知識庫失敗: {e}")
        return f"搜尋失敗：{str(e)}"


@mcp.tool()
async def get_knowledge_item(
    kb_id: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    取得知識庫文件的完整內容

    Args:
        kb_id: 知識 ID（如 kb-001、kb-002）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("get_knowledge_item", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from . import knowledge as kb_service
    from pathlib import Path

    try:
        item = kb_service.get_knowledge(kb_id)

        # 格式化輸出
        tags_str = ", ".join(item.tags.topics) if item.tags.topics else "無標籤"
        output = [
            f"📄 **[{item.id}] {item.title}**",
            f"分類：{item.category} | 標籤：{tags_str}",
            "",
            "---",
            "",
            item.content or "（無內容）",
        ]

        # 加入附件資訊
        if item.attachments:
            output.append("")
            output.append("---")
            output.append("")
            output.append(f"📎 **附件** ({len(item.attachments)} 個)")
            for idx, att in enumerate(item.attachments):
                filename = Path(att.path).name
                desc = f" - {att.description}" if att.description else ""
                output.append(f"  [{idx}] {att.type}: {filename}{desc}")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"取得知識失敗: {e}")
        return f"找不到知識 {kb_id}：{str(e)}"


@mcp.tool()
async def update_knowledge_item(
    kb_id: str,
    title: str | None = None,
    content: str | None = None,
    category: str | None = None,
    scope: str | None = None,
    topics: list[str] | None = None,
    projects: list[str] | None = None,
    roles: list[str] | None = None,
    level: str | None = None,
    type: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    更新知識庫文件

    Args:
        kb_id: 知識 ID（如 kb-001）
        title: 新標題（不填則不更新）
        content: 新內容（不填則不更新）
        category: 新分類（不填則不更新）
        scope: 知識範圍，可選 global（全域）或 personal（個人）。改為 global 會清除 owner；改為 personal 會自動設定 owner 為當前用戶
        topics: 主題標籤列表（不填則不更新）
        projects: 關聯專案列表（不填則不更新）
        roles: 適用角色列表（不填則不更新）
        level: 難度層級，如 beginner、intermediate、advanced（不填則不更新）
        type: 知識類型，如 note、spec、guide（不填則不更新）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於設定 personal 知識的 owner）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("update_knowledge_item", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from ..models.knowledge import KnowledgeUpdate, KnowledgeTags
    from . import knowledge as kb_service

    try:
        # 如果改為 personal，需要設定 owner
        owner: str | None = None
        if scope == "personal" and ctos_user_id:
            async with get_connection() as conn:
                user_row = await conn.fetchrow(
                    "SELECT username FROM users WHERE id = $1",
                    ctos_user_id,
                )
                if user_row:
                    owner = user_row["username"]
                else:
                    return "❌ 無法設為個人知識：找不到您的帳號"
        elif scope == "personal" and not ctos_user_id:
            return "❌ 無法設為個人知識：需要綁定 CTOS 帳號"

        # 建立標籤更新資料（任一標籤欄位有值就建立 KnowledgeTags）
        tags = None
        if any([topics, projects, roles, level]):
            tags = KnowledgeTags(
                topics=topics or [],
                projects=projects or [],
                roles=roles or [],
                level=level,
            )

        # 建立更新資料
        update_data = KnowledgeUpdate(
            title=title,
            content=content,
            category=category,
            scope=scope,
            owner=owner,
            type=type,
            tags=tags,
        )

        item = kb_service.update_knowledge(kb_id, update_data)

        scope_info = f"（{item.scope}）" if item.scope else ""
        return f"✅ 已更新 [{item.id}] {item.title}{scope_info}"

    except Exception as e:
        logger.error(f"更新知識失敗: {e}")
        return f"更新失敗：{str(e)}"


@mcp.tool()
async def add_attachments_to_knowledge(
    kb_id: str,
    attachments: list[str],
    descriptions: list[str] | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    為現有知識庫新增附件

    Args:
        kb_id: 知識 ID（如 kb-001）
        attachments: 附件的 NAS 路徑列表（從 get_message_attachments 取得）
        descriptions: 附件描述列表（與 attachments 一一對應，如「圖1 水切爐」）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("add_attachments_to_knowledge", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from . import knowledge as kb_service

    # 限制附件數量
    if len(attachments) > 10:
        return "附件數量不能超過 10 個"

    # 確認知識存在
    try:
        knowledge = kb_service.get_knowledge(kb_id)
    except Exception:
        return f"找不到知識 {kb_id}"

    # 取得目前附件數量（用來計算新附件的 index）
    current_attachment_count = len(knowledge.attachments)

    # 處理附件
    success_count = 0
    failed_attachments = []
    added_descriptions = []

    for i, nas_path in enumerate(attachments):
        try:
            kb_service.copy_linebot_attachment_to_knowledge(kb_id, nas_path)
            success_count += 1

            # 如果有對應的描述，更新附件描述
            if descriptions and i < len(descriptions) and descriptions[i]:
                try:
                    new_index = current_attachment_count + success_count - 1
                    kb_service.update_attachment_description(kb_id, new_index, descriptions[i])
                    added_descriptions.append(descriptions[i])
                except Exception as e:
                    logger.warning(f"設定描述失敗 {descriptions[i]}: {e}")
        except Exception as e:
            logger.warning(f"附件複製失敗 {nas_path}: {e}")
            failed_attachments.append(nas_path)

    # 回傳結果
    if success_count == 0 and failed_attachments:
        return f"所有附件都無法加入：{', '.join(failed_attachments)}"

    output = [f"✅ 已為 {kb_id} 新增 {success_count} 個附件"]

    if added_descriptions:
        output.append(f"📝 已設定描述：{', '.join(added_descriptions)}")

    if failed_attachments:
        output.append(f"⚠️ 以下附件無法加入：")
        for path in failed_attachments:
            output.append(f"  - {path}")

    return "\n".join(output)


@mcp.tool()
async def delete_knowledge_item(
    kb_id: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    刪除知識庫文件

    Args:
        kb_id: 知識 ID（如 kb-001）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("delete_knowledge_item", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from . import knowledge as kb_service

    try:
        kb_service.delete_knowledge(kb_id)
        return f"✅ 已刪除知識 {kb_id}"

    except Exception as e:
        logger.error(f"刪除知識失敗: {e}")
        return f"刪除失敗：{str(e)}"


@mcp.tool()
async def get_knowledge_attachments(
    kb_id: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    取得知識庫的附件列表

    Args:
        kb_id: 知識 ID（如 kb-001、kb-002）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("get_knowledge_attachments", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from . import knowledge as kb_service
    from pathlib import Path

    try:
        item = kb_service.get_knowledge(kb_id)

        if not item.attachments:
            return f"知識 {kb_id} 沒有附件"

        output = [f"📎 **{kb_id} 附件列表** ({len(item.attachments)} 個)\n"]

        for idx, att in enumerate(item.attachments):
            filename = Path(att.path).name
            output.append(f"[{idx}] {att.type}")
            output.append(f"    檔名：{filename}")
            output.append(f"    路徑：{att.path}")  # 完整路徑，供 prepare_file_message 使用
            if att.size:
                output.append(f"    大小：{att.size}")
            if att.description:
                output.append(f"    說明：{att.description}")
            else:
                output.append("    說明：（無）")
            output.append("")

        output.append("提示：使用 prepare_file_message(file_path=路徑) 準備附件發送")
        return "\n".join(output)

    except Exception as e:
        logger.error(f"取得附件列表失敗: {e}")
        return f"找不到知識 {kb_id}：{str(e)}"


@mcp.tool()
async def update_knowledge_attachment(
    kb_id: str,
    attachment_index: int,
    description: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    更新知識庫附件的說明

    Args:
        kb_id: 知識 ID（如 kb-001）
        attachment_index: 附件索引（從 0 開始，可用 get_knowledge_attachments 查詢）
        description: 附件說明（如「圖1 水切爐畫面」）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("update_knowledge_attachment", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from . import knowledge as kb_service
    from pathlib import Path

    try:
        attachment = kb_service.update_attachment(
            kb_id=kb_id,
            attachment_idx=attachment_index,
            description=description,
        )

        filename = Path(attachment.path).name
        desc = attachment.description or "（無）"
        return f"✅ 已更新 {kb_id} 附件 [{attachment_index}]\n檔名：{filename}\n說明：{desc}"

    except Exception as e:
        logger.error(f"更新附件失敗: {e}")
        return f"更新失敗：{str(e)}"


@mcp.tool()
async def read_knowledge_attachment(
    kb_id: str,
    attachment_index: int = 0,
    max_chars: int = 15000,
    ctos_user_id: int | None = None,
) -> str:
    """
    讀取知識庫附件的內容

    Args:
        kb_id: 知識 ID（如 kb-001）
        attachment_index: 附件索引（從 0 開始，可用 get_knowledge_attachments 查詢）
        max_chars: 最大字元數限制，預設 15000（避免超過 CLI 的 25000 token 限制）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("read_knowledge_attachment", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from . import knowledge as kb_service
    from .path_manager import path_manager
    from pathlib import Path

    try:
        item = kb_service.get_knowledge(kb_id)

        if not item.attachments:
            return f"知識 {kb_id} 沒有附件"

        if attachment_index < 0 or attachment_index >= len(item.attachments):
            return f"附件索引 {attachment_index} 超出範圍（共 {len(item.attachments)} 個附件，索引 0-{len(item.attachments)-1}）"

        attachment = item.attachments[attachment_index]
        filename = Path(attachment.path).name
        file_ext = Path(attachment.path).suffix.lower()

        # 解析路徑並轉換為檔案系統路徑
        try:
            fs_path = path_manager.to_filesystem(attachment.path)
        except ValueError as e:
            return f"無法解析附件路徑：{e}"

        fs_path_obj = Path(fs_path)
        if not fs_path_obj.exists():
            return f"附件檔案不存在：{filename}"

        # 判斷檔案類型
        text_extensions = {".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".csv", ".log", ".ini", ".conf", ".html", ".css", ".js", ".py", ".sh"}

        if file_ext in text_extensions:
            # 文字檔案：直接讀取
            try:
                content = fs_path_obj.read_text(encoding="utf-8")
                if len(content) > max_chars:
                    content = content[:max_chars] + f"\n\n... (內容已截斷，共 {len(content)} 字元)"

                return f"📄 **{kb_id} 附件 [{attachment_index}]**\n檔名：{filename}\n\n---\n\n{content}"
            except UnicodeDecodeError:
                return f"無法讀取檔案 {filename}：編碼錯誤"
        else:
            # 二進位檔案：顯示檔案資訊
            file_size = fs_path_obj.stat().st_size
            if file_size >= 1024 * 1024:
                size_str = f"{file_size / 1024 / 1024:.1f}MB"
            else:
                size_str = f"{file_size / 1024:.1f}KB"

            return f"📎 **{kb_id} 附件 [{attachment_index}]**\n檔名：{filename}\n大小：{size_str}\n類型：{file_ext}\n\n此為二進位檔案，無法直接顯示內容。"

    except Exception as e:
        logger.error(f"讀取附件失敗: {e}")
        return f"讀取附件失敗：{str(e)}"


async def _determine_knowledge_scope(
    line_group_id: str | None,
    line_user_id: str | None,
    ctos_user_id: int | None,
) -> tuple[str, str | None, str | None]:
    """判斷知識庫的 scope 和相關屬性

    Args:
        line_group_id: Line 群組的內部 UUID
        line_user_id: Line 用戶 ID
        ctos_user_id: CTOS 用戶 ID

    Returns:
        tuple[scope, owner_username, project_id]
        - scope: "global", "personal", 或 "project"
        - owner_username: 擁有者帳號（scope=personal 時使用）
        - project_id: 專案 UUID（scope=project 時使用）
    """
    from uuid import UUID as UUID_type

    scope = "global"
    owner_username: str | None = None
    project_id: str | None = None

    # 1. 取得 CTOS 使用者名稱（如果有綁定）
    if ctos_user_id:
        async with get_connection() as conn:
            user_row = await conn.fetchrow(
                "SELECT username FROM users WHERE id = $1",
                ctos_user_id,
            )
            if user_row:
                owner_username = user_row["username"]

    # 2. 判斷對話來源並設定 scope
    if line_group_id:
        # 群組聊天：檢查群組是否綁定專案
        async with get_connection() as conn:
            group_row = await conn.fetchrow(
                "SELECT project_id FROM bot_groups WHERE id = $1",
                UUID_type(line_group_id),
            )
            if group_row and group_row["project_id"]:
                # 群組已綁定專案 → scope=project
                scope = "project"
                project_id = str(group_row["project_id"])
            else:
                # 群組未綁定專案 → scope=global
                scope = "global"
    elif line_user_id and owner_username:
        # 個人聊天且已綁定帳號 → scope=personal
        scope = "personal"
    # 其他情況（未綁定帳號）→ scope=global（預設值）

    return scope, owner_username, project_id


@mcp.tool()
async def add_note(
    title: str,
    content: str,
    category: str = "note",
    topics: list[str] | None = None,
    project: str | None = None,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    新增筆記到知識庫

    Args:
        title: 筆記標題
        content: 筆記內容（Markdown 格式）
        category: 分類，預設 note（可選：technical, process, tool, note）
        topics: 主題標籤列表
        project: 關聯的專案名稱
        line_group_id: Line 群組的內部 UUID（從對話識別取得，群組對話時使用）
        line_user_id: Line 用戶 ID（從對話識別取得，個人對話時使用）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於判斷帳號綁定）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("add_note", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from ..models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from . import knowledge as kb_service

    try:
        # 自動判斷 scope 和相關屬性
        scope, owner_username, project_id = await _determine_knowledge_scope(
            line_group_id, line_user_id, ctos_user_id
        )

        # 建立標籤
        tags = KnowledgeTags(
            projects=[project] if project else [],
            roles=[],
            topics=topics or [],
            level=None,
        )

        # 建立來源（標記來自 Line Bot）
        source = KnowledgeSource(
            project=None,
            path="linebot",
            commit=None,
        )

        # 建立知識
        data = KnowledgeCreate(
            title=title,
            content=content,
            type="note",
            category=category,
            scope=scope,
            project_id=project_id,
            tags=tags,
            source=source,
            related=[],
            author=owner_username or "linebot",
        )

        result = kb_service.create_knowledge(data, owner=owner_username, project_id=project_id)

        # 組裝回應訊息
        scope_text = {"global": "全域", "personal": "個人", "project": "專案"}.get(scope, scope)
        return f"✅ 筆記已新增！\nID：{result.id}\n標題：{result.title}\n範圍：{scope_text}知識"

    except Exception as e:
        logger.error(f"新增筆記失敗: {e}")
        return f"新增筆記失敗：{str(e)}"


@mcp.tool()
async def add_note_with_attachments(
    title: str,
    content: str,
    attachments: list[str],
    category: str = "note",
    topics: list[str] | None = None,
    project: str | None = None,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    新增筆記到知識庫並加入附件

    Args:
        title: 筆記標題
        content: 筆記內容（Markdown 格式）
        attachments: 附件的 NAS 路徑列表（從 get_message_attachments 取得）
        category: 分類，預設 note（可選：technical, process, tool, note）
        topics: 主題標籤列表
        project: 關聯的專案名稱
        line_group_id: Line 群組的內部 UUID（從對話識別取得，群組對話時使用）
        line_user_id: Line 用戶 ID（從對話識別取得，個人對話時使用）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於判斷帳號綁定）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("add_note_with_attachments", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from ..models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from . import knowledge as kb_service

    # 限制附件數量
    if len(attachments) > 10:
        return "附件數量不能超過 10 個"

    try:
        # 自動判斷 scope 和相關屬性
        scope, owner_username, knowledge_project_id = await _determine_knowledge_scope(
            line_group_id, line_user_id, ctos_user_id
        )

        # 建立知識庫筆記
        tags = KnowledgeTags(
            projects=[project] if project else [],
            roles=[],
            topics=topics or [],
            level=None,
        )

        source = KnowledgeSource(
            project=None,
            path="linebot",
            commit=None,
        )

        data = KnowledgeCreate(
            title=title,
            content=content,
            type="note",
            category=category,
            scope=scope,
            project_id=knowledge_project_id,
            tags=tags,
            source=source,
            related=[],
            author=owner_username or "linebot",
        )

        result = kb_service.create_knowledge(data, owner=owner_username, project_id=knowledge_project_id)
        kb_id = result.id

        # 2. 處理附件
        success_count = 0
        failed_attachments = []

        for nas_path in attachments:
            try:
                kb_service.copy_linebot_attachment_to_knowledge(kb_id, nas_path)
                success_count += 1
            except Exception as e:
                logger.warning(f"附件複製失敗 {nas_path}: {e}")
                failed_attachments.append(nas_path)

        # 3. 回傳結果
        scope_text = {"global": "全域", "personal": "個人", "project": "專案"}.get(scope, scope)
        output = [f"✅ 筆記已新增！", f"ID：{kb_id}", f"標題：{title}", f"範圍：{scope_text}知識"]

        if success_count > 0:
            output.append(f"附件：已加入 {success_count} 個")

        if failed_attachments:
            output.append(f"⚠️ 以下附件無法加入：")
            for path in failed_attachments:
                output.append(f"  - {path}")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"新增筆記失敗: {e}")
        return f"新增筆記失敗：{str(e)}"


@mcp.tool()
async def summarize_chat(
    line_group_id: str,
    hours: int = 24,
    max_messages: int = 50,
) -> str:
    """
    取得 Line 群組聊天記錄，供 AI 摘要使用

    Args:
        line_group_id: Line 群組的內部 UUID
        hours: 取得最近幾小時的訊息，預設 24
        max_messages: 最大訊息數量，預設 50
    """
    await ensure_db_connection()
    
    async with get_connection() as conn:
        # 計算時間範圍
        since = datetime.now() - timedelta(hours=hours)

        # 取得訊息
        rows = await conn.fetch(
            """
            SELECT m.content, m.created_at, m.message_type,
                   u.display_name as user_name
            FROM bot_messages m
            LEFT JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id = $1
              AND m.created_at >= $2
              AND m.message_type = 'text'
              AND m.content IS NOT NULL
            ORDER BY m.created_at ASC
            LIMIT $3
            """,
            UUID(line_group_id),
            since,
            max_messages,
        )

        if not rows:
            return f"過去 {hours} 小時內沒有文字訊息"

        # 取得群組名稱
        group = await conn.fetchrow(
            "SELECT name FROM bot_groups WHERE id = $1",
            UUID(line_group_id),
        )
        group_name = group["name"] if group else "未知群組"

        # 格式化訊息
        messages = [f"【{group_name}】過去 {hours} 小時的聊天記錄（共 {len(rows)} 則）：\n"]
        for row in rows:
            created_at_taipei = to_taipei_time(row["created_at"])
            time_str = created_at_taipei.strftime("%H:%M")
            user = row["user_name"] or "未知用戶"
            messages.append(f"[{time_str}] {user}: {row['content']}")

        return "\n".join(messages)


@mcp.tool()
async def get_message_attachments(
    line_user_id: str | None = None,
    line_group_id: str | None = None,
    days: int = 7,
    file_type: str | None = None,
    limit: int = 20,
) -> str:
    """
    查詢對話中的附件（圖片、檔案等），用於將附件加入知識庫

    Args:
        line_user_id: Line 用戶 ID（個人聊天時使用）
        line_group_id: Line 群組的內部 UUID
        days: 查詢最近幾天的附件，預設 7 天，可根據用戶描述調整
        file_type: 檔案類型過濾（image, file, video, audio），不填則查詢全部
        limit: 最大回傳數量，預設 20
    """
    await ensure_db_connection()
    
    if not line_user_id and not line_group_id:
        return "請提供 line_user_id 或 line_group_id"

    async with get_connection() as conn:
        # 計算時間範圍
        since = datetime.now() - timedelta(days=days)

        # 建立查詢條件
        conditions = ["m.created_at >= $1"]
        params: list = [since]
        param_idx = 2

        if line_group_id:
            conditions.append(f"m.bot_group_id = ${param_idx}")
            params.append(UUID(line_group_id))
            param_idx += 1
        elif line_user_id:
            # 個人聊天：查詢該用戶的訊息且不在群組中
            conditions.append(f"u.platform_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1
            conditions.append("m.bot_group_id IS NULL")

        if file_type:
            conditions.append(f"f.file_type = ${param_idx}")
            params.append(file_type)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # 查詢附件
        rows = await conn.fetch(
            f"""
            SELECT f.id, f.file_type, f.file_name, f.file_size, f.nas_path,
                   f.created_at, u.display_name as user_name
            FROM bot_files f
            JOIN bot_messages m ON f.message_id = m.id
            LEFT JOIN bot_users u ON m.bot_user_id = u.id
            WHERE {where_clause}
              AND f.nas_path IS NOT NULL
            ORDER BY f.created_at DESC
            LIMIT {limit}
            """,
            *params,
        )

        if not rows:
            type_hint = f"（類型：{file_type}）" if file_type else ""
            return f"最近 {days} 天內沒有找到附件{type_hint}"

        # 格式化結果
        type_names = {
            "image": "圖片",
            "file": "檔案",
            "video": "影片",
            "audio": "音訊",
        }

        output = [f"找到 {len(rows)} 個附件（最近 {days} 天）：\n"]
        for i, row in enumerate(rows, 1):
            type_name = type_names.get(row["file_type"], row["file_type"])
            created_at_taipei = to_taipei_time(row["created_at"])
            time_str = created_at_taipei.strftime("%Y-%m-%d %H:%M")
            user = row["user_name"] or "未知用戶"

            # 將相對路徑轉換為完整 URI 格式
            nas_path = row["nas_path"]
            if nas_path and not nas_path.startswith(("/", "ctos://", "shared://", "temp://")):
                # 相對路徑：加上 ctos://linebot/files/ 前綴
                nas_path = f"ctos://linebot/files/{nas_path}"

            output.append(f"{i}. [{type_name}] {time_str} - {user}")
            output.append(f"   NAS 路徑：{nas_path}")

            if row["file_name"]:
                output.append(f"   檔名：{row['file_name']}")
            if row["file_size"]:
                size_kb = row["file_size"] / 1024
                if size_kb >= 1024:
                    output.append(f"   大小：{size_kb / 1024:.1f} MB")
                else:
                    output.append(f"   大小：{size_kb:.1f} KB")
            output.append("")

        output.append("提示：使用 NAS 路徑作為 add_note_with_attachments 的 attachments 參數")

        return "\n".join(output)


@mcp.tool()
async def search_nas_files(
    keywords: str,
    file_types: str | None = None,
    limit: int = 100,
    ctos_user_id: int | None = None,
) -> str:
    """
    搜尋 NAS 共享檔案

    Args:
        keywords: 搜尋關鍵字，多個關鍵字用逗號分隔（AND 匹配，大小寫不敏感）
        file_types: 檔案類型過濾，多個類型用逗號分隔（如：pdf,xlsx,dwg）
        limit: 最大回傳數量，預設 100
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("search_nas_files", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    # 此工具搜尋的是公司共用區，不是租戶隔離區
    # 公司共用檔案
        from pathlib import Path
    from ..config import settings

    # 搜尋來源定義（shared zone 的子來源）
    # TODO: 未來可依使用者權限過濾可搜尋的來源
    search_sources = {
        "projects": Path(settings.projects_mount_path),
        "circuits": Path(settings.circuits_mount_path),
    }

    # 過濾出實際存在的掛載點
    available_sources = {
        name: path for name, path in search_sources.items() if path.exists()
    }
    if not available_sources:
        return "錯誤：沒有可用的搜尋來源掛載點"

    # 解析關鍵字（大小寫不敏感）
    keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not keyword_list:
        return "錯誤：請提供至少一個關鍵字"

    # 解析檔案類型
    type_list = []
    if file_types:
        type_list = [t.strip().lower().lstrip(".") for t in file_types.split(",") if t.strip()]

    # 清理關鍵字中的 find glob 特殊字元（避免非預期匹配）
    import re
    def _sanitize_for_find(s: str) -> str:
        return re.sub(r'[\[\]?*\\]', '', s)
    keyword_list = [_sanitize_for_find(kw) for kw in keyword_list]
    keyword_list = [kw for kw in keyword_list if kw]  # 移除清理後變空的關鍵字
    if not keyword_list:
        return "錯誤：請提供有效的關鍵字"

    # 兩階段搜尋：先淺層找目錄，再深入匹配的目錄搜尋檔案
    # 使用 asyncio subprocess 避免阻塞 event loop
    source_paths = [str(p) for p in available_sources.values()]
    source_name_map = {str(p): name for name, p in available_sources.items()}

    async def _run_find(args: list[str], timeout: int = 30) -> str:
        """非同步執行 find 指令"""
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace").strip()
        except (asyncio.TimeoutError, OSError):
            if proc:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            return ""

    async def _find_matching_dirs(max_depth: int) -> list[str]:
        """用 find 在淺層找出名稱匹配任一關鍵字的目錄"""
        # 對每個 source × keyword 平行執行 find
        tasks = []
        for source in source_paths:
            for kw in keyword_list:
                args = ["find", source, "-maxdepth", str(max_depth), "-type", "d", "-iname", f"*{kw}*"]
                tasks.append(_run_find(args, timeout=30))

        results = await asyncio.gather(*tasks)
        dirs = set()
        for output in results:
            for line in output.split("\n"):
                if line:
                    dirs.add(line)
        return sorted(dirs)

    async def _search_in_dirs(dirs: list[str]) -> list[dict]:
        """在指定目錄中用 find 搜尋符合條件的檔案"""
        if not dirs:
            return []

        args = ["find"] + dirs + ["-type", "f"]
        # 關鍵字過濾（所有關鍵字都要匹配路徑）
        for kw in keyword_list:
            args.extend(["-ipath", f"*{kw}*"])
        # 檔案類型過濾
        if type_list:
            args.append("(")
            for i, t in enumerate(type_list):
                if i > 0:
                    args.append("-o")
                args.extend(["-iname", f"*.{t}"])
            args.append(")")

        output = await _run_find(args, timeout=120)
        if not output:
            return []

        files = []
        seen = set()
        for line in output.split("\n"):
            if not line or line in seen:
                continue
            seen.add(line)

            fp = Path(line)
            # 判斷屬於哪個來源
            source_name = None
            source_path = None
            for sp, sn in source_name_map.items():
                if line.startswith(sp):
                    source_name = sn
                    source_path = sp
                    break
            if not source_name:
                continue

            rel_path_str = line[len(source_path):].lstrip("/")

            try:
                stat = fp.stat()
                size = stat.st_size
                modified = datetime.fromtimestamp(stat.st_mtime)
            except OSError:
                size = 0
                modified = None

            files.append({
                "path": f"shared://{source_name}/{rel_path_str}",
                "name": fp.name,
                "size": size,
                "modified": modified,
            })
            if len(files) >= limit:
                break

        return files

    matched_files = []
    try:
        # 階段 1：淺層 2 層目錄匹配
        matched_dirs = await _find_matching_dirs(max_depth=2)
        matched_files = await _search_in_dirs(matched_dirs)

        # 階段 2：沒找到結果，擴展到 3 層
        if not matched_files:
            matched_dirs = await _find_matching_dirs(max_depth=3)
            matched_files = await _search_in_dirs(matched_dirs)

        # 階段 3：仍沒結果，全掃檔名（關鍵字可能只出現在檔名中，不在目錄名）
        if not matched_files:
            matched_files = await _search_in_dirs(source_paths)

    except PermissionError:
        return "錯誤：沒有權限存取檔案系統"
    except Exception as e:
        return f"搜尋時發生錯誤：{str(e)}"

    if not matched_files:
        type_hint = f"（類型：{file_types}）" if file_types else ""
        return f"找不到符合「{keywords}」的檔案{type_hint}"

    # 格式化輸出
    output = [f"找到 {len(matched_files)} 個檔案：\n"]
    for f in matched_files:
        size_str = ""
        if f["size"]:
            if f["size"] >= 1024 * 1024:
                size_str = f" ({f['size'] / 1024 / 1024:.1f} MB)"
            elif f["size"] >= 1024:
                size_str = f" ({f['size'] / 1024:.1f} KB)"

        output.append(f"📄 {f['path']}{size_str}")

    if len(matched_files) >= limit:
        output.append(f"\n（已達上限 {limit} 筆，可能還有更多結果）")

    output.append("\n提示：使用 get_nas_file_info 取得詳細資訊，或 create_share_link 產生下載連結")
    return "\n".join(output)


@mcp.tool()
async def get_nas_file_info(
    file_path: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    取得 NAS 檔案詳細資訊

    Args:
        file_path: 檔案路徑（相對於 /mnt/nas/projects 或完整路徑）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("get_nas_file_info", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

        from pathlib import Path
    from .share import validate_nas_file_path, NasFileNotFoundError, NasFileAccessDenied

    # 統一使用 validate_nas_file_path 進行路徑驗證（支援 shared://projects/...、shared://circuits/... 等）
    try:
        full_path = validate_nas_file_path(file_path)
    except NasFileNotFoundError as e:
        return f"錯誤：{e}"
    except NasFileAccessDenied as e:
        return f"錯誤：{e}"

    # 取得檔案資訊
    try:
        stat = full_path.stat()
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime)
    except OSError as e:
        return f"錯誤：無法讀取檔案資訊 - {e}"

    # 格式化大小
    if size >= 1024 * 1024:
        size_str = f"{size / 1024 / 1024:.2f} MB"
    elif size >= 1024:
        size_str = f"{size / 1024:.2f} KB"
    else:
        size_str = f"{size} bytes"

    # 判斷檔案類型
    suffix = full_path.suffix.lower()
    type_map = {
        ".pdf": "PDF 文件",
        ".doc": "Word 文件",
        ".docx": "Word 文件",
        ".xls": "Excel 試算表",
        ".xlsx": "Excel 試算表",
        ".ppt": "PowerPoint 簡報",
        ".pptx": "PowerPoint 簡報",
        ".png": "PNG 圖片",
        ".jpg": "JPEG 圖片",
        ".jpeg": "JPEG 圖片",
        ".gif": "GIF 圖片",
        ".dwg": "AutoCAD 圖檔",
        ".dxf": "AutoCAD 交換檔",
        ".zip": "ZIP 壓縮檔",
        ".rar": "RAR 壓縮檔",
        ".txt": "文字檔",
        ".csv": "CSV 檔案",
    }
    file_type = type_map.get(suffix, f"{suffix} 檔案")

    return f"""📄 **{full_path.name}**

類型：{file_type}
大小：{size_str}
修改時間：{modified.strftime('%Y-%m-%d %H:%M:%S')}
完整路徑：{str(full_path)}

可用操作：
- create_share_link(resource_type="nas_file", resource_id="{str(full_path)}") 產生下載連結
- read_document(file_path="{str(full_path)}") 讀取文件內容（Word/Excel/PowerPoint/PDF）"""


@mcp.tool()
async def read_document(
    file_path: str,
    max_chars: int = 50000,
    ctos_user_id: int | None = None,
) -> str:
    """
    讀取文件內容（支援 Word、Excel、PowerPoint、PDF）

    將文件轉換為純文字，讓 AI 可以分析、總結或查詢內容。

    Args:
        file_path: NAS 檔案路徑（nas:// 格式、相對路徑或完整路徑）
        max_chars: 最大字元數限制，預設 50000
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("read_document", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    # 支援 CTOS zone 和 SHARED zone
        from pathlib import Path
    from ..config import settings
    from . import document_reader
    from .path_manager import path_manager, StorageZone

    # 使用 PathManager 解析路徑
    # 支援：nas://..., ctos://..., shared://..., /專案A/..., groups/... 等格式
    try:
        parsed = path_manager.parse(file_path)
    except ValueError as e:
        return f"錯誤：{e}"

    # 取得實際檔案系統路徑
    resolved_path = path_manager.to_filesystem(file_path)
    full_path = Path(resolved_path)

    # 安全檢查：只允許 CTOS 和 SHARED 區域（不允許 TEMP/LOCAL）
    if parsed.zone not in (StorageZone.CTOS, StorageZone.SHARED):
        return f"錯誤：不允許存取 {parsed.zone.value}:// 區域的檔案"

    # 安全檢查：確保路徑在 /mnt/nas/ 下
    nas_path = Path(settings.nas_mount_path)
    try:
        full_path = full_path.resolve()
        resolved_nas = str(nas_path.resolve())
        if not str(full_path).startswith(resolved_nas):
            return "錯誤：不允許存取此路徑"
    except Exception:
        return "錯誤：無效的路徑"

    if not full_path.exists():
        return f"錯誤：檔案不存在 - {file_path}"

    if not full_path.is_file():
        return f"錯誤：路徑不是檔案 - {file_path}"

    # 檢查是否為支援的文件格式
    suffix = full_path.suffix.lower()
    if suffix not in document_reader.SUPPORTED_EXTENSIONS:
        if suffix in document_reader.LEGACY_EXTENSIONS:
            return f"錯誤：不支援舊版格式 {suffix}，請轉存為新版格式（.docx/.xlsx/.pptx）"
        return f"錯誤：不支援的檔案格式 {suffix}。支援的格式：{', '.join(document_reader.SUPPORTED_EXTENSIONS)}"

    # 解析文件
    try:
        result = document_reader.extract_text(str(full_path))

        # 截斷過長的內容
        text = result.text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[內容已截斷，原文共 {len(text)} 字元]"

        # 建立回應
        response = f"📄 **{full_path.name}**\n"
        response += f"格式：{result.format.upper()}\n"
        if result.page_count:
            label = "工作表數" if result.format == "xlsx" else "頁數"
            response += f"{label}：{result.page_count}\n"
        if result.truncated:
            response += "⚠️ 內容已截斷\n"
        if result.error:
            response += f"⚠️ 注意：{result.error}\n"
        response += "\n---\n\n"
        response += text

        return response

    except document_reader.FileTooLargeError as e:
        return f"錯誤：{e}"
    except document_reader.PasswordProtectedError:
        return "錯誤：此文件有密碼保護，無法讀取"
    except document_reader.CorruptedFileError as e:
        return f"錯誤：文件損壞 - {e}"
    except document_reader.UnsupportedFormatError as e:
        return f"錯誤：{e}"
    except Exception as e:
        logger.error(f"read_document 錯誤: {e}")
        return f"錯誤：讀取文件失敗 - {e}"


@mcp.tool()
async def create_share_link(
    resource_type: str,
    resource_id: str,
    expires_in: str | None = "24h",
) -> str:
    """
    建立公開分享連結，讓沒有帳號的人也能查看知識庫或下載檔案

    Args:
        resource_type: 資源類型，可選：
            - knowledge: 知識庫
            - nas_file: NAS 檔案（路徑）
        resource_id: 資源 ID（如 kb-001 或 NAS 檔案路徑）
        expires_in: 有效期限，可選 1h、24h、7d、null（永久），預設 24h

    注意：專案分享功能已遷移至 ERPNext，請直接在 ERPNext 系統操作。
    """
    await ensure_db_connection()

    from .share import (
        create_share_link as _create_share_link,
        ShareError,
        ResourceNotFoundError,
    )
    from ..models.share import ShareLinkCreate

    # 驗證資源類型（專案相關類型已移除，遷移至 ERPNext）
    valid_types = ("knowledge", "nas_file")
    if resource_type not in valid_types:
        if resource_type in ("project", "project_attachment"):
            return "錯誤：專案分享功能已遷移至 ERPNext，請直接在 ERPNext 系統操作：http://ct.erp"
        return f"錯誤：資源類型必須是 {', '.join(valid_types)}，收到：{resource_type}"

    # 驗證有效期限
    valid_expires = {"1h", "24h", "7d", "null", None}
    if expires_in not in valid_expires:
        return f"錯誤：有效期限必須是 1h、24h、7d 或 null（永久），收到：{expires_in}"

    try:
        data = ShareLinkCreate(
            resource_type=resource_type,
            resource_id=resource_id,
            expires_in=expires_in,
        )
        # 使用 system 作為建立者（Line Bot 代理建立）
        result = await _create_share_link(data, "linebot")

        # 轉換為台北時區顯示
        if result.expires_at:
            expires_taipei = to_taipei_time(result.expires_at)
            expires_text = f"有效至 {expires_taipei.strftime('%Y-%m-%d %H:%M')}"
        else:
            expires_text = "永久有效"

        return f"""分享連結已建立！

📎 連結：{result.full_url}
📄 資源：{result.resource_title}
⏰ {expires_text}

可以直接把連結傳給需要查看的人。"""

    except ResourceNotFoundError as e:
        return f"錯誤：找不到資源 - {e}"
    except ShareError as e:
        return f"錯誤：{e}"
    except Exception as e:
        return f"建立分享連結時發生錯誤：{e}"


@mcp.tool()
async def share_knowledge_attachment(
    kb_id: str,
    attachment_idx: int,
    expires_in: str | None = "24h",
) -> str:
    """
    分享知識庫附件（適用於 .md2ppt 或 .md2doc 檔案）

    此工具會：
    1. 讀取知識庫附件內容
    2. 建立分享連結
    3. 根據檔案類型產生對應的前端 URL

    Args:
        kb_id: 知識庫 ID（如 kb-001）
        attachment_idx: 附件索引（從 0 開始，依照知識庫中的附件順序）
        expires_in: 有效期限，可選 1h、24h、7d、null（永久），預設 24h

    Returns:
        分享連結資訊，包含密碼
    """
    await ensure_db_connection()

    from pathlib import Path
    from .knowledge import get_knowledge, get_nas_attachment, KnowledgeNotFoundError, KnowledgeError
    from .share import (
        create_share_link as _create_share_link,
        ShareError,
    )
    from ..models.share import ShareLinkCreate
    from .path_manager import path_manager, StorageZone

    # 驗證有效期限
    valid_expires = {"1h", "24h", "7d", "null", None}
    if expires_in not in valid_expires:
        return f"錯誤：有效期限必須是 1h、24h、7d 或 null（永久），收到：{expires_in}"

    try:
        # 取得知識庫
        knowledge = get_knowledge(kb_id)

        # 檢查附件索引
        if attachment_idx < 0 or attachment_idx >= len(knowledge.attachments):
            return f"錯誤：附件索引 {attachment_idx} 超出範圍，知識 {kb_id} 共有 {len(knowledge.attachments)} 個附件"

        attachment = knowledge.attachments[attachment_idx]
        attachment_path = attachment.path
        filename = Path(attachment_path).name

        # 判斷檔案類型
        ext = Path(filename).suffix.lower()
        if ext not in (".md2ppt", ".md2doc"):
            return f"錯誤：此工具僅支援 .md2ppt 或 .md2doc 檔案，收到：{filename}"

        # 讀取附件內容
        parsed = path_manager.parse(attachment_path)
        if parsed.zone == StorageZone.CTOS and parsed.path.startswith("knowledge/"):
            # CTOS 區的知識庫檔案
            nas_path = parsed.path.replace("knowledge/", "", 1)
            content = get_nas_attachment(nas_path).decode('utf-8')
        elif parsed.zone == StorageZone.LOCAL:
            # 本機檔案
            from .local_file import create_knowledge_file_service
            _, _, assets_path, _ = _get_knowledge_paths()
            file_name_only = parsed.path.split("/")[-1]
            local_path = assets_path / "images" / file_name_only
            content = local_path.read_text(encoding='utf-8')
        else:
            return f"錯誤：不支援的附件路徑格式：{attachment_path}"

        # 建立分享連結（使用 content 類型）
        data = ShareLinkCreate(
            resource_type="content",
            resource_id="",
            content=content,
            content_type="text/markdown",
            filename=filename,
            expires_in=expires_in,
        )
        result = await _create_share_link(data, "linebot")

        # 根據檔案類型產生前端 URL
        from ..config import settings
        if ext == ".md2ppt":
            app_url = f"{settings.md2ppt_url}/?shareToken={result.token}"
            app_name = "MD2PPT"
        else:  # .md2doc
            app_url = f"{settings.md2doc_url}/?shareToken={result.token}"
            app_name = "MD2DOC"

        # 轉換為台北時區顯示
        if result.expires_at:
            expires_taipei = to_taipei_time(result.expires_at)
            expires_text = f"有效至 {expires_taipei.strftime('%Y-%m-%d %H:%M')}"
        else:
            expires_text = "永久有效"

        return f"""已建立 {app_name} 分享連結！

📎 連結：{app_url}
🔑 密碼：{result.password}
📄 檔案：{filename}
⏰ {expires_text}

請將連結和密碼一起傳給需要查看的人。"""

    except KnowledgeNotFoundError as e:
        return f"錯誤：{e}"
    except KnowledgeError as e:
        return f"錯誤：{e}"
    except ShareError as e:
        return f"錯誤：{e}"
    except Exception as e:
        return f"建立分享連結時發生錯誤：{e}"


def _get_knowledge_paths():
    """取得知識庫路徑（內部輔助函數）"""
    from ..config import settings
    from pathlib import Path
    base_path = Path(settings.get_tenant_knowledge_path(None))
    entries_path = base_path / "entries"
    assets_path = base_path / "assets"
    index_path = base_path / "index.json"
    return base_path, entries_path, assets_path, index_path


@mcp.tool()
async def send_nas_file(
    file_path: str,
    line_user_id: str | None = None,
    line_group_id: str | None = None,
    telegram_chat_id: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    直接發送 NAS 檔案給用戶。圖片會直接顯示在對話中，其他檔案會發送下載連結。

    Args:
        file_path: NAS 檔案的完整路徑（從 search_nas_files 取得）
        line_user_id: Line 用戶 ID（個人對話時使用，從【對話識別】取得）
        line_group_id: Line 群組的內部 UUID（群組對話時使用，從【對話識別】取得）
        telegram_chat_id: Telegram chat ID（從【對話識別】取得）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）

    注意：
    - 圖片（jpg/jpeg/png/gif/webp）< 10MB 會直接顯示
    - 其他檔案會發送下載連結
    - 必須提供 line_user_id、line_group_id 或 telegram_chat_id 其中之一
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("send_nas_file", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    # 取得租戶 ID 用於資料庫查詢過濾
    
    from pathlib import Path
    from .share import (
        create_share_link as _create_share_link,
        validate_nas_file_path,
        ShareError,
        NasFileNotFoundError,
        NasFileAccessDenied,
    )
    from ..models.share import ShareLinkCreate

    # 驗證必要參數
    if not line_user_id and not line_group_id and not telegram_chat_id:
        return "錯誤：請從【對話識別】區塊取得 line_user_id、line_group_id 或 telegram_chat_id"

    # 驗證檔案路徑
    try:
        full_path = validate_nas_file_path(file_path)
    except NasFileNotFoundError as e:
        return f"錯誤：{e}"
    except NasFileAccessDenied as e:
        return f"錯誤：{e}"

    # 取得檔案資訊
    file_name = full_path.name
    file_size = full_path.stat().st_size
    file_ext = full_path.suffix.lower().lstrip(".")

    # 判斷是否為圖片
    image_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
    is_image = file_ext in image_extensions

    # 圖片大小限制 10MB
    max_image_size = 10 * 1024 * 1024

    # 產生分享連結
    try:
        data = ShareLinkCreate(
            resource_type="nas_file",
            resource_id=file_path,
            expires_in="24h",
        )
        result = await _create_share_link(data, "linebot")
    except Exception as e:
        return f"建立分享連結失敗：{e}"

    download_url = result.full_url.replace("/s/", "/api/public/") + "/download"
    size_str = f"{file_size / 1024 / 1024:.1f}MB" if file_size >= 1024 * 1024 else f"{file_size / 1024:.1f}KB"

    # === Telegram 發送 ===
    if telegram_chat_id:
        from .bot_telegram.adapter import TelegramBotAdapter
        from ..config import settings as _settings
        if not _settings.telegram_bot_token:
            return "❌ Telegram Bot 未設定"
        try:
            adapter = TelegramBotAdapter(token=_settings.telegram_bot_token)
            if is_image and file_size <= max_image_size:
                await adapter.send_image(telegram_chat_id, download_url)
                return f"已發送圖片：{file_name}"
            else:
                await adapter.send_file(telegram_chat_id, download_url, file_name)
                return f"已發送檔案：{file_name}（{size_str}）"
        except Exception as e:
            # fallback 到連結
            try:
                await adapter.send_text(
                    telegram_chat_id,
                    f"📎 {file_name}（{size_str}）\n{result.full_url}\n⏰ 連結 24 小時內有效",
                )
                return f"檔案直接發送失敗（{e}），已改發連結：{file_name}"
            except Exception as e2:
                return f"無法直接發送（{e2}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"

    # === Line 發送 ===
    from .linebot import push_image, push_text

    # 決定發送目標（優先使用群組 ID）
    # line_group_id 是內部 UUID，需要轉換為 Line group ID
    target_id = None
    if line_group_id:
        # 查詢 Line group ID
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT platform_group_id FROM bot_groups WHERE id = $1",
                UUID(line_group_id),
            )
            if row:
                target_id = row["platform_group_id"]
            else:
                return f"錯誤：找不到群組 {line_group_id}"
    elif line_user_id:
        target_id = line_user_id

    if not target_id:
        return "錯誤：無法確定發送目標"

    # 發送訊息
    try:
        if is_image and file_size <= max_image_size:
            # 小圖片：直接發送 ImageMessage
            message_id, error = await push_image(target_id, download_url)
            if message_id:
                return f"已發送圖片：{file_name}"
            else:
                # 發送圖片失敗，fallback 到連結
                fallback_msg = f"📎 {file_name}\n{result.full_url}\n⏰ 連結 24 小時內有效"
                fallback_id, fallback_error = await push_text(target_id, fallback_msg)
                if fallback_id:
                    return f"圖片發送失敗（{error}），已改發連結：{file_name}"
                else:
                    return f"無法直接發送（{fallback_error}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"
        else:
            # 其他檔案或大圖片：發送連結
            message = f"📎 {file_name}（{size_str}）\n{result.full_url}\n⏰ 連結 24 小時內有效"
            message_id, error = await push_text(target_id, message)
            if message_id:
                return f"已發送檔案連結：{file_name}"
            else:
                return f"無法直接發送（{error}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"
    except Exception as e:
        return f"發送訊息失敗：{e}，連結：{result.full_url}"


# Line ImageMessage 支援的圖片格式
_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
# Line ImageMessage 限制 10MB
_MAX_IMAGE_SIZE = 10 * 1024 * 1024


def _format_file_size(size_bytes: int) -> str:
    """格式化檔案大小為人類可讀的字串"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f}MB"
    return f"{size_bytes / 1024:.1f}KB"


def _build_file_message_info(
    file_name: str,
    file_size: int,
    download_url: str,
    fallback_url: str | None = None,
    extra_fields: dict | None = None,
    is_knowledge: bool = False,
) -> tuple[dict, str]:
    """
    建立檔案訊息資訊

    Args:
        file_name: 檔案名稱
        file_size: 檔案大小（bytes）
        download_url: 下載 URL（圖片用）
        fallback_url: 備用 URL（非圖片檔案用，如果為 None 則使用 download_url）
        extra_fields: 額外欄位（如 nas_path, kb_path）
        is_knowledge: 是否為知識庫附件

    Returns:
        (file_info, hint) 元組
    """
    file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    is_image = file_ext in _IMAGE_EXTENSIONS
    size_str = _format_file_size(file_size)
    prefix = "知識庫" if is_knowledge else ""

    if is_image and file_size <= _MAX_IMAGE_SIZE:
        file_info = {
            "type": "image",
            "url": download_url,
            "name": file_name,
        }
        hint = f"已準備好{prefix}圖片 {file_name}，會顯示在回覆中"
    else:
        file_info = {
            "type": "file",
            "url": fallback_url or download_url,
            "download_url": download_url,
            "name": file_name,
            "size": size_str,
        }
        hint = f"已準備好{prefix}檔案 {file_name}（{size_str}），會以連結形式顯示"

    # 加入額外欄位
    if extra_fields:
        file_info.update(extra_fields)

    return file_info, hint


@mcp.tool()
async def prepare_file_message(
    file_path: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    準備檔案訊息供 Line Bot 回覆。圖片會直接顯示在回覆中，其他檔案會以連結形式呈現。

    Args:
        file_path: 檔案路徑，支援以下格式：
            - NAS 檔案路徑（從 search_nas_files 取得）
            - 知識庫附件路徑（從 get_knowledge_attachments 取得的 attachment.path）
              例如：local://knowledge/assets/images/kb-001-demo.png
                   ctos://knowledge/attachments/kb-001/file.pdf
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）

    Returns:
        包含檔案訊息標記的字串，系統會自動處理並在回覆中顯示圖片或連結
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("prepare_file_message", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    # 取得租戶 ID，用於 CTOS zone 路徑解析
    
    import json
    import re
    from pathlib import Path
    from urllib.parse import quote
    from .share import (
        create_share_link as _create_share_link,
        validate_nas_file_path,
        ShareError,
        NasFileNotFoundError,
        NasFileAccessDenied,
    )
    from .path_manager import path_manager, StorageZone
    from ..models.share import ShareLinkCreate
    from ..config import settings

    # 檢測是否為知識庫附件路徑（local:// 或含有 knowledge 的 ctos://）
    is_knowledge_attachment = (
        file_path.startswith("local://knowledge/") or
        file_path.startswith("ctos://knowledge/") or
        file_path.startswith("nas://knowledge/")
    )

    if is_knowledge_attachment:
        # ===== 知識庫附件處理 =====
        # 使用 path_manager 解析路徑
        try:
            parsed = path_manager.parse(file_path)
            fs_path = Path(path_manager.to_filesystem(file_path))
        except ValueError as e:
            return f"錯誤：無法解析路徑 - {e}"

        if not fs_path.exists():
            return f"錯誤：檔案不存在 - {fs_path.name}"

        # 從檔名或路徑中提取 kb_id
        # 本機附件格式：local://knowledge/assets/images/{kb_id}-{filename}
        # NAS 附件格式：ctos://knowledge/attachments/{kb_id}/{filename}
        file_name = fs_path.name
        kb_id = None

        if parsed.zone == StorageZone.LOCAL:
            # 本機附件：從檔名提取 kb_id（格式：{kb_id}-{filename}）
            match = re.match(r"^(kb-\d+)-", file_name)
            if match:
                kb_id = match.group(1)
        else:
            # NAS 附件：從路徑提取 kb_id（格式：knowledge/attachments/{kb_id}/...）
            path_match = re.search(r"knowledge/attachments/(kb-\d+)/", parsed.path)
            if path_match:
                kb_id = path_match.group(1)

        if not kb_id:
            return f"錯誤：無法從路徑中識別知識庫 ID - {file_path}"

        # 取得檔案資訊
        file_size = fs_path.stat().st_size

        # 為知識文章建立分享連結
        try:
            data = ShareLinkCreate(
                resource_type="knowledge",
                resource_id=kb_id,
                expires_in="24h",
            )
            result = await _create_share_link(data, "linebot")
        except Exception as e:
            return f"建立分享連結失敗：{e}"

        # 組合附件下載 URL
        # 格式：/api/public/{token}/attachments/{encoded_path}
        encoded_path = quote(file_path, safe="")
        download_url = f"{settings.public_url}/api/public/{result.token}/attachments/{encoded_path}"

        # 使用輔助函式組合檔案訊息
        file_info, hint = _build_file_message_info(
            file_name=file_name,
            file_size=file_size,
            download_url=download_url,
            extra_fields={"kb_path": file_path},
            is_knowledge=True,
        )

    else:
        # ===== NAS 檔案處理 =====
        # 驗證檔案路徑
        try:
            full_path = validate_nas_file_path(file_path)
        except NasFileNotFoundError as e:
            return f"錯誤：{e}"
        except NasFileAccessDenied as e:
            return f"錯誤：{e}"

        # 取得檔案資訊
        file_name = full_path.name
        file_size = full_path.stat().st_size

        # 產生分享連結
        try:
            data = ShareLinkCreate(
                resource_type="nas_file",
                resource_id=file_path,
                expires_in="24h",
            )
            result = await _create_share_link(data, "linebot")
        except Exception as e:
            return f"建立分享連結失敗：{e}"

        # 下載連結需要加上 /download（圖片用）
        download_url = result.full_url.replace("/s/", "/api/public/") + "/download"

        # 計算相對於 linebot_local_path 的路徑（用於存 bot_files）
        linebot_base = settings.linebot_local_path
        full_path_str = str(full_path)
        if full_path_str.startswith(linebot_base):
            relative_nas_path = full_path_str[len(linebot_base):].lstrip("/")
        else:
            relative_nas_path = full_path_str  # 其他路徑保持原樣

        # 使用輔助函式組合檔案訊息
        file_info, hint = _build_file_message_info(
            file_name=file_name,
            file_size=file_size,
            download_url=download_url,
            fallback_url=result.full_url,  # 非圖片檔案使用分享連結頁面
            extra_fields={"nas_path": relative_nas_path},
            is_knowledge=False,
        )

    # 回傳標記（linebot_ai.py 會解析這個標記）
    marker = f"[FILE_MESSAGE:{json.dumps(file_info, ensure_ascii=False)}]"

    return f"{hint}\n{marker}"


# ============================================
# 網路圖片下載
# ============================================


@mcp.tool()
async def download_web_image(
    url: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    下載網路圖片並準備為回覆訊息。用於將網路上找到的參考圖片傳送給用戶。

    使用時機：當用戶要求尋找參考圖片、範例圖、示意圖等，透過 WebSearch/WebFetch 找到圖片 URL 後，
    使用此工具下載圖片並傳送給用戶。可多次呼叫以傳送多張圖片（建議不超過 4 張）。

    Args:
        url: 圖片的完整 URL（支援 jpg、jpeg、png、gif、webp 格式）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）

    Returns:
        包含檔案訊息標記的字串，系統會自動在回覆中顯示圖片
    """
    import json
    from .bot.media import download_image_from_url

    local_path = await download_image_from_url(url)
    if not local_path:
        return f"❌ 無法下載圖片：{url}"

    import os
    file_name = os.path.basename(local_path)
    file_info = {
        "type": "image",
        "url": local_path,
        "original_url": url,
        "name": file_name,
    }
    marker = f"[FILE_MESSAGE:{json.dumps(file_info, ensure_ascii=False)}]"
    return f"已下載圖片 {file_name}\n{marker}"


# ============================================
# 專案發包/交貨期程管理
# ============================================


@mcp.tool()
async def convert_pdf_to_images(
    pdf_path: str,
    pages: str = "all",
    output_format: str = "png",
    dpi: int = 150,
    max_pages: int = 20,
    ctos_user_id: int | None = None,
) -> str:
    """
    將 PDF 轉換為圖片

    Args:
        pdf_path: PDF 檔案路徑（NAS 路徑或暫存路徑）
        pages: 要轉換的頁面，預設 "all"
            - "0"：只查詢頁數，不轉換
            - "1"：只轉換第 1 頁
            - "1-3"：轉換第 1 到 3 頁
            - "1,3,5"：轉換第 1、3、5 頁
            - "all"：轉換全部頁面
        output_format: 輸出格式，可選 "png"（預設）或 "jpg"
        dpi: 解析度，預設 150，範圍 72-600
        max_pages: 最大頁數限制，預設 20
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    import json

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("convert_pdf_to_images", ctos_user_id)
    if not allowed:
        return json.dumps({
            "success": False,
            "error": error_msg
        }, ensure_ascii=False)

    # 取得租戶 ID，用於 CTOS zone 路徑解析
        from pathlib import Path as FilePath

    from ..config import settings
    from .document_reader import (
        CorruptedFileError,
        PasswordProtectedError,
        UnsupportedFormatError,
        convert_pdf_to_images as do_convert,
    )

    # 驗證參數
    if output_format not in ("png", "jpg"):
        return json.dumps({
            "success": False,
            "error": f"不支援的輸出格式: {output_format}，請使用 png 或 jpg"
        }, ensure_ascii=False)

    if not 72 <= dpi <= 600:
        return json.dumps({
            "success": False,
            "error": f"DPI 必須在 72-600 之間，目前為 {dpi}"
        }, ensure_ascii=False)

    # 使用 PathManager 解析路徑
    # 支援：nas://..., ctos://..., shared://..., temp://..., /專案A/..., groups/... 等格式
    from .path_manager import path_manager, StorageZone

    try:
        parsed = path_manager.parse(pdf_path)
    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)

    # 安全檢查：只允許 CTOS、SHARED、TEMP 區域
    if parsed.zone not in (StorageZone.CTOS, StorageZone.SHARED, StorageZone.TEMP):
        return json.dumps({
            "success": False,
            "error": f"不允許存取 {parsed.zone.value}:// 區域的檔案"
        }, ensure_ascii=False)

    # 取得實際檔案系統路徑
    actual_path = path_manager.to_filesystem(pdf_path)

    # 檢查檔案存在
    if not FilePath(actual_path).exists():
        return json.dumps({
            "success": False,
            "error": f"PDF 檔案不存在: {pdf_path}"
        }, ensure_ascii=False)

    try:
        # 建立輸出目錄
        today = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")
        unique_id = str(uuid_module.uuid4())[:8]
        output_dir = f"{settings.linebot_local_path}/pdf-converted/{today}/{unique_id}"

        # 執行轉換
        result = do_convert(
            file_path=actual_path,
            output_dir=output_dir,
            pages=pages,
            dpi=dpi,
            output_format=output_format,
            max_pages=max_pages,
        )

        return json.dumps({
            "success": result.success,
            "total_pages": result.total_pages,
            "converted_pages": result.converted_pages,
            "images": result.images,
            "message": result.message,
        }, ensure_ascii=False)

    except FileNotFoundError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except PasswordProtectedError:
        return json.dumps({
            "success": False,
            "error": "此 PDF 有密碼保護，無法轉換"
        }, ensure_ascii=False)
    except UnsupportedFormatError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except CorruptedFileError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except ValueError as e:
        # 頁碼格式錯誤
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"PDF 轉換失敗: {e}")
        return json.dumps({
            "success": False,
            "error": f"轉換失敗: {str(e)}"
        }, ensure_ascii=False)


# ============================================================
# 廠商管理工具
# ============================================================


@mcp.tool()
async def generate_presentation(
    topic: str = "",
    num_slides: int = 5,
    theme: str = "uncover",
    include_images: bool = True,
    image_source: str = "pexels",
    outline_json: str | dict | None = None,
    output_format: str = "html",
) -> str:
    """
    生成簡報（HTML 或 PDF，使用 Marp）

    生成的簡報支援 HTML（瀏覽器直接查看）或 PDF（下載列印）格式。

    有兩種使用方式：

    方式一：只給主題，AI 自動生成大綱（較慢，約 30-60 秒）
        generate_presentation(topic="AI 在製造業的應用", num_slides=5)

    方式二：傳入完整大綱 JSON，直接製作簡報（推薦用於知識庫內容）
        1. 先用 search_knowledge / get_knowledge_item 查詢相關知識
        2. 根據知識內容組織大綱 JSON
        3. 呼叫 generate_presentation(outline_json="...")
        4. 用 create_share_link 產生分享連結回覆用戶

    Args:
        topic: 簡報主題（方式一必填，方式二可省略）
        num_slides: 頁數，預設 5 頁（範圍 2-20，方式一使用）
        theme: Marp 內建主題風格，可選：
            - uncover: 深色投影（深灰背景），適合晚間活動、影片風格（預設）
            - gaia: 暖色調（米黃/棕色背景），適合輕鬆場合
            - gaia-invert: 專業藍（深藍背景），適合正式提案、投影展示
            - default: 簡約白（白底黑字），適合技術文件、學術報告
        include_images: 是否自動配圖，預設 True
        image_source: 圖片來源，可選：
            - pexels: 從 Pexels 圖庫下載（預設，快速）
            - huggingface: 使用 Hugging Face FLUX AI 生成
            - nanobanana: 使用 nanobanana/Gemini AI 生成
        outline_json: 直接傳入大綱 JSON 字串，跳過 AI 生成步驟。格式範例：
            {
                "title": "簡報標題",
                "slides": [
                    {"type": "title", "title": "標題", "subtitle": "副標題"},
                    {"type": "content", "title": "第一章", "content": ["重點1", "重點2"], "image_keyword": "factory automation"}
                ]
            }
            type 類型：title（封面）、section（章節分隔）、content（標題+內容）
        output_format: 輸出格式，可選：
            - html: 網頁格式，可直接在瀏覽器查看（預設）
            - pdf: PDF 格式，可下載列印

    Returns:
        包含簡報資訊和 NAS 路徑的回應，可用於 create_share_link
    """
    from ..services.presentation import generate_html_presentation

    # 驗證：必須有 topic 或 outline_json
    if not topic and not outline_json:
        return "❌ 請提供 topic（主題）或 outline_json（大綱 JSON）"

    # 驗證頁數範圍
    if not outline_json:
        if num_slides < 2:
            num_slides = 2
        elif num_slides > 20:
            num_slides = 20

    # 驗證主題
    valid_themes = ["default", "gaia", "gaia-invert", "uncover"]
    if theme not in valid_themes:
        return (
            f"❌ 無效的主題：{theme}\n"
            f"可用主題：\n"
            f"  - gaia（專業藍）：正式提案、投影展示\n"
            f"  - gaia-invert（亮色藍）：列印、螢幕閱讀\n"
            f"  - default（簡約白）：技術文件、學術報告\n"
            f"  - uncover（深色投影）：晚間活動、影片風格"
        )

    # 驗證輸出格式
    valid_formats = ["html", "pdf"]
    if output_format not in valid_formats:
        return f"❌ 無效的輸出格式：{output_format}\n可用格式：html（網頁）、pdf（列印）"

    # 驗證圖片來源
    valid_image_sources = ["pexels", "huggingface", "nanobanana"]
    if image_source not in valid_image_sources:
        return f"❌ 無效的圖片來源：{image_source}\n可用來源：pexels（圖庫）、huggingface（AI）、nanobanana（Gemini）"

    # 將 dict 轉換為 JSON 字串
    import json as _json
    if isinstance(outline_json, dict):
        outline_json = _json.dumps(outline_json, ensure_ascii=False)

    # 取得租戶 ID
    
    try:
        result = await generate_html_presentation(
            topic=topic or "簡報",
            num_slides=num_slides,
            theme=theme,
            include_images=include_images,
            image_source=image_source,
            outline_json=outline_json,
            output_format=output_format,
        )

        theme_names = {
            "default": "簡約白",
            "gaia": "專業藍",
            "gaia-invert": "亮色藍",
            "uncover": "深色投影",
        }

        image_source_names = {
            "pexels": "Pexels 圖庫",
            "huggingface": "Hugging Face AI",
            "nanobanana": "Gemini AI",
        }

        format_names = {
            "html": "HTML（可直接在瀏覽器查看）",
            "pdf": "PDF（可下載列印）",
        }

        # 產生 NAS 檔案路徑（供 create_share_link 使用）
        nas_file_path = f"ctos://{result['nas_path']}"

        image_info = f"{'有（' + image_source_names.get(image_source, image_source) + '）' if include_images else '無'}"
        theme_display = theme_names.get(theme, theme)
        format_display = format_names.get(output_format, output_format)

        return (
            f"✅ 簡報生成完成！\n\n"
            f"📊 {result['title']}\n"
            f"・頁數：{result['slides_count']} 頁\n"
            f"・主題：{theme_display}\n"
            f"・配圖：{image_info}\n"
            f"・格式：{format_display}\n\n"
            f"📁 NAS 路徑：{nas_file_path}\n\n"
            f"💡 下一步：使用 create_share_link(resource_type=\"nas_file\", resource_id=\"{nas_file_path}\") 產生分享連結"
        )

    except Exception as e:
        logger.error(f"生成簡報失敗: {e}")
        return f"❌ 生成簡報時發生錯誤：{str(e)}\n請稍後重試或調整內容"


# ============================================================
# 記憶管理工具
# ============================================================


@mcp.tool()
async def add_memory(
    content: str,
    title: str | None = None,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
) -> str:
    """
    新增記憶

    Args:
        content: 記憶內容（必填）
        title: 記憶標題（方便識別），若未提供系統會自動產生
        line_group_id: Line 群組的內部 UUID（群組對話時使用，從對話識別取得）
        line_user_id: Line 用戶 ID（個人對話時使用，從對話識別取得）
    """
    await ensure_db_connection()

    # 自動產生標題（取 content 前 20 字）
    if not title:
        title = content[:20] + ("..." if len(content) > 20 else "")

    if line_group_id:
        # 群組記憶
        try:
            group_uuid = UUID(line_group_id)
        except ValueError:
            return "❌ 群組 ID 格式錯誤"

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO bot_group_memories (bot_group_id, title, content)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                group_uuid,
                title,
                content,
            )
            return f"✅ 已新增群組記憶：{title}\n記憶 ID：{row['id']}"

    elif line_user_id:
        # 個人記憶：需要查詢用戶的內部 UUID
        from .linebot import get_line_user_record
        user_row = await get_line_user_record(line_user_id, "id")
        if not user_row:
            return "❌ 找不到用戶"

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO bot_user_memories (bot_user_id, title, content)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                user_row["id"],
                title,
                content,
            )
            return f"✅ 已新增個人記憶：{title}\n記憶 ID：{row['id']}"
    else:
        return "❌ 請提供 line_group_id 或 line_user_id"


@mcp.tool()
async def get_memories(
    line_group_id: str | None = None,
    line_user_id: str | None = None,
) -> str:
    """
    查詢記憶

    Args:
        line_group_id: Line 群組的內部 UUID（群組對話時使用，從對話識別取得）
        line_user_id: Line 用戶 ID（個人對話時使用，從對話識別取得）
    """
    await ensure_db_connection()

    if line_group_id:
        # 群組記憶
        try:
            group_uuid = UUID(line_group_id)
        except ValueError:
            return "❌ 群組 ID 格式錯誤"

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, content, is_active, created_at
                FROM bot_group_memories
                WHERE bot_group_id = $1
                ORDER BY created_at DESC
                """,
                group_uuid,
            )

            if not rows:
                return "目前沒有設定任何記憶"

            result = "📝 **群組記憶列表**\n\n"
            for row in rows:
                status = "✅" if row["is_active"] else "❌"
                created = to_taipei_time(row["created_at"]).strftime("%Y-%m-%d %H:%M")
                result += f"**{row['title']}** {status}\n"
                result += f"ID: `{row['id']}`\n"
                result += f"內容: {row['content'][:100]}{'...' if len(row['content']) > 100 else ''}\n"
                result += f"建立時間: {created}\n\n"
            return result

    elif line_user_id:
        # 個人記憶
        from .linebot import get_line_user_record
        user_row = await get_line_user_record(line_user_id, "id")
        if not user_row:
            return "❌ 找不到用戶"

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, content, is_active, created_at
                FROM bot_user_memories
                WHERE bot_user_id = $1
                ORDER BY created_at DESC
                """,
                user_row["id"],
            )

        if not rows:
            return "目前沒有設定任何記憶"

        result = "📝 **個人記憶列表**\n\n"
        for row in rows:
            status = "✅" if row["is_active"] else "❌"
            created = to_taipei_time(row["created_at"]).strftime("%Y-%m-%d %H:%M")
            result += f"**{row['title']}** {status}\n"
            result += f"ID: `{row['id']}`\n"
            result += f"內容: {row['content'][:100]}{'...' if len(row['content']) > 100 else ''}\n"
            result += f"建立時間: {created}\n\n"
        return result
    else:
        return "❌ 請提供 line_group_id 或 line_user_id"


@mcp.tool()
async def update_memory(
    memory_id: str,
    title: str | None = None,
    content: str | None = None,
    is_active: bool | None = None,
) -> str:
    """
    更新記憶

    Args:
        memory_id: 記憶 UUID（必填）
        title: 新標題
        content: 新內容
        is_active: 是否啟用（true/false）
    """
    await ensure_db_connection()

    try:
        memory_uuid = UUID(memory_id)
    except ValueError:
        return "❌ 記憶 ID 格式錯誤"

    # 建構更新欄位
    update_fields = []
    params = [memory_uuid]
    param_idx = 2

    if title is not None:
        update_fields.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1
    if content is not None:
        update_fields.append(f"content = ${param_idx}")
        params.append(content)
        param_idx += 1
    if is_active is not None:
        update_fields.append(f"is_active = ${param_idx}")
        params.append(is_active)
        param_idx += 1

    if not update_fields:
        return "❌ 請提供要更新的欄位（title、content 或 is_active）"

    update_fields.append("updated_at = NOW()")
    set_clause = ", ".join(update_fields)

    async with get_connection() as conn:
        # 先嘗試更新群組記憶
        result = await conn.execute(
            f"UPDATE bot_group_memories SET {set_clause} WHERE id = $1",
            *params,
        )
        if result == "UPDATE 1":
            return f"✅ 已更新群組記憶"

        # 再嘗試更新個人記憶
        result = await conn.execute(
            f"UPDATE bot_user_memories SET {set_clause} WHERE id = $1",
            *params,
        )
        if result == "UPDATE 1":
            return f"✅ 已更新個人記憶"

        return "❌ 找不到指定的記憶"


@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """
    刪除記憶

    Args:
        memory_id: 記憶 UUID（必填）
    """
    await ensure_db_connection()

    try:
        memory_uuid = UUID(memory_id)
    except ValueError:
        return "❌ 記憶 ID 格式錯誤"

    async with get_connection() as conn:
        # 先嘗試刪除群組記憶
        result = await conn.execute(
            "DELETE FROM bot_group_memories WHERE id = $1",
            memory_uuid,
        )
        if result == "DELETE 1":
            return "✅ 已刪除群組記憶"

        # 再嘗試刪除個人記憶
        result = await conn.execute(
            "DELETE FROM bot_user_memories WHERE id = $1",
            memory_uuid,
        )
        if result == "DELETE 1":
            return "✅ 已刪除個人記憶"

        return "❌ 找不到指定的記憶"


# ============================================================
# MD2PPT / MD2DOC 簡報與文件生成
# ============================================================

# MD2PPT System Prompt
MD2PPT_SYSTEM_PROMPT = '''你是專業的 MD2PPT-Evolution 簡報設計師。直接輸出 Markdown 代碼，不要包含解釋文字或 ``` 標記。

## 格式結構

### 1. 全域 Frontmatter（檔案開頭必須有）
```
---
title: "簡報標題"
author: "作者"
bg: "#FFFFFF"
transition: fade
---
```
- theme 可選：amber, midnight, academic, material
- transition 可選：slide, fade, zoom, none

### 2. 分頁符號
用 `===` 分隔頁面，前後必須有空行：
```
（前一頁內容）

===

（下一頁內容）
```

### 3. 每頁 Frontmatter（在 === 後）
```
===

---
layout: impact
bg: "#EA580C"
---

# 標題
```

### 4. Layout 選項
- `default`：標準頁面
- `impact`：強調頁（適合重點、開場）
- `center`：置中頁
- `grid`：網格（搭配 `columns: 2`）
- `two-column`：雙欄（用 `:: right ::` 分隔）
- `quote`：引言頁
- `alert`：警告/重點提示頁

### 5. 雙欄語法（two-column 或 grid）
`:: right ::` 前後必須有空行：
```
### 左欄標題
左欄內容

:: right ::

### 右欄標題
右欄內容
```

### 6. 圖表語法
JSON 必須用雙引號，前後必須有空行：
```
::: chart-bar { "title": "標題", "showValues": true }

| 類別 | 數值 |
| :--- | :--- |
| A | 100 |
| B | 200 |

:::
```
圖表類型：chart-bar, chart-line, chart-pie, chart-area

### 7. Mesh 漸層背景
```
---
bg: mesh
mesh:
  colors: ["#4158D0", "#C850C0", "#FFCC70"]
  seed: 12345
---
```

### 8. 背景圖片
```
---
bgImage: "https://images.unsplash.com/..."
---
```

### 9. 備忘錄（演講者筆記）
```
<!-- note:
這是演講者備忘錄，觀眾看不到。
-->
```

### 10. 對話模式
```
User ":: 這是用戶說的話（靠左）

AI ::" 這是 AI 回覆（靠右）

系統 :": 這是系統提示（置中）
```

### 11. 程式碼區塊
```typescript
const hello = "world";
```

## 配色建議

| 風格 | theme | mesh 配色 | 適用場景 |
|------|-------|----------|---------|
| 科技藍 | midnight | ["#0F172A", "#1E40AF", "#3B82F6"] | 科技、AI、軟體 |
| 溫暖橙 | amber | ["#FFF7ED", "#FB923C", "#EA580C"] | 行銷、活動、創意 |
| 清新綠 | material | ["#ECFDF5", "#10B981", "#047857"] | 環保、健康、自然 |
| 極簡灰 | academic | ["#F8FAFC", "#94A3B8", "#475569"] | 學術、報告、正式 |
| 電競紫 | midnight | ["#111827", "#7C3AED", "#DB2777"] | 遊戲、娛樂、年輕 |

## 設計原則

1. **標題/重點頁**（impact/center/quote）→ 用 `bg: mesh` 或鮮明純色
2. **資訊頁**（grid/two-column/default）→ 用淺色純色（#F8FAFC）或深色（#1E293B）
3. **不要每頁都用 mesh**，會視覺疲勞
4. **圖表數據要合理**，數值要有意義

## 完整範例

---
title: "產品發表會"
author: "產品團隊"
bg: "#FFFFFF"
transition: fade
---

# 產品發表會
## 創新解決方案 2026

===

---
layout: impact
bg: mesh
mesh:
  colors: ["#0F172A", "#1E40AF", "#3B82F6"]
---

# 歡迎各位
## 今天我們將介紹全新產品線

===

---
layout: grid
columns: 2
bg: "#F8FAFC"
---

# 市場分析

### 現況
- 市場規模持續成長
- 客戶需求多元化
- 競爭日益激烈

### 機會
- 數位轉型趨勢
- AI 技術成熟
- 新興市場開拓

===

---
layout: two-column
bg: "#F8FAFC"
---

# 產品特色

### 核心功能
- 智能分析
- 即時監控
- 自動化流程

:: right ::

### 技術優勢
- 高效能運算
- 安全加密
- 彈性擴展

===

---
layout: grid
columns: 2
bg: "#F8FAFC"
---

# 業績表現

::: chart-bar { "title": "季度營收", "showValues": true }

| 季度 | 營收 |
| :--- | :--- |
| Q1 | 150 |
| Q2 | 200 |
| Q3 | 280 |
| Q4 | 350 |

:::

::: chart-pie { "title": "市場佔比" }

| 區域 | 佔比 |
| :--- | :--- |
| 北區 | 40 |
| 中區 | 35 |
| 南區 | 25 |

:::

===

---
layout: center
bg: mesh
mesh:
  colors: ["#0F172A", "#1E40AF", "#3B82F6"]
---

# 感謝聆聽
## 歡迎提問
'''

# MD2DOC System Prompt
MD2DOC_SYSTEM_PROMPT = '''你是專業的 MD2DOC-Evolution 技術文件撰寫專家。直接輸出 Markdown 代碼，不要包含解釋文字或 ``` 標記。

## 格式結構

### 1. Frontmatter（檔案開頭必須有）
```
---
title: "文件標題"
author: "作者名稱"
header: true
footer: true
---
```
- title 和 author 為必填欄位
- header/footer 控制頁首頁尾顯示

### 2. 標題層級
- 只支援 H1 (#)、H2 (##)、H3 (###)
- H4 以下請改用 **粗體文字** 或列表項目

### 3. 目錄（可選）
```
[TOC]
- 第一章 章節名稱 1
- 第二章 章節名稱 2
```

### 4. 提示區塊 (Callouts)
只支援三種類型：
```
> [!TIP]
> **提示標題**
> 提示內容，用於分享小撇步或最佳實踐。

> [!NOTE]
> **筆記標題**
> 筆記內容，用於補充背景知識。

> [!WARNING]
> **警告標題**
> 警告內容，用於重要注意事項。
```

### 5. 對話模式 (Chat Syntax)
```
系統 :": 這是置中的系統訊息。

AI助手 ":: 這是靠左的 AI 回覆，使用 `"::` 語法。

用戶 ::" 這是靠右的用戶訊息，使用 `::"` 語法。
```

### 6. 程式碼區塊
```typescript
// 預設顯示行號，右上角顯示語言名稱
const config = {
  name: "example"
};
```

隱藏行號（適合短設定檔）：
```json:no-ln
{
  "name": "config",
  "version": "1.0.0"
}
```

強制顯示行號：
```bash:ln
npm install
npm run dev
```

### 7. 行內樣式
- **粗體**：`**文字**` → **文字**
- *斜體*：`*文字*` → *文字*
- <u>底線</u>：`<u>文字</u>` → <u>底線</u>
- `行內程式碼`：反引號包覆
- UI 按鈕：`【確定】` → 【確定】
- 快捷鍵：`[Ctrl]` + `[S]` → [Ctrl] + [S]
- 書名/專案名：`『書名』` → 『書名』
- 智慧連結：`[文字](URL)` → 匯出 Word 時自動生成 QR Code

### 8. 表格
```
| 欄位一 | 欄位二 | 欄位三 |
| --- | --- | --- |
| 內容 | 內容 | 內容 |
```

### 9. 列表
- 第一項
- 第二項
  - 巢狀項目（縮排 2 空格）
  - 巢狀項目

### 10. 分隔線
```
---
```

### 11. Mermaid 圖表（可選）
```mermaid
graph TD
    A[開始] --> B{判斷}
    B -- Yes --> C[執行]
    B -- No --> D[結束]
```

## 設計原則

1. **結構清晰**：使用 H1 作為大章節，H2 作為小節，H3 作為細項
2. **善用 Callouts**：重要提示用 TIP，補充說明用 NOTE，警告事項用 WARNING
3. **程式碼標註語言**：所有程式碼區塊都要標註語言（typescript, json, bash, python 等）
4. **表格對齊**：表格內容盡量簡潔，複雜內容用列表呈現

## 完整範例

---
title: "系統操作手冊"
author: "技術團隊"
header: true
footer: true
---

# 系統操作手冊

[TOC]
- 第一章 系統介紹 1
- 第二章 基本操作 2
- 第三章 進階功能 3

## 1. 系統介紹

本系統是專為企業設計的管理平台，提供 **完整的資料管理** 與 *即時監控* 功能。

> [!TIP]
> **快速開始**
> 首次使用請先完成帳號設定，詳見第二章說明。

---

## 2. 基本操作

### 2.1 登入系統

1. 開啟瀏覽器，輸入系統網址
2. 輸入帳號密碼
3. 點擊 【登入】 按鈕

> [!NOTE]
> **帳號格式**
> 帳號格式為 `員工編號@公司代碼`，例如：`A001@acme`

### 2.2 常用快捷鍵

| 功能 | Windows | Mac |
| --- | --- | --- |
| 儲存 | [Ctrl] + [S] | [Cmd] + [S] |
| 搜尋 | [Ctrl] + [F] | [Cmd] + [F] |
| 列印 | [Ctrl] + [P] | [Cmd] + [P] |

---

## 3. 進階功能

### 3.1 API 整合

系統提供 RESTful API，可與外部系統整合：

```typescript
// 取得使用者資料
const response = await fetch('/api/users', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
```

設定檔範例：

```json:no-ln
{
  "apiUrl": "https://api.example.com",
  "timeout": 30000
}
```

> [!WARNING]
> **安全注意**
> API Token 請妥善保管，切勿分享給他人或提交到版本控制系統。

---

### 3.2 常見問題

系統 :": 以下是常見問題的對話範例。

用戶 ::" 我忘記密碼了，該怎麼辦？

客服 ":: 您可以點擊登入頁面的「忘記密碼」連結，系統會發送重設信件到您的註冊信箱。

---

更多資訊請參考『系統管理指南』或聯繫技術支援。
'''


def fix_md2ppt_format(content: str) -> str:
    """
    自動修正 MD2PPT 常見格式問題

    修正項目：
    1. === 分頁符前後空行
    2. :: right :: 前後空行
    3. ::: chart-xxx 前後空行
    4. ::: 結束標記前空行
    5. JSON 單引號改雙引號
    6. 無效 theme 替換為 midnight
    7. 無效 layout 替換為 default
    8. 移除 ``` 標記
    """
    import re
    import json

    # 移除可能的 markdown 標記
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    # 有效的 theme 和 layout 值
    valid_themes = {"amber", "midnight", "academic", "material"}
    valid_layouts = {"default", "impact", "center", "grid", "two-column", "quote", "alert"}

    # 修正 theme 無效值
    def fix_theme(match):
        theme = match.group(1).strip('"\'')
        if theme not in valid_themes:
            return "theme: midnight"
        return match.group(0)

    content = re.sub(r'^theme:\s*(\S+)', fix_theme, content, flags=re.MULTILINE)

    # 修正 layout 無效值
    def fix_layout(match):
        layout = match.group(1).strip('"\'')
        if layout not in valid_layouts:
            return "layout: default"
        return match.group(0)

    content = re.sub(r'^layout:\s*(\S+)', fix_layout, content, flags=re.MULTILINE)

    # 修正圖表 JSON 中的單引號
    def fix_chart_json(match):
        prefix = match.group(1)  # ::: chart-xxx
        json_str = match.group(2)  # { ... }
        if json_str:
            # 嘗試修正單引號
            try:
                json.loads(json_str)
            except json.JSONDecodeError:
                # 嘗試將單引號替換為雙引號
                fixed_json = json_str.replace("'", '"')
                try:
                    json.loads(fixed_json)
                    return f"{prefix} {fixed_json}"
                except json.JSONDecodeError:
                    pass  # 無法修正，保持原樣
        return match.group(0)

    content = re.sub(
        r'^(:::[\s]*chart-\w+)\s*(\{[^}]+\})',
        fix_chart_json,
        content,
        flags=re.MULTILINE
    )

    # 修正空行問題
    lines = content.split('\n')
    result = []

    # 正則模式
    right_col_pattern = re.compile(r'^(\s*)::[\s]*right[\s]*::[\s]*$', re.IGNORECASE)
    page_break_pattern = re.compile(r'^[\s]*===[\s]*$')
    block_end_pattern = re.compile(r'^[\s]*:::[\s]*$')
    chart_start_pattern = re.compile(r'^[\s]*:::[\s]*chart', re.IGNORECASE)
    frontmatter_pattern = re.compile(r'^---\s*$')

    for i, line in enumerate(lines):
        stripped = line.strip()
        is_right_col = right_col_pattern.match(line)
        is_page_break = page_break_pattern.match(line)
        is_block_end = block_end_pattern.match(line)
        is_chart_start = chart_start_pattern.match(line)

        # 這些模式前面需要空行
        if is_right_col or is_page_break or is_block_end or is_chart_start:
            # 確保前面有空行（除非是檔案開頭或前一行是 frontmatter）
            if result and result[-1].strip() != '' and not frontmatter_pattern.match(result[-1]):
                result.append('')
            result.append(line)
        else:
            # 檢查前一行是否是需要後面空行的模式
            if result:
                prev_line = result[-1]
                need_blank = (
                    right_col_pattern.match(prev_line) or
                    page_break_pattern.match(prev_line) or
                    chart_start_pattern.match(prev_line) or
                    block_end_pattern.match(prev_line)
                )
                if need_blank and stripped != '':
                    result.append('')
            result.append(line)

    return '\n'.join(result)


def fix_md2doc_format(content: str) -> str:
    """
    自動修正 MD2DOC 常見格式問題

    修正項目：
    1. 移除 ``` 標記
    2. 確保有 frontmatter
    3. H4+ 標題轉換為粗體
    4. 修正 Callout 格式
    """
    import re

    # 移除可能的 markdown 標記
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    # 確保有 frontmatter（如果沒有就加上基本的）
    if not content.strip().startswith("---"):
        content = """---
title: "文件"
author: "AI Assistant"
---

""" + content

    # 修正 H4+ 標題為粗體
    def fix_heading(match):
        level = len(match.group(1))
        text = match.group(2).strip()
        if level >= 4:
            return f"**{text}**"
        return match.group(0)

    content = re.sub(r'^(#{4,})\s+(.+)$', fix_heading, content, flags=re.MULTILINE)

    # 修正 Callout 類型（只允許 TIP, NOTE, WARNING）
    valid_callouts = {"TIP", "NOTE", "WARNING"}

    def fix_callout(match):
        callout_type = match.group(1).upper()
        if callout_type not in valid_callouts:
            # 映射常見的錯誤類型
            mapping = {
                "INFO": "NOTE",
                "IMPORTANT": "WARNING",
                "CAUTION": "WARNING",
                "DANGER": "WARNING",
                "HINT": "TIP",
            }
            fixed_type = mapping.get(callout_type, "NOTE")
            return f"> [!{fixed_type}]"
        return match.group(0)

    content = re.sub(r'>\s*\[!(\w+)\]', fix_callout, content)

    return content


@mcp.tool()
async def generate_md2ppt(
    content: str,
    style: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    產生 MD2PPT 格式的簡報內容，並建立帶密碼保護的分享連結

    用戶說「做簡報」「投影片」「PPT」時呼叫此工具。
    與 generate_presentation（Marp HTML/PDF）不同，此工具產生可線上編輯的簡報。

    Args:
        content: 要轉換為簡報的內容或主題
        style: 風格需求（如：科技藍、簡約深色），不填則自動選擇
        ctos_user_id: CTOS 用戶 ID（從對話識別取得）

    Returns:
        分享連結和存取密碼
    """
    from .claude_agent import call_claude
    from .share import create_share_link
    from ..models.share import ShareLinkCreate

    await ensure_db_connection()
    
    # 組合 prompt
    style_hint = f"【風格需求】：{style}\n" if style else ""
    user_prompt = f"{style_hint}【內容】：\n{content}"

    try:
        logger.debug(f"generate_md2ppt: prompt_len={len(user_prompt)}")

        # 呼叫 Claude 產生內容
        response = await call_claude(
            prompt=user_prompt,
            model="sonnet",
            system_prompt=MD2PPT_SYSTEM_PROMPT,
            timeout=180,
        )

        if not response.success:
            logger.warning(f"generate_md2ppt: AI 失敗: {response.error}")
            return f"❌ AI 產生失敗：{response.error}"

        generated_content = response.message.strip()

        # 自動修正格式問題（不驗證、不重試）
        generated_content = fix_md2ppt_format(generated_content)

        # 建立分享連結
        share_data = ShareLinkCreate(
            resource_type="content",
            content=generated_content,
            content_type="text/markdown",
            filename="presentation.md2ppt",
            expires_in="24h",
        )

        share_link = await create_share_link(
            data=share_data,
            created_by="linebot-ai",
        )

        # 產生 MD2PPT 連結
        from ..config import settings
        md2ppt_url = f"{settings.md2ppt_url}/?shareToken={share_link.token}"

        # 同時保存檔案到 NAS，以便加入知識庫附件
        from pathlib import Path
        import uuid

        file_id = str(uuid.uuid4())[:8]
        filename = f"presentation-{file_id}.md2ppt"

        # 保存到 ai-generated 目錄
        save_dir = Path(settings.ctos_mount_path) / "linebot" / "files" / "ai-generated"

        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename
        save_path.write_text(generated_content, encoding="utf-8")

        # 產生可用於 add_attachments_to_knowledge 的路徑
        attachment_path = f"ai-generated/{filename}"

        return f"""✅ 簡報產生成功！

🔗 開啟連結：{md2ppt_url}
🔑 存取密碼：{share_link.password}

📎 檔案路徑：{attachment_path}
（可用 add_attachments_to_knowledge 加入知識庫附件）

⏰ 連結有效期限：24 小時
💡 開啟後可直接編輯並匯出為 PPT"""

    except Exception as e:
        logger.error(f"generate_md2ppt 錯誤: {e}")
        return f"❌ 產生簡報時發生錯誤：{str(e)}"


@mcp.tool()
async def generate_md2doc(
    content: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    產生 MD2DOC 格式的文件內容，並建立帶密碼保護的分享連結

    用戶說「寫文件」「做報告」「說明書」「教學」「SOP」時呼叫此工具。

    Args:
        content: 要轉換為文件的內容
        ctos_user_id: CTOS 用戶 ID（從對話識別取得）

    Returns:
        分享連結和存取密碼
    """
    from .claude_agent import call_claude
    from .share import create_share_link
    from ..models.share import ShareLinkCreate

    await ensure_db_connection()
    
    user_prompt = f"請將以下內容轉換為 MD2DOC 格式的文件：\n\n{content}"

    try:
        logger.debug(f"generate_md2doc: prompt_len={len(user_prompt)}")

        # 呼叫 Claude 產生內容
        response = await call_claude(
            prompt=user_prompt,
            model="sonnet",
            system_prompt=MD2DOC_SYSTEM_PROMPT,
            timeout=180,
        )

        if not response.success:
            logger.warning(f"generate_md2doc: AI 失敗: {response.error}")
            return f"❌ AI 產生失敗：{response.error}"

        generated_content = response.message.strip()

        # 自動修正格式問題（不驗證、不重試）
        generated_content = fix_md2doc_format(generated_content)

        # 建立分享連結
        share_data = ShareLinkCreate(
            resource_type="content",
            content=generated_content,
            content_type="text/markdown",
            filename="document.md2doc",
            expires_in="24h",
        )

        share_link = await create_share_link(
            data=share_data,
            created_by="linebot-ai",
        )

        # 產生 MD2DOC 連結
        from ..config import settings
        md2doc_url = f"{settings.md2doc_url}/?shareToken={share_link.token}"

        # 同時保存檔案到 NAS，以便加入知識庫附件
        from pathlib import Path
        import uuid

        file_id = str(uuid.uuid4())[:8]
        filename = f"document-{file_id}.md2doc"

        # 保存到 ai-generated 目錄
        save_dir = Path(settings.ctos_mount_path) / "linebot" / "files" / "ai-generated"

        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename
        save_path.write_text(generated_content, encoding="utf-8")

        # 產生可用於 add_attachments_to_knowledge 的路徑
        attachment_path = f"ai-generated/{filename}"

        return f"""✅ 文件產生成功！

🔗 開啟連結：{md2doc_url}
🔑 存取密碼：{share_link.password}

📎 檔案路徑：{attachment_path}
（可用 add_attachments_to_knowledge 加入知識庫附件）

⏰ 連結有效期限：24 小時
💡 開啟後可直接編輯並匯出為 Word"""

    except Exception as e:
        logger.error(f"generate_md2doc 錯誤: {e}")
        return f"❌ 產生文件時發生錯誤：{str(e)}"


# ============================================================
# 列印前置處理工具
# ============================================================

# 需透過 LibreOffice 轉 PDF 的格式
OFFICE_EXTENSIONS = {
    ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt",
    ".odt", ".ods", ".odp",
}

# printer-mcp 可直接列印的格式
PRINTABLE_EXTENSIONS = {
    ".pdf", ".txt", ".log", ".csv",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp",
}

# 允許存取的路徑前綴
ALLOWED_PRINT_PATHS = ("/mnt/nas/", "/tmp/ctos/")


@mcp.tool()
async def prepare_print_file(
    file_path: str,
    ctos_user_id: int | None = None,
) -> str:
    """將虛擬路徑轉換為可列印的絕對路徑，Office 文件會自動轉為 PDF

    【重要】此工具只負責路徑轉換和格式轉換，不會執行列印。
    取得回傳的絕對路徑後，請接著呼叫 printer-mcp 的 print_file 工具進行實際列印。

    列印完整流程：
    1. 呼叫 prepare_print_file 取得絕對路徑
    2. 呼叫 printer-mcp 的 print_file(file_path=回傳的路徑) 進行列印

    file_path 可以是：
    - 虛擬路徑：ctos://knowledge/attachments/report.pdf、shared://projects/...
    - 絕對路徑：/mnt/nas/ctos/...

    支援的檔案格式：
    - 直接可印：PDF、純文字（.txt, .log, .csv）、圖片（PNG, JPG, JPEG, GIF, BMP, TIFF, WebP）
    - 自動轉 PDF：Office 文件（.docx, .xlsx, .pptx, .doc, .xls, .ppt, .odt, .ods, .odp）
    """
    await ensure_db_connection()
    if ctos_user_id:
        allowed, error_msg = await check_mcp_tool_permission("prepare_print_file", ctos_user_id)
        if not allowed:
            return f"❌ {error_msg}"

    import asyncio as _asyncio
    from pathlib import Path

    # 路徑轉換：虛擬路徑 → 絕對路徑
    try:
        from .path_manager import path_manager

        if "://" in file_path:
            actual_path = Path(path_manager.to_filesystem(file_path))
        else:
            actual_path = Path(file_path)
    except Exception as e:
        return f"❌ 路徑解析失敗：{str(e)}"

    # 取得實際絕對路徑（解析 symlink）
    try:
        actual_path = actual_path.resolve()
    except Exception:
        pass

    # 安全檢查
    actual_str = str(actual_path)
    if ".." in file_path:
        return "❌ 不允許的路徑（禁止路徑穿越）"

    if not any(actual_str.startswith(prefix) for prefix in ALLOWED_PRINT_PATHS):
        return "❌ 不允許存取此路徑的檔案。僅允許 NAS 和暫存目錄中的檔案。"

    # 檢查檔案存在
    if not actual_path.exists():
        return f"❌ 檔案不存在：{file_path}"

    if not actual_path.is_file():
        return f"❌ 路徑不是檔案：{file_path}"

    # 檢查檔案格式
    ext = actual_path.suffix.lower()

    if ext in PRINTABLE_EXTENSIONS:
        return f"""✅ 檔案已準備好，請使用 printer-mcp 的 print_file 工具列印：

📄 檔案：{actual_path.name}
📂 絕對路徑：{actual_str}

下一步：呼叫 print_file(file_path="{actual_str}")"""

    if ext in OFFICE_EXTENSIONS:
        # Office 文件轉 PDF
        try:
            tmp_dir = Path("/tmp/ctos/print")
            tmp_dir.mkdir(parents=True, exist_ok=True)

            proc_convert = await _asyncio.create_subprocess_exec(
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", str(tmp_dir), str(actual_path),
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
            )
            _, stderr_convert = await proc_convert.communicate()

            if proc_convert.returncode != 0:
                error_msg = stderr_convert.decode().strip() if stderr_convert else "未知錯誤"
                return f"❌ 檔案轉換 PDF 失敗：{error_msg}"

            pdf_name = actual_path.stem + ".pdf"
            tmp_pdf = tmp_dir / pdf_name

            if not tmp_pdf.exists():
                return "❌ 檔案轉換 PDF 後找不到輸出檔案"

            pdf_str = str(tmp_pdf)
            return f"""✅ Office 文件已轉換為 PDF，請使用 printer-mcp 的 print_file 工具列印：

📄 原始檔案：{actual_path.name}
📄 轉換後 PDF：{pdf_name}
📂 絕對路徑：{pdf_str}

下一步：呼叫 print_file(file_path="{pdf_str}")"""

        except FileNotFoundError:
            return "❌ 找不到 libreoffice 指令，無法轉換 Office 文件。"
        except Exception as e:
            return f"❌ 轉換 PDF 時發生錯誤：{str(e)}"

    supported = ", ".join(sorted(PRINTABLE_EXTENSIONS | OFFICE_EXTENSIONS))
    return f"❌ 不支援的檔案格式：{ext}\n支援的格式：{supported}"


# ============================================================
# 工具存取介面（供 Line Bot 和其他服務使用）
# ============================================================


async def get_mcp_tools() -> list[dict]:
    """
    取得 MCP 工具定義列表，格式符合 Claude API

    Returns:
        工具定義列表，可直接用於 Claude API 的 tools 參數
    """
    tools = await mcp.list_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        }
        for tool in tools
    ]


async def get_mcp_tool_names(exclude_group_only: bool = False) -> list[str]:
    """
    取得 MCP 工具名稱列表，格式為 mcp__ching-tech-os__{tool_name}

    Args:
        exclude_group_only: 是否排除群組專用工具（如 summarize_chat）

    Returns:
        工具名稱列表，可用於 Claude API 的 tools 參數
    """
    # 群組專用工具
    group_only_tools = {"summarize_chat"}

    tools = await mcp.list_tools()
    tool_names = []

    for tool in tools:
        if exclude_group_only and tool.name in group_only_tools:
            continue
        tool_names.append(f"mcp__ching-tech-os__{tool.name}")

    return tool_names


async def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    執行 MCP 工具

    Args:
        tool_name: 工具名稱
        arguments: 工具參數

    Returns:
        工具執行結果（文字）
    """
    try:
        result = await mcp.call_tool(tool_name, arguments)
        # result 是 (list[TextContent], dict) 的元組
        contents, _ = result
        if contents:
            return contents[0].text
        return "執行完成（無輸出）"
    except Exception as e:
        logger.error(f"執行工具 {tool_name} 失敗: {e}")
        return f"執行失敗：{str(e)}"


# ============================================================
# CLI 入口點（供 Claude Code 使用）
# ============================================================


def run_cli():
    """以 stdio 模式執行 MCP Server"""
    mcp.run()


if __name__ == "__main__":
    run_cli()
