"""新增 consultation_transcripts 表

儲存診間錄影逐字稿及 AI 分析結果。

Revision ID: 022
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultation_transcripts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel", sa.VARCHAR(10), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("segments", JSONB()),
        sa.Column("scene_type", sa.VARCHAR(20), server_default="unclassified"),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_score", sa.SmallInteger()),
        sa.Column("ai_score_breakdown", JSONB()),
        sa.Column("ai_feedback", sa.Text()),
        sa.Column("ai_roles", JSONB()),
        sa.Column("ai_tags", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("ai_raw_response", JSONB()),
        sa.Column("nas_path", sa.VARCHAR(500)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_ct_start_time", "consultation_transcripts", ["start_time"], postgresql_using="btree")
    op.create_index("idx_ct_channel", "consultation_transcripts", ["channel"])
    op.create_index("idx_ct_scene_type", "consultation_transcripts", ["scene_type"])
    op.create_index(
        "idx_ct_ai_score",
        "consultation_transcripts",
        ["ai_score"],
        postgresql_where=sa.text("ai_score IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("consultation_transcripts")
