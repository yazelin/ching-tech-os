"""Line Bot MCP Server

使用 FastMCP 定義工具，支援：
- Claude Code CLI（stdio 模式）
- Line Bot AI（直接呼叫）
- 其他 MCP 客戶端

工具只定義一次，Schema 自動從 type hints 和 docstring 生成。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from ..database import get_connection, init_db_pool

logger = logging.getLogger("mcp_server")

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
# MCP 工具定義
# ============================================================


@mcp.tool()
async def query_project(project_id: str | None = None, keyword: str | None = None) -> str:
    """
    查詢專案資訊

    Args:
        project_id: 專案 UUID，查詢特定專案
        keyword: 搜尋關鍵字，搜尋專案名稱和描述
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        if project_id:
            # 查詢特定專案
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1",
                UUID(project_id),
            )
            if not row:
                return f"找不到專案 ID: {project_id}"

            # 取得里程碑統計
            milestone_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress
                FROM project_milestones
                WHERE project_id = $1
                """,
                UUID(project_id),
            )

            # 取得成員數
            member_count = await conn.fetchval(
                "SELECT COUNT(*) FROM project_members WHERE project_id = $1",
                UUID(project_id),
            )

            return f"""專案：{row['name']}
狀態：{row['status']}
描述：{row['description'] or '無描述'}
成員數：{member_count}
里程碑：共 {milestone_stats['total']} 個，完成 {milestone_stats['completed']}，進行中 {milestone_stats['in_progress']}
建立時間：{row['created_at'].strftime('%Y-%m-%d')}"""

        elif keyword:
            # 搜尋專案
            rows = await conn.fetch(
                """
                SELECT id, name, status, description
                FROM projects
                WHERE name ILIKE $1 OR description ILIKE $1
                ORDER BY updated_at DESC
                LIMIT 5
                """,
                f"%{keyword}%",
            )
            if not rows:
                return f"找不到包含「{keyword}」的專案"

            results = ["搜尋結果："]
            for row in rows:
                results.append(f"- {row['name']} ({row['status']}) [ID: {row['id']}]")
            return "\n".join(results)

        else:
            # 列出最近專案
            rows = await conn.fetch(
                """
                SELECT id, name, status
                FROM projects
                ORDER BY updated_at DESC
                LIMIT 5
                """
            )
            if not rows:
                return "目前沒有任何專案"

            results = ["最近的專案："]
            for row in rows:
                results.append(f"- {row['name']} ({row['status']}) [ID: {row['id']}]")
            return "\n".join(results)


@mcp.tool()
async def create_project(
    name: str,
    description: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """
    建立新專案

    Args:
        name: 專案名稱（必填）
        description: 專案描述
        start_date: 開始日期（格式：YYYY-MM-DD）
        end_date: 結束日期（格式：YYYY-MM-DD）
    """
    from datetime import date as date_type
    from ..models.project import ProjectCreate
    from .project import create_project as svc_create_project

    await ensure_db_connection()

    try:
        # 解析日期
        parsed_start = None
        parsed_end = None
        if start_date:
            parsed_start = date_type.fromisoformat(start_date)
        if end_date:
            parsed_end = date_type.fromisoformat(end_date)

        # 建立專案
        data = ProjectCreate(
            name=name,
            description=description,
            start_date=parsed_start,
            end_date=parsed_end,
        )
        result = await svc_create_project(data, created_by="linebot")

        return f"✅ 已建立專案「{result.name}」\n專案 ID：{result.id}"

    except Exception as e:
        logger.error(f"建立專案失敗: {e}")
        return f"建立專案失敗：{str(e)}"


@mcp.tool()
async def get_project_milestones(
    project_id: str,
    status: str | None = None,
    limit: int = 10,
) -> str:
    """
    取得專案里程碑列表

    Args:
        project_id: 專案 UUID
        status: 狀態過濾，可選值：pending, in_progress, completed, delayed
        limit: 最大數量，預設 10
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        query = """
            SELECT name, milestone_type, planned_date, actual_date, status, notes
            FROM project_milestones
            WHERE project_id = $1
        """
        params: list = [UUID(project_id)]

        if status:
            query += " AND status = $2"
            params.append(status)

        query += " ORDER BY sort_order, planned_date LIMIT $" + str(len(params) + 1)
        params.append(limit)

        rows = await conn.fetch(query, *params)

        if not rows:
            return "此專案目前沒有里程碑"

        # 取得專案名稱
        project = await conn.fetchrow(
            "SELECT name FROM projects WHERE id = $1",
            UUID(project_id),
        )
        project_name = project["name"] if project else "未知專案"

        # 格式化里程碑
        milestones = [f"【{project_name}】里程碑：\n"]
        for row in rows:
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "delayed": "⚠️",
            }.get(row["status"], "❓")
            planned = row["planned_date"].strftime("%m/%d") if row["planned_date"] else "未排程"
            milestones.append(f"{status_emoji} {row['name']} | 預計 {planned}")

        return "\n".join(milestones)


