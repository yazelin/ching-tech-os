"""修改 meeting_date 欄位為 timestamptz 以支援時區

Revision ID: 031
Revises: 030
Create Date: 2026-01-15

修正說明：
將 project_meetings.meeting_date 從 timestamp 改為 timestamptz。
現有資料視為台北時間（Asia/Taipei），轉換後以 UTC 儲存。
"""

from alembic import op


# revision identifiers
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """將 meeting_date 從 timestamp 改為 timestamptz"""
    # 修改 project_meetings.meeting_date 欄位類型
    # 現有資料視為台北時間，轉換成 UTC 儲存
    op.execute("""
        ALTER TABLE project_meetings
        ALTER COLUMN meeting_date TYPE timestamp with time zone
        USING meeting_date AT TIME ZONE 'Asia/Taipei'
    """)


def downgrade() -> None:
    """還原為 timestamp without time zone"""
    # 轉換回台北時間的 timestamp
    op.execute("""
        ALTER TABLE project_meetings
        ALTER COLUMN meeting_date TYPE timestamp without time zone
        USING meeting_date AT TIME ZONE 'Asia/Taipei'
    """)
