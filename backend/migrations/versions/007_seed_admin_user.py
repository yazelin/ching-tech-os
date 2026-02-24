"""建立預設管理員帳號

插入預設管理員帳號 ct，首次登入強制變更密碼。

Revision ID: 007
Revises: 006
Create Date: 2026-02-24
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

# ct / 36274806 的 bcrypt hash
ADMIN_PASSWORD_HASH = '$2b$12$0Manfm0XjvdWztbGihAKpu4aNajUQAxZclwcMDf6zFQl.vR.7YppS'


def upgrade() -> None:
    connection = op.get_bind()
    raw_conn = connection.connection.dbapi_connection
    cur = raw_conn.cursor()

    cur.execute(
        """
        INSERT INTO users (username, display_name, password_hash, role, must_change_password)
        VALUES ('ct', '管理員', %s, 'admin', TRUE)
        ON CONFLICT (username) DO NOTHING
        """,
        (ADMIN_PASSWORD_HASH,),
    )


def downgrade() -> None:
    connection = op.get_bind()
    raw_conn = connection.connection.dbapi_connection
    cur = raw_conn.cursor()
    cur.execute("DELETE FROM users WHERE username = 'ct' AND display_name = '管理員'")
