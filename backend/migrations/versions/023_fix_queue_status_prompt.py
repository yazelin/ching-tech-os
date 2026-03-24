"""修正看診進度查詢 prompt

- skill 名稱 his-integration → clinic-info
- 加強「幾號」語意引導（看診號碼，非日期）

Revision ID: 023
"""

from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 取得 jfmskin-full 的 prompt 內容，替換錯誤的 skill 名稱
    conn.execute(
        sa.text("""
            UPDATE ai_prompts
            SET content = REPLACE(
                content,
                'run_skill_script(skill="his-integration", script="queue_status")',
                'run_skill_script(skill="clinic-info", script="queue_status")'
            ),
            updated_at = now()
            WHERE id = (
                SELECT system_prompt_id FROM ai_agents WHERE name = 'jfmskin-full'
            )
            AND content LIKE '%his-integration%queue_status%'
        """)
    )

    # 也修 jfmskin-edu 如果有的話
    conn.execute(
        sa.text("""
            UPDATE ai_prompts
            SET content = REPLACE(
                content,
                'run_skill_script(skill="his-integration", script="queue_status")',
                'run_skill_script(skill="clinic-info", script="queue_status")'
            ),
            updated_at = now()
            WHERE id = (
                SELECT system_prompt_id FROM ai_agents WHERE name = 'jfmskin-edu'
            )
            AND content LIKE '%his-integration%queue_status%'
        """)
    )


def downgrade() -> None:
    pass
