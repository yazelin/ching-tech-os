"""create login_records table with partitioning

Revision ID: 004
Revises: 003
Create Date: 2025-12-11

登入記錄表 - 完整追蹤登入歷史（使用 RANGE 分區按月分區）
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 建立分區父表
    op.execute("""
        CREATE TABLE login_records (
            id BIGSERIAL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- 使用者
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            username VARCHAR(100) NOT NULL,

            -- 結果
            success BOOLEAN NOT NULL,
            failure_reason VARCHAR(200),

            -- 網路資訊
            ip_address INET NOT NULL,
            user_agent TEXT,

            -- 地理位置（GeoIP）
            geo_country VARCHAR(100),
            geo_city VARCHAR(100),
            geo_latitude DECIMAL(10, 7),
            geo_longitude DECIMAL(10, 7),

            -- 裝置指紋
            device_fingerprint VARCHAR(100),
            device_type VARCHAR(50),
            browser VARCHAR(100),
            os VARCHAR(100),

            -- Session 資訊
            session_id VARCHAR(100),

            -- 分區鍵
            partition_date DATE NOT NULL DEFAULT CURRENT_DATE,

            PRIMARY KEY (id, partition_date)
        ) PARTITION BY RANGE (partition_date)
    """)

    # 建立索引
    op.execute("CREATE INDEX idx_login_records_created_at ON login_records (created_at DESC)")
    op.execute("CREATE INDEX idx_login_records_user_id ON login_records (user_id)")
    op.execute("CREATE INDEX idx_login_records_username ON login_records (username)")
    op.execute("CREATE INDEX idx_login_records_ip_address ON login_records (ip_address)")
    op.execute("CREATE INDEX idx_login_records_success ON login_records (success)")
    op.execute("CREATE INDEX idx_login_records_device_fingerprint ON login_records (device_fingerprint)")

    # 建立當月和下兩個月的分區
    now = datetime.now()
    for i in range(3):
        month = now.replace(day=1) + timedelta(days=32 * i)
        month = month.replace(day=1)
        next_month = month + timedelta(days=32)
        next_month = next_month.replace(day=1)

        partition_name = f"login_records_{month.strftime('%Y_%m')}"
        op.execute(f"""
            CREATE TABLE {partition_name} PARTITION OF login_records
            FOR VALUES FROM ('{month.strftime('%Y-%m-%d')}') TO ('{next_month.strftime('%Y-%m-%d')}')
        """)

    # 建立預設分區（處理未來資料）
    op.execute("""
        CREATE TABLE login_records_default PARTITION OF login_records DEFAULT
    """)

    # 加入註解
    op.execute("COMMENT ON TABLE login_records IS '登入記錄表 - 完整追蹤登入歷史（分區表）'")
    op.execute("COMMENT ON COLUMN login_records.success IS '登入是否成功'")
    op.execute("COMMENT ON COLUMN login_records.failure_reason IS '失敗原因（如密碼錯誤、帳號不存在等）'")
    op.execute("COMMENT ON COLUMN login_records.ip_address IS '登入 IP 位址'")
    op.execute("COMMENT ON COLUMN login_records.user_agent IS '瀏覽器 User-Agent'")
    op.execute("COMMENT ON COLUMN login_records.geo_country IS 'GeoIP 解析的國家'")
    op.execute("COMMENT ON COLUMN login_records.geo_city IS 'GeoIP 解析的城市'")
    op.execute("COMMENT ON COLUMN login_records.geo_latitude IS 'GeoIP 解析的緯度'")
    op.execute("COMMENT ON COLUMN login_records.geo_longitude IS 'GeoIP 解析的經度'")
    op.execute("COMMENT ON COLUMN login_records.device_fingerprint IS '裝置指紋 hash'")
    op.execute("COMMENT ON COLUMN login_records.device_type IS '裝置類型: desktop/mobile/tablet'")
    op.execute("COMMENT ON COLUMN login_records.browser IS '瀏覽器名稱與版本'")
    op.execute("COMMENT ON COLUMN login_records.os IS '作業系統名稱與版本'")
    op.execute("COMMENT ON COLUMN login_records.partition_date IS '分區鍵（日期）'")


def downgrade() -> None:
    # 刪除所有分區和主表
    op.execute("DROP TABLE IF EXISTS login_records CASCADE")
