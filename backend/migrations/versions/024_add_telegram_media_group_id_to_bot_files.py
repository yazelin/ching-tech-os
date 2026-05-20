"""bot_files 新增 telegram_media_group_id 欄位

Telegram 相冊（album）中每張圖片屬於同一個 media_group，
儲存 media_group_id 後可直接用強訊號（album 成員身份）
取代時間段啟發式演算法，精準取得所有參考圖片。

Revision ID: 024
"""

from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bot_files",
        sa.Column(
            "telegram_media_group_id",
            sa.String(64),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_bot_files_telegram_media_group",
        "bot_files",
        ["telegram_media_group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bot_files_telegram_media_group", table_name="bot_files")
    op.drop_column("bot_files", "telegram_media_group_id")
