"""新增 sessions 表（Session 持久化）

將 in-memory session 儲存改為 PostgreSQL，重啟不掉線。
SMB 密碼以 AES-256-GCM 加密儲存。

Revision ID: 005
Revises: 004
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('token', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('password_enc', sa.Text(), nullable=False, server_default=''),
        sa.Column('nas_host', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False, server_default='user'),
        sa.Column('app_permissions', JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_sessions_expires', 'sessions', ['expires_at'])
    op.create_index('idx_sessions_user_id', 'sessions', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_sessions_user_id')
    op.drop_index('idx_sessions_expires')
    op.drop_table('sessions')
