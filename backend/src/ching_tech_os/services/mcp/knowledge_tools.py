"""知識庫相關 MCP 工具

包含：search_knowledge, get_knowledge_item, update_knowledge_item,
add_attachments_to_knowledge, delete_knowledge_item, get_knowledge_attachments,
update_knowledge_attachment, read_knowledge_attachment, add_note, add_note_with_attachments
"""

from .server import (
    mcp,
    logger,
    ensure_db_connection,
    check_mcp_tool_permission,
    _LIST_ALL_KNOWLEDGE_QUERIES,
)
from ...database import get_connection


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

    from .. import knowledge as kb_service

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

    # 未綁定用戶（ctos_user_id 為 None）僅能搜尋公開知識
    public_only = ctos_user_id is None

    try:
        result = kb_service.search_knowledge(
            query=search_query,
            project=project,
            category=category,
            current_username=current_username,
            public_only=public_only,
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

    from .. import knowledge as kb_service
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

    from ...models.knowledge import KnowledgeUpdate, KnowledgeTags
    from .. import knowledge as kb_service

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

    from .. import knowledge as kb_service

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

    from .. import knowledge as kb_service

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

    from .. import knowledge as kb_service
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

    from .. import knowledge as kb_service
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

    from .. import knowledge as kb_service
    from ..path_manager import path_manager
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

    from ...models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from .. import knowledge as kb_service

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

    from ...models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from .. import knowledge as kb_service

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
