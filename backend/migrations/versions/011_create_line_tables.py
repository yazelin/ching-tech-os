"""create Line Bot tables

Revision ID: 011
Revises: 010
Create Date: 2025-12-23

Line Bot 整合 - 群組、用戶、訊息、檔案
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Line 群組表
    op.execute("""
        CREATE TABLE IF NOT EXISTS line_groups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            line_group_id VARCHAR(64) UNIQUE NOT NULL,
            name VARCHAR(256),
            picture_url TEXT,
            member_count INTEGER DEFAULT 0,
            project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
            is_active BOOLEAN DEFAULT true,
            joined_at TIMESTAMPTZ DEFAULT NOW(),
            left_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_groups_line_group_id ON line_groups(line_group_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_groups_project_id ON line_groups(project_id)")
    op.execute("COMMENT ON TABLE line_groups IS 'Line 群組資訊'")
    op.execute("COMMENT ON COLUMN line_groups.line_group_id IS 'Line 群組 ID'")
    op.execute("COMMENT ON COLUMN line_groups.project_id IS '綁定的專案 ID'")

    # Line 用戶表
    op.execute("""
        CREATE TABLE IF NOT EXISTS line_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            line_user_id VARCHAR(64) UNIQUE NOT NULL,
            display_name VARCHAR(256),
            picture_url TEXT,
            status_message TEXT,
            language VARCHAR(16),
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            is_friend BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_users_line_user_id ON line_users(line_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_users_user_id ON line_users(user_id)")
    op.execute("COMMENT ON TABLE line_users IS 'Line 用戶資訊'")
    op.execute("COMMENT ON COLUMN line_users.line_user_id IS 'Line 用戶 ID'")
    op.execute("COMMENT ON COLUMN line_users.user_id IS '對應的系統用戶 ID'")

    # Line 訊息表（儲存所有訊息：群組+個人）
    op.execute("""
        CREATE TABLE IF NOT EXISTS line_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            message_id VARCHAR(64) UNIQUE NOT NULL,
            line_user_id UUID NOT NULL REFERENCES line_users(id) ON DELETE CASCADE,
            line_group_id UUID REFERENCES line_groups(id) ON DELETE CASCADE,
            message_type VARCHAR(32) NOT NULL,
            content TEXT,
            file_id UUID,
            reply_token VARCHAR(64),
            is_from_bot BOOLEAN DEFAULT false,
            ai_processed BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_messages_line_user_id ON line_messages(line_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_messages_line_group_id ON line_messages(line_group_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_messages_created_at ON line_messages(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_messages_message_type ON line_messages(message_type)")
    op.execute("COMMENT ON TABLE line_messages IS 'Line 訊息記錄（群組+個人）'")
    op.execute("COMMENT ON COLUMN line_messages.line_group_id IS '群組 ID（NULL 表示個人對話）'")
    op.execute("COMMENT ON COLUMN line_messages.message_type IS '訊息類型：text, image, video, audio, file, location, sticker'")
    op.execute("COMMENT ON COLUMN line_messages.ai_processed IS '是否已經過 AI 處理'")

    # Line 檔案表（圖片/檔案記錄）
    op.execute("""
        CREATE TABLE IF NOT EXISTS line_files (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            message_id UUID NOT NULL REFERENCES line_messages(id) ON DELETE CASCADE,
            file_type VARCHAR(32) NOT NULL,
            file_name VARCHAR(512),
            file_size INTEGER,
            mime_type VARCHAR(128),
            nas_path TEXT,
            thumbnail_path TEXT,
            duration INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_files_message_id ON line_files(message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_files_file_type ON line_files(file_type)")
    op.execute("COMMENT ON TABLE line_files IS 'Line 檔案記錄'")
    op.execute("COMMENT ON COLUMN line_files.file_type IS '檔案類型：image, video, audio, file'")
    op.execute("COMMENT ON COLUMN line_files.nas_path IS 'NAS 儲存路徑'")
    op.execute("COMMENT ON COLUMN line_files.duration IS '音訊/影片長度（毫秒）'")

    # 更新 line_messages 的 file_id 外鍵（在 line_files 建立後）
    op.execute("""
        ALTER TABLE line_messages
        ADD CONSTRAINT fk_line_messages_file_id
        FOREIGN KEY (file_id) REFERENCES line_files(id) ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE line_messages DROP CONSTRAINT IF EXISTS fk_line_messages_file_id")
    op.execute("DROP TABLE IF EXISTS line_files CASCADE")
    op.execute("DROP TABLE IF EXISTS line_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS line_users CASCADE")
    op.execute("DROP TABLE IF EXISTS line_groups CASCADE")
