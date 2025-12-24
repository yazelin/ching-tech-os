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
    instructions="擎添科技 OS 的 AI 工具，可查詢專案、會議、成員等資訊。",
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
) -> str:
    """
    更新知識庫文件

    Args:
        kb_id: 知識 ID（如 kb-001）
        title: 新標題（不填則不更新）
        content: 新內容（不填則不更新）
        category: 新分類（不填則不更新）
        topics: 新標籤列表（不填則不更新）
    """
    from ..models.knowledge import KnowledgeUpdate, KnowledgeTags
    from . import knowledge as kb_service

    try:
        # 建立更新資料
        update_data = KnowledgeUpdate(
            title=title,
            content=content,
            category=category,
            tags=KnowledgeTags(topics=topics) if topics else None,
        )

        item = kb_service.update_knowledge(kb_id, update_data)

        return f"✅ 已更新 [{item.id}] {item.title}"

    except Exception as e:
        logger.error(f"更新知識失敗: {e}")
        return f"更新失敗：{str(e)}"


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

        # 建立知識
        data = KnowledgeCreate(
            title=title,
            content=content,
            type="note",
            category=category,
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
