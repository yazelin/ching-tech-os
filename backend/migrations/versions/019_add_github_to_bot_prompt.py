"""更新 Bot Agent Prompt — 加入 GitHub 工具指引

讓 Line Bot / Telegram Bot 的 AI Agent 能操作 GitHub Issues。

Revision ID: 019
"""

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None

# 要插入的 GitHub 工具說明段落
GITHUB_SECTION = """
【GitHub Issues 管理】
程式碼相關的 bug 回報、功能需求、開發追蹤，使用 GitHub 工具：

- mcp__plugin_github_github__list_issues: 列出 Issues
  · owner: "yazelin", repo: "ching-tech-os"
  · state: "OPEN"（預設）或 "CLOSED"
  · labels: 依模組過濾，如 ["his"]、["law"]、["core"]
- mcp__plugin_github_github__issue_write: 建立或更新 Issue
  · method: "create"（新建）或 "update"（更新）
  · owner: "yazelin", repo: "ching-tech-os"
  · title: Issue 標題（建議格式：feat/fix/docs(模組): 說明）
  · labels: ["enhancement"] 或 ["bug"]，加上模組標籤如 ["his"]、["law"]
  · body: Issue 內容（純文字）
- mcp__plugin_github_github__issue_read: 讀取 Issue 詳情
  · owner: "yazelin", repo: "ching-tech-os"
  · issue_number: Issue 編號

【工具選擇指引】
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
・「這個功能怎麼用」「架構是什麼」→ 知識庫
"""

# 要插入的位置標記（插在「使用工具的流程」之前）
INSERT_BEFORE = "使用工具的流程："


def upgrade() -> None:
    # 更新 linebot-personal prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = replace(
            content,
            '{INSERT_BEFORE}',
            $github${GITHUB_SECTION}$github$
            || '{INSERT_BEFORE}'
        ),
        updated_at = NOW()
        WHERE name = 'linebot-personal'
        AND content NOT LIKE '%GitHub Issues 管理%'
    """)

    # 更新 linebot-group prompt（簡化版）
    group_github = """
【GitHub Issues】
程式碼 bug/feature 回報使用 GitHub：
- mcp__plugin_github_github__list_issues: 列出 Issues（owner: "yazelin", repo: "ching-tech-os"）
- mcp__plugin_github_github__issue_write: 建立 Issue（method: "create"）
"""
    op.execute(f"""
        UPDATE ai_prompts
        SET content = content || $github${group_github}$github$,
        updated_at = NOW()
        WHERE name = 'linebot-group'
        AND content NOT LIKE '%GitHub Issues%'
    """)


def downgrade() -> None:
    # 移除 GitHub 段落（回滾用）
    op.execute(f"""
        UPDATE ai_prompts
        SET content = replace(content, $github${GITHUB_SECTION}$github$, ''),
        updated_at = NOW()
        WHERE name = 'linebot-personal'
    """)
