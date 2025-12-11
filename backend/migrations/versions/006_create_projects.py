"""create project management tables

Revision ID: 006
Revises: 005
Create Date: 2025-12-11

專案管理模組 - 專案、成員、會議記錄、附件、連結
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 專案主表
    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'active',
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            created_by VARCHAR(100)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC)")
    op.execute("COMMENT ON TABLE projects IS '專案主表'")
    op.execute("COMMENT ON COLUMN projects.status IS '專案狀態：active, completed, on_hold, cancelled'")

    # 專案成員/聯絡人
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            role VARCHAR(100),
            company VARCHAR(200),
            email VARCHAR(200),
            phone VARCHAR(50),
            notes TEXT,
            is_internal BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_members_project_id ON project_members(project_id)")
    op.execute("COMMENT ON TABLE project_members IS '專案成員/聯絡人'")
    op.execute("COMMENT ON COLUMN project_members.role IS '角色：PM, 工程師, 客戶等'")
    op.execute("COMMENT ON COLUMN project_members.is_internal IS '是否為內部人員'")

    # 會議記錄
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_meetings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            meeting_date TIMESTAMP NOT NULL,
            location VARCHAR(200),
            attendees TEXT[],
            content TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            created_by VARCHAR(100)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_meetings_project_id ON project_meetings(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_meetings_date ON project_meetings(meeting_date DESC)")
    op.execute("COMMENT ON TABLE project_meetings IS '專案會議記錄'")
    op.execute("COMMENT ON COLUMN project_meetings.attendees IS '參與人員名單'")
    op.execute("COMMENT ON COLUMN project_meetings.content IS 'Markdown 格式會議內容'")

    # 專案附件
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_attachments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            filename VARCHAR(500) NOT NULL,
            file_type VARCHAR(50),
            file_size BIGINT,
            storage_path VARCHAR(1000) NOT NULL,
            description TEXT,
            uploaded_at TIMESTAMP DEFAULT NOW(),
            uploaded_by VARCHAR(100)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_attachments_project_id ON project_attachments(project_id)")
    op.execute("COMMENT ON TABLE project_attachments IS '專案附件'")
    op.execute("COMMENT ON COLUMN project_attachments.file_type IS '檔案類型：image, pdf, cad, document, other'")
    op.execute("COMMENT ON COLUMN project_attachments.storage_path IS '儲存路徑：本機路徑或 nas://...'")

    # 專案連結
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            url VARCHAR(2000) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_links_project_id ON project_links(project_id)")
    op.execute("COMMENT ON TABLE project_links IS '專案連結（NAS 路徑或外部 URL）'")
    op.execute("COMMENT ON COLUMN project_links.url IS 'NAS 路徑 (/) 或外部 URL (https://)'")

    # 專案里程碑
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_milestones (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            milestone_type VARCHAR(50) DEFAULT 'custom',
            planned_date DATE,
            actual_date DATE,
            status VARCHAR(50) DEFAULT 'pending',
            notes TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_milestones_project_id ON project_milestones(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_milestones_status ON project_milestones(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_milestones_planned_date ON project_milestones(planned_date)")
    op.execute("COMMENT ON TABLE project_milestones IS '專案里程碑'")
    op.execute("COMMENT ON COLUMN project_milestones.milestone_type IS '里程碑類型：design, manufacture, delivery, field_test, acceptance, custom'")
    op.execute("COMMENT ON COLUMN project_milestones.status IS '狀態：pending, in_progress, completed, delayed'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_milestones")
    op.execute("DROP TABLE IF EXISTS project_links")
    op.execute("DROP TABLE IF EXISTS project_attachments")
    op.execute("DROP TABLE IF EXISTS project_meetings")
    op.execute("DROP TABLE IF EXISTS project_members")
    op.execute("DROP TABLE IF EXISTS projects")
