"""users 加 nas_username（NAS 帳號綁定）

平台帳號與 NAS 帳號脫鉤：username 是平台識別，nas_username 是綁定的 NAS 帳號。
既有帳號全部源自 NAS 登入，回填 nas_username = username。

Revision ID: 026
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nas_username", sa.String(100), nullable=True))
    op.execute("UPDATE users SET nas_username = username WHERE nas_username IS NULL")
    op.create_unique_constraint("uq_users_nas_username", "users", ["nas_username"])


def downgrade() -> None:
    op.drop_constraint("uq_users_nas_username", "users", type_="unique")
    op.drop_column("users", "nas_username")