@mcp.tool()
async def get_project_meetings(
    project_id: str,
    limit: int = 5,
) -> str:
    """
    取得專案會議記錄

    Args:
        project_id: 專案 UUID
        limit: 最大數量，預設 5
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT title, meeting_date, location, attendees, content
            FROM project_meetings
            WHERE project_id = $1
            ORDER BY meeting_date DESC
            LIMIT $2
            """,
            UUID(project_id),
            limit,
        )

        if not rows:
            return "此專案目前沒有會議記錄"

        # 取得專案名稱
        project = await conn.fetchrow(
            "SELECT name FROM projects WHERE id = $1",
            UUID(project_id),
        )
        project_name = project["name"] if project else "未知專案"

        # 格式化會議記錄
        meetings = [f"【{project_name}】最近會議：\n"]
        for row in rows:
            date_str = row["meeting_date"].strftime("%Y-%m-%d %H:%M")
            attendees = ", ".join(row["attendees"]) if row["attendees"] else "無記錄"
            content_snippet = (row["content"] or "")[:100]
            if len(row["content"] or "") > 100:
                content_snippet += "..."

            meetings.append(f"📅 {date_str} - {row['title']}")
            meetings.append(f"   地點：{row['location'] or '未指定'}")
            meetings.append(f"   參與者：{attendees}")
            if content_snippet:
                meetings.append(f"   內容：{content_snippet}")
            meetings.append("")

        return "\n".join(meetings)


