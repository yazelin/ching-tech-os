"""create project delivery schedules table

Revision ID: 025
Revises: 024
Create Date: 2026-01-12

專案發包/交貨期程管理 - 追蹤廠商發包與料件交貨狀態
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 專案發包/交貨期程表
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_delivery_schedules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            vendor VARCHAR(200) NOT NULL,
            item VARCHAR(500) NOT NULL,
            quantity VARCHAR(100),
            order_date DATE,
            expected_delivery_date DATE,
            actual_delivery_date DATE,
            status VARCHAR(50) DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            created_by VARCHAR(100)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_schedules_project_id "
        "ON project_delivery_schedules(project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_schedules_status "
        "ON project_delivery_schedules(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_schedules_vendor "
        "ON project_delivery_schedules(vendor)"
    )
    op.execute(
        "COMMENT ON TABLE project_delivery_schedules IS '專案發包/交貨期程'"
    )
    op.execute(
        "COMMENT ON COLUMN project_delivery_schedules.vendor IS '廠商名稱'"
    )
    op.execute(
        "COMMENT ON COLUMN project_delivery_schedules.item IS '料件名稱'"
    )
    op.execute(
        "COMMENT ON COLUMN project_delivery_schedules.quantity IS '數量（含單位，如「2 台」）'"
    )
    op.execute(
        "COMMENT ON COLUMN project_delivery_schedules.status IS "
        "'狀態：pending(待發包), ordered(已發包), delivered(已到貨), completed(已完成)'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_delivery_schedules")
