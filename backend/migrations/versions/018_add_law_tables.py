"""新增律師事務所模組表格

- law_parties：當事人資料
- law_cases：案件資料
- law_case_parties：案件-當事人關聯表

Revision ID: 018
"""

from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 當事人表
    op.create_table(
        "law_parties",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("id_number", sa.String(255), nullable=True),  # 加密儲存
        sa.Column("party_type", sa.String(20), nullable=True),  # natural_person / legal_entity
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # 2. 案件表
    op.create_table(
        "law_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_number", sa.String(50), nullable=True),
        sa.Column("case_name", sa.String(200), nullable=False),
        sa.Column("case_type", sa.String(20), nullable=False),  # civil / criminal / administrative / family
        sa.Column("court", sa.String(50), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),  # plaintiff / defendant / third_party
        sa.Column("status", sa.String(20), server_default="active"),  # active / closed / appealing
        sa.Column("lawyer_name", sa.String(50), nullable=True),
        sa.Column("folder_path", sa.Text(), nullable=True),
        sa.Column("next_court_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # 3. 案件-當事人關聯表
    op.create_table(
        "law_case_parties",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("law_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "party_id",
            sa.Integer(),
            sa.ForeignKey("law_parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),  # plaintiff / defendant / third_party / witness
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "party_id", "role", name="uq_case_party_role"),
    )


def downgrade() -> None:
    op.drop_table("law_case_parties")
    op.drop_table("law_cases")
    op.drop_table("law_parties")
