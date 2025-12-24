"""create AI management tables

Revision ID: 007
Revises: 006
Create Date: 2025-12-22

AI 管理模組 - Prompts、Agents、Logs（分區表）
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # AI Prompts 表（取代檔案式管理）
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_prompts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(128) UNIQUE NOT NULL,
            display_name VARCHAR(256),
            category VARCHAR(64),
            content TEXT NOT NULL,
            description TEXT,
            variables JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_prompts_name ON ai_prompts(name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_prompts_category ON ai_prompts(category)")
    op.execute("COMMENT ON TABLE ai_prompts IS 'AI Prompt 管理表'")
    op.execute("COMMENT ON COLUMN ai_prompts.name IS '唯一識別名（如 web-chat-default）'")
    op.execute("COMMENT ON COLUMN ai_prompts.category IS '分類：system, task, template'")
    op.execute("COMMENT ON COLUMN ai_prompts.variables IS '可用變數說明 JSON'")

    # AI Agents 表
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_agents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(64) UNIQUE NOT NULL,
            display_name VARCHAR(128),
            description TEXT,
            model VARCHAR(32) NOT NULL,
            system_prompt_id UUID REFERENCES ai_prompts(id) ON DELETE SET NULL,
            is_active BOOLEAN DEFAULT true,
            settings JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_agents_name ON ai_agents(name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_agents_is_active ON ai_agents(is_active)")
    op.execute("COMMENT ON TABLE ai_agents IS 'AI Agent 設定表'")
    op.execute("COMMENT ON COLUMN ai_agents.name IS '唯一識別名（如 web-chat-default）'")
    op.execute("COMMENT ON COLUMN ai_agents.model IS 'AI 模型：claude-haiku, claude-sonnet 等'")
    op.execute("COMMENT ON COLUMN ai_agents.settings IS '額外設定 JSON（保留擴展）'")

    # AI Logs 分區主表
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_logs (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            agent_id UUID REFERENCES ai_agents(id) ON DELETE SET NULL,
            prompt_id UUID REFERENCES ai_prompts(id) ON DELETE SET NULL,
            context_type VARCHAR(32),
            context_id VARCHAR(64),
            input_prompt TEXT NOT NULL,
            raw_response TEXT,
            parsed_response JSONB,
            model VARCHAR(32),
            success BOOLEAN DEFAULT true,
            error_message TEXT,
            duration_ms INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_logs_agent_id ON ai_logs(agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_logs_context ON ai_logs(context_type, context_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_logs_created_at ON ai_logs(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_logs_success ON ai_logs(success)")
    op.execute("COMMENT ON TABLE ai_logs IS 'AI 調用日誌（按月分區）'")
    op.execute("COMMENT ON COLUMN ai_logs.context_type IS '調用情境：web-chat, linebot-group, system, test'")
    op.execute("COMMENT ON COLUMN ai_logs.context_id IS '情境 ID：chat_id, group_id, job_id'")
    op.execute("COMMENT ON COLUMN ai_logs.duration_ms IS 'AI 調用耗時（毫秒）'")

    # 建立初始分區（當月與下月）
    now = datetime.now()
    current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    month_after = (next_month + timedelta(days=32)).replace(day=1)

    # 當月分區
    partition_name = f"ai_logs_{current_month.strftime('%Y_%m')}"
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF ai_logs
        FOR VALUES FROM ('{current_month.strftime('%Y-%m-%d')}')
        TO ('{next_month.strftime('%Y-%m-%d')}')
    """)

    # 下月分區
    partition_name = f"ai_logs_{next_month.strftime('%Y_%m')}"
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF ai_logs
        FOR VALUES FROM ('{next_month.strftime('%Y-%m-%d')}')
        TO ('{month_after.strftime('%Y-%m-%d')}')
    """)

    # 分區管理函數：自動建立新分區
    op.execute("""
        CREATE OR REPLACE FUNCTION create_ai_logs_partition()
        RETURNS void AS $$
        DECLARE
            partition_date DATE;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            -- 建立未來兩個月的分區
            FOR i IN 0..1 LOOP
                partition_date := DATE_TRUNC('month', NOW() + (i || ' month')::INTERVAL);
                partition_name := 'ai_logs_' || TO_CHAR(partition_date, 'YYYY_MM');
                start_date := partition_date;
                end_date := partition_date + INTERVAL '1 month';

                -- 檢查分區是否存在
                IF NOT EXISTS (
                    SELECT 1 FROM pg_class
                    WHERE relname = partition_name
                    AND relkind = 'r'
                ) THEN
                    EXECUTE FORMAT(
                        'CREATE TABLE %I PARTITION OF ai_logs FOR VALUES FROM (%L) TO (%L)',
                        partition_name, start_date, end_date
                    );
                    RAISE NOTICE 'Created partition: %', partition_name;
                END IF;
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("COMMENT ON FUNCTION create_ai_logs_partition() IS '自動建立 ai_logs 分區（當月與下月）'")

    # 建立預設 Prompts
    op.execute("""
        INSERT INTO ai_prompts (name, display_name, category, content, description) VALUES
        ('web-chat-default', '預設對話助手', 'system',
         '你是一個友善的 AI 助手。請用繁體中文回答問題，回答要簡潔明瞭。',
         '前端對話預設使用的 system prompt'),
        ('web-chat-code', '程式碼助手', 'system',
         '你是一個專業的程式設計助手。請用繁體中文回答問題，提供清晰的程式碼範例和解釋。回答要精確且有條理。',
         '程式碼相關問題使用的 system prompt'),
        ('linebot-group', 'Line 群組助手', 'system',
         '你是群組中的 AI 助手。回答要簡短（不超過 200 字），使用繁體中文。只在被 @ 或直接詢問時回應。',
         'Line Bot 群組對話使用'),
        ('linebot-personal', 'Line 個人助理', 'system',
         '你是使用者的個人 AI 助理。可以幫助查詢資訊、管理筆記、回答問題。使用繁體中文，語氣親切專業。',
         'Line Bot 個人對話使用'),
        ('system-task', '系統任務', 'task',
         '你是系統內部任務處理程式。請根據指令執行任務，輸出結構化的結果。',
         '系統排程任務使用')
        ON CONFLICT (name) DO NOTHING
    """)

    # 建立預設 Agents
    op.execute("""
        INSERT INTO ai_agents (name, display_name, description, model, system_prompt_id, is_active)
        SELECT 'web-chat-default', '預設對話', '前端對話預設 Agent', 'claude-sonnet',
               (SELECT id FROM ai_prompts WHERE name = 'web-chat-default'), true
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE name = 'web-chat-default')
    """)
    op.execute("""
        INSERT INTO ai_agents (name, display_name, description, model, system_prompt_id, is_active)
        SELECT 'web-chat-code', '程式碼助手', '程式碼相關問題 Agent', 'claude-sonnet',
               (SELECT id FROM ai_prompts WHERE name = 'web-chat-code'), true
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE name = 'web-chat-code')
    """)
    op.execute("""
        INSERT INTO ai_agents (name, display_name, description, model, system_prompt_id, is_active)
        SELECT 'linebot-group', 'Line 群組', 'Line Bot 群組對話 Agent', 'claude-haiku',
               (SELECT id FROM ai_prompts WHERE name = 'linebot-group'), true
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE name = 'linebot-group')
    """)
    op.execute("""
        INSERT INTO ai_agents (name, display_name, description, model, system_prompt_id, is_active)
        SELECT 'linebot-personal', 'Line 個人助理', 'Line Bot 個人對話 Agent', 'claude-sonnet',
               (SELECT id FROM ai_prompts WHERE name = 'linebot-personal'), true
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE name = 'linebot-personal')
    """)
    op.execute("""
        INSERT INTO ai_agents (name, display_name, description, model, system_prompt_id, is_active)
        SELECT 'system-scheduler', '系統排程', '系統排程任務 Agent', 'claude-haiku',
               (SELECT id FROM ai_prompts WHERE name = 'system-task'), true
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE name = 'system-scheduler')
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS create_ai_logs_partition()")
    op.execute("DROP TABLE IF EXISTS ai_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_agents CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_prompts CASCADE")