@mcp.tool()
async def get_project_members(
    project_id: str,
    is_internal: bool | None = None,
) -> str:
    """
    取得專案成員與聯絡人

    Args:
        project_id: 專案 UUID
        is_internal: 篩選內部或外部人員，不指定則顯示全部
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        query = """
            SELECT name, role, company, email, phone, is_internal
            FROM project_members
            WHERE project_id = $1
        """
        params: list = [UUID(project_id)]

        if is_internal is not None:
            query += " AND is_internal = $2"
            params.append(is_internal)

        query += " ORDER BY is_internal DESC, name"

        rows = await conn.fetch(query, *params)

        if not rows:
            return "此專案目前沒有成員"

        # 取得專案名稱
        project = await conn.fetchrow(
            "SELECT name FROM projects WHERE id = $1",
            UUID(project_id),
        )
        project_name = project["name"] if project else "未知專案"

        # 格式化成員
        members = [f"【{project_name}】成員/聯絡人：\n"]

        internal = [r for r in rows if r["is_internal"]]
        external = [r for r in rows if not r["is_internal"]]

        if internal:
            members.append("內部人員：")
            for row in internal:
                members.append(f"  👤 {row['name']} - {row['role'] or '未指定角色'}")

        if external:
            members.append("\n外部聯絡人：")
            for row in external:
                info = f"  👤 {row['name']}"
                if row["company"]:
                    info += f" ({row['company']})"
                if row["role"]:
                    info += f" - {row['role']}"
                members.append(info)

        return "\n".join(members)


@mcp.tool()
async def search_knowledge(
    query: str,
    project: str | None = None,
    category: str | None = None,
    limit: int = 5,
) -> str:
    """
    搜尋知識庫

    Args:
        query: 搜尋關鍵字
        project: 專案過濾（如：專案 ID 或名稱）
        category: 分類過濾（如：technical, process, tool）
        limit: 最大結果數量，預設 5
    """
    from . import knowledge as kb_service

    try:
        result = kb_service.search_knowledge(
            query=query,
            project=project,
            category=category,
        )

        if not result.items:
            return f"找不到包含「{query}」的知識"

        # 格式化結果
        items = result.items[:limit]
        output = [f"搜尋「{query}」找到 {len(result.items)} 筆結果：\n"]

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
async def get_knowledge_item(kb_id: str) -> str:
    """
    取得知識庫文件的完整內容

    Args:
        kb_id: 知識 ID（如 kb-001、kb-002）
    """
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
    topics: list[str] | None = None,
    projects: list[str] | None = None,
    roles: list[str] | None = None,
    level: str | None = None,
    type: str | None = None,
) -> str:
    """
    更新知識庫文件

    Args:
        kb_id: 知識 ID（如 kb-001）
        title: 新標題（不填則不更新）
        content: 新內容（不填則不更新）
        category: 新分類（不填則不更新）
        topics: 主題標籤列表（不填則不更新）
        projects: 關聯專案列表（不填則不更新）
        roles: 適用角色列表（不填則不更新）
        level: 難度層級，如 beginner、intermediate、advanced（不填則不更新）
        type: 知識類型，如 note、spec、guide（不填則不更新）
    """
    from ..models.knowledge import KnowledgeUpdate, KnowledgeTags
    from . import knowledge as kb_service

    try:
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
            type=type,
            tags=tags,
        )

        item = kb_service.update_knowledge(kb_id, update_data)

        return f"✅ 已更新 [{item.id}] {item.title}"

    except Exception as e:
        logger.error(f"更新知識失敗: {e}")
        return f"更新失敗：{str(e)}"


@mcp.tool()
async def add_attachments_to_knowledge(
    kb_id: str,
    attachments: list[str],
    descriptions: list[str] | None = None,
) -> str:
    """
    為現有知識庫新增附件

    Args:
        kb_id: 知識 ID（如 kb-001）
        attachments: 附件的 NAS 路徑列表（從 get_message_attachments 取得）
        descriptions: 附件描述列表（與 attachments 一一對應，如「圖1 水切爐」）
    """
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
async def delete_knowledge_item(kb_id: str) -> str:
    """
    刪除知識庫文件

    Args:
        kb_id: 知識 ID（如 kb-001）
    """
    from . import knowledge as kb_service

    try:
        kb_service.delete_knowledge(kb_id)
        return f"✅ 已刪除知識 {kb_id}"

    except Exception as e:
        logger.error(f"刪除知識失敗: {e}")
        return f"刪除失敗：{str(e)}"


@mcp.tool()
async def get_knowledge_attachments(kb_id: str) -> str:
    """
    取得知識庫的附件列表

    Args:
        kb_id: 知識 ID（如 kb-001、kb-002）
    """
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
            if att.size:
                output.append(f"    大小：{att.size}")
            if att.description:
                output.append(f"    說明：{att.description}")
            else:
                output.append("    說明：（無）")
            output.append("")

        output.append("提示：使用 update_knowledge_attachment 更新附件說明")
        return "\n".join(output)

    except Exception as e:
        logger.error(f"取得附件列表失敗: {e}")
        return f"找不到知識 {kb_id}：{str(e)}"


@mcp.tool()
async def update_knowledge_attachment(
    kb_id: str,
    attachment_index: int,
    description: str | None = None,
) -> str:
    """
    更新知識庫附件的說明

    Args:
        kb_id: 知識 ID（如 kb-001）
        attachment_index: 附件索引（從 0 開始，可用 get_knowledge_attachments 查詢）
        description: 附件說明（如「圖1 水切爐畫面」）
    """
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
async def add_note(
    title: str,
    content: str,
    category: str = "note",
    topics: list[str] | None = None,
    project: str | None = None,
) -> str:
    """
    新增筆記到知識庫

    Args:
        title: 筆記標題
        content: 筆記內容（Markdown 格式）
        category: 分類，預設 note（可選：technical, process, tool, note）
        topics: 主題標籤列表
        project: 關聯的專案名稱
    """
    from ..models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from . import knowledge as kb_service

    try:
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

        # 建立知識（Line Bot 建立的筆記為全域可見）
        data = KnowledgeCreate(
            title=title,
            content=content,
            type="note",
            category=category,
            scope="global",  # Line Bot 筆記設為全域可見
            tags=tags,
            source=source,
            related=[],
            author="linebot",
        )

        result = kb_service.create_knowledge(data)
        return f"✅ 筆記已新增！\nID：{result.id}\n標題：{result.title}"

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
    """
    from ..models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from . import knowledge as kb_service

    # 限制附件數量
    if len(attachments) > 10:
        return "附件數量不能超過 10 個"

    try:
        # 1. 建立知識庫筆記
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
            scope="global",
            tags=tags,
            source=source,
            related=[],
            author="linebot",
        )

        result = kb_service.create_knowledge(data)
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
        output = [f"✅ 筆記已新增！", f"ID：{kb_id}", f"標題：{title}"]

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
            FROM line_messages m
            LEFT JOIN line_users u ON m.line_user_id = u.id
            WHERE m.line_group_id = $1
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
            "SELECT name FROM line_groups WHERE id = $1",
            UUID(line_group_id),
        )
        group_name = group["name"] if group else "未知群組"

        # 格式化訊息
        messages = [f"【{group_name}】過去 {hours} 小時的聊天記錄（共 {len(rows)} 則）：\n"]
        for row in rows:
            time_str = row["created_at"].strftime("%H:%M")
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
            conditions.append(f"m.line_group_id = ${param_idx}")
            params.append(UUID(line_group_id))
            param_idx += 1
        elif line_user_id:
            # 個人聊天：查詢該用戶的訊息且不在群組中
            conditions.append(f"u.line_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1
            conditions.append("m.line_group_id IS NULL")

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
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            LEFT JOIN line_users u ON m.line_user_id = u.id
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
            time_str = row["created_at"].strftime("%Y-%m-%d %H:%M")
            user = row["user_name"] or "未知用戶"

            output.append(f"{i}. [{type_name}] {time_str} - {user}")
            output.append(f"   NAS 路徑：{row['nas_path']}")

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
async def create_share_link(
    resource_type: str,
    resource_id: str,
    expires_in: str | None = "24h",
) -> str:
    """
    建立公開分享連結，讓沒有帳號的人也能查看知識庫或專案

    Args:
        resource_type: 資源類型，knowledge（知識庫）或 project（專案）
        resource_id: 資源 ID（如 kb-001 或專案 UUID）
        expires_in: 有效期限，可選 1h、24h、7d、null（永久），預設 24h
    """
    await ensure_db_connection()

    from .share import (
        create_share_link as _create_share_link,
        ShareError,
        ResourceNotFoundError,
    )
    from ..models.share import ShareLinkCreate

    # 驗證資源類型
    if resource_type not in ("knowledge", "project"):
        return f"錯誤：資源類型必須是 knowledge 或 project，收到：{resource_type}"

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
            from datetime import timezone, timedelta
            taipei_tz = timezone(timedelta(hours=8))
            expires_taipei = result.expires_at.astimezone(taipei_tz)
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
