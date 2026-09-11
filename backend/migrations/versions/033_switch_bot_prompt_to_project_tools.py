"""bot prompt 切換到專案模組 MCP 工具（PR 7b）

`ai_prompts` 的 `linebot-group`、`linebot-personal` 內容存在資料庫，程式碼裡的
`services/linebot_agents.py` 只是新環境的種子，改了程式碼不會動到既有的那兩筆。
這支 migration 把「專案沒有 MCP 工具，請到新前端」的段落換成
`services/mcp/project_tools.py` 的工具指引。

手法照 032：逐段 `str.replace()`，舊段落的原文就是 032 換上去的新段落；
某一段找不到就記 log 跳過，不讓整支 migration 失敗——prompt 是可以在後台再修的
資料，擋住後面的 schema migration 代價比較大。

downgrade 反向替換，把段落換回「請到新前端」版本。

Revision ID: 033
"""

import logging

from alembic import op
import sqlalchemy as sa

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.migration.033")

# 受影響的 prompt
PERSONAL = "linebot-personal"
GROUP = "linebot-group"

# 段落名稱 → (032 換上去的版本, 專案工具版本)
SECTIONS: dict[str, tuple[str, str]] = {
    "personal_project": (
        """【專案管理】
專案資料在 CTOS 自己的系統。目前還沒有專案的 MCP 工具，要查專案、任務、成員，
請到新前端 os.ching-tech.com/projects""",
        """【專案管理】
專案、里程碑與任務都在 CTOS 自己的資料庫：

- find_project: 模糊搜尋專案（名稱或客戶）
  · query: 搜尋字串
  · status: planning／active／on_hold／completed／cancelled（可省略）
- get_project: 專案明細（成員、里程碑含逾期、任務、綁定群組、進度）
  · project_id: 專案 UUID；或 name: 專案名稱／客戶（會做模糊解析）
- list_overdue_milestones: 逾期里程碑清單（依到期日升冪）＋進行中專案數
- list_tasks: 任務清單
  · project: 專案名稱或 UUID；status: todo／doing／done；assignee: 負責人
- create_task: 建立任務
  · project、title 必填
  · assignee 吃 username 或顯示名稱、milestone 吃里程碑名稱、due_date 用 YYYY-MM-DD
- update_task: 更新任務
  · project、task（標題或 UUID）、fields
  · fields 例：{"status": "done"}、{"assignee": "亞澤"}、{"due_date": "2026-10-01"}
- create_milestone: 建立里程碑（project、name、due_date）
- complete_milestone: 里程碑標記完成（project、milestone，完成日填今天）
- add_project_member: 加入專案成員（project、user 吃 username 或顯示名稱）

寫入類（建任務、改任務、里程碑、加成員）只有專案成員或管理員能做，
被擋下來時直接告訴用戶「只有專案成員能編輯」，不要重試。
建立專案不開放給 bot，請用戶到 os.ching-tech.com/projects 開。""",
    ),
    "personal_flow_project": (
        """1. 查詢專案時，請到新前端 os.ching-tech.com/projects（目前沒有專案的 MCP 工具）""",
        """1. 查詢專案時，先用 find_project 找到專案，再用 get_project 看明細
   （進度、里程碑逾期、任務、成員都在裡面）；問「有什麼逾期」用 list_overdue_milestones""",
    ),
    "personal_flow_project_ops": (
        """11. 用戶需要操作專案時：
    - 請到新前端 os.ching-tech.com/projects""",
        """11. 用戶需要操作專案時：
    - 建任務用 create_task、改狀態或負責人用 update_task、查任務用 list_tasks
    - 里程碑用 create_milestone、complete_milestone，加人用 add_project_member
    - 專案、任務、里程碑、人都可以直接講名字，回多個候選時唸出來讓用戶挑
    - 只有專案成員或管理員能寫；要開新專案請用戶到 os.ching-tech.com/projects""",
    ),
    "group_project": (
        """【專案管理】
專案目前沒有 MCP 工具，請到新前端 os.ching-tech.com/projects""",
        """【專案管理】
- find_project: 搜尋專案（名稱或客戶，status 可省略）
- get_project: 專案明細（成員、里程碑含逾期、任務、進度）
- list_overdue_milestones: 逾期里程碑清單＋進行中專案數
- list_tasks: 任務清單（status、assignee 可過濾）
- create_task / update_task: 建任務、改狀態或負責人（fields 例 {"status": "done"}）
- create_milestone / complete_milestone: 里程碑建立與標記完成
- add_project_member: 加入專案成員
- 寫入只有專案成員或管理員能做；要開新專案請到 os.ching-tech.com/projects""",
    ),
}

# 每個 prompt 要套哪些段落
PROMPT_SECTIONS: dict[str, list[str]] = {
    PERSONAL: [
        "personal_project",
        "personal_flow_project",
        "personal_flow_project_ops",
    ],
    GROUP: ["group_project"],
}


def rewrite(
    content: str, names: list[str], reverse: bool = False
) -> tuple[str, list[str], list[str]]:
    """逐段替換，回傳（改寫後內容, 找不到的段落, 已經是目標版本的段落）

    `reverse=True` 是 downgrade 方向（工具指引換回「請到新前端」）。

    「找不到」與「已切換」要分開：前者代表段落被人改過、需要人工補，
    後者是重跑 migration 的正常情況，不該吵。
    """
    missing: list[str] = []
    already: list[str] = []
    for name in names:
        old, new = SECTIONS[name]
        if reverse:
            old, new = new, old
        if old not in content:
            if new in content:
                already.append(name)
            else:
                missing.append(name)
            continue
        content = content.replace(old, new)
    return content, missing, already


def _apply(reverse: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, name, content FROM ai_prompts WHERE name = ANY(:names)"),
        {"names": list(PROMPT_SECTIONS)},
    ).fetchall()
    found = {row.name for row in rows}
    for name in PROMPT_SECTIONS:
        if name not in found:
            logger.warning("ai_prompts 沒有 %s，略過", name)

    for row in rows:
        new_content, missing, already = rewrite(
            row.content, PROMPT_SECTIONS[row.name], reverse=reverse
        )
        if already:
            logger.info("%s 這些段落已切換，略過：%s", row.name, "、".join(already))
        if missing:
            logger.warning("%s 找不到這些段落，已略過：%s", row.name, "、".join(missing))
        if new_content == row.content:
            logger.info("%s 內容沒有變化，不更新", row.name)
            continue
        conn.execute(
            sa.text("UPDATE ai_prompts SET content = :content, updated_at = NOW() WHERE id = :id"),
            {"content": new_content, "id": row.id},
        )
        logger.info(
            "%s 已更新（%d 段）",
            row.name,
            len(PROMPT_SECTIONS[row.name]) - len(missing) - len(already),
        )


def upgrade() -> None:
    _apply(reverse=False)


def downgrade() -> None:
    _apply(reverse=True)
