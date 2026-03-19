"""更新 Bot Agent Prompt — 加入 Asana 工具指引

讓 Line Bot / Telegram Bot 的 AI Agent 能操作 Asana 看板。

Revision ID: 020
"""

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

# 要插入的 Asana 工具說明段落
ASANA_SECTION = """
【Asana 看板管理】
跨模組進度追蹤、知識索引、協作任務，使用 Asana 工具：

- asana_list_workspaces: 列出工作區
- asana_get_projects_for_workspace: 列出專案
- asana_get_project_sections: 取得專案的 Section（看板欄位）
- asana_get_tasks: 取得 Section 或專案中的任務
  · project: 專案 GID
  · section: Section GID（可選）
  · opt_fields: "name,completed,assignee.name,due_on,notes"
- asana_create_task: 建立任務
  · name: 任務名稱
  · project_id: 專案 GID
  · section_id: Section GID（可選）
  · notes: 說明
- asana_update_task: 更新任務
  · task_id: 任務 GID
  · completed: true/false
- asana_typeahead_search: 快速搜尋（任務、專案等）
  · resource_type: "task" 或 "project"
  · query: 搜尋關鍵字

CTOS Asana 看板資訊：
・工作區：ching-tech.com
・CTOS 專案 GID：1213730634997133
・Section：核心、HIS、LAW、Done

【工具選擇指引（更新）】
根據用戶意圖選擇正確的工具：
・知識/文件/經驗/架構相關 → 搜尋知識庫（search_knowledge）
・程式碼 bug/feature/開發任務 → GitHub Issues
・專案任務/採購/庫存/廠商客戶 → ERPNext
・看板進度/協作追蹤/知識索引 → Asana
・圖片生成 → Nanobanana
・列印 → Printer
・找檔案 → NAS 搜尋

ERPNext vs Asana 區分：
・「專案進度」「部署任務」「庫存」「廠商」→ ERPNext
・「看板」「CTOS 進度」「模組概覽」→ Asana
"""

# 替換舊的工具選擇指引
OLD_GUIDE = """【工具選擇指引】
根據用戶意圖選擇正確的工具：
・知識/文件/經驗/架構相關 → 搜尋知識庫（search_knowledge）
・程式碼 bug/feature/開發任務 → GitHub Issues
・專案任務/採購/庫存/廠商客戶 → ERPNext
・圖片生成 → Nanobanana
・列印 → Printer
・找檔案 → NAS 搜尋

常見判斷：
・「建一個 issue」「回報 bug」「新功能需求」→ GitHub
・「專案進度」「庫存」「廠商電話」→ ERPNext
・「這個功能怎麼用」「架構是什麼」→ 知識庫"""

INSERT_BEFORE = "使用工具的流程："


def upgrade() -> None:
    # 先移除舊的工具選擇指引（由 019 migration 加入）
    op.execute(f"""
        UPDATE ai_prompts
        SET content = replace(content, $old${OLD_GUIDE}$old$, ''),
        updated_at = NOW()
        WHERE name = 'linebot-personal'
        AND content LIKE '%工具選擇指引%'
    """)

    # 插入 Asana + 更新版工具選擇指引
    op.execute(f"""
        UPDATE ai_prompts
        SET content = replace(
            content,
            '{INSERT_BEFORE}',
            $asana${ASANA_SECTION}$asana$
            || '{INSERT_BEFORE}'
        ),
        updated_at = NOW()
        WHERE name = 'linebot-personal'
        AND content NOT LIKE '%Asana 看板管理%'
    """)

    # 更新 linebot-group prompt
    group_asana = """
【Asana 看板】
看板進度追蹤使用 Asana：
- asana_get_tasks: 查看任務（CTOS 專案 GID: 1213730634997133）
- asana_create_task: 建立任務
- asana_typeahead_search: 搜尋任務
"""
    op.execute(f"""
        UPDATE ai_prompts
        SET content = content || $asana${group_asana}$asana$,
        updated_at = NOW()
        WHERE name = 'linebot-group'
        AND content NOT LIKE '%Asana 看板%'
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE ai_prompts
        SET content = replace(content, $asana${ASANA_SECTION}$asana$, ''),
        updated_at = NOW()
        WHERE name = 'linebot-personal'
    """)
