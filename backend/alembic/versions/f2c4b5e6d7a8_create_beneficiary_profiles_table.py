"""create_beneficiary_profiles_table

Revision ID: f2c4b5e6d7a8
Revises: e7b2c419fa01
Create Date: 2026-11-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f2c4b5e6d7a8"
down_revision: Union[str, Sequence[str], None] = "e7b2c419fa01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create beneficiary_profiles table for managing family members."""
    op.create_table(
        "beneficiary_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(50), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("residence_type", sa.String(50), nullable=True),
        sa.Column("occupation", sa.String(100), nullable=True),
        sa.Column("annual_family_income", sa.Numeric(12, 2), nullable=True),
        sa.Column("profile_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("char_length(trim(full_name)) > 0", name="ck_beneficiary_profiles_full_name"),
        sa.CheckConstraint(
            "relationship IN ('father', 'mother', 'spouse', 'son', 'daughter', 'sibling', 'guardian', 'other')",
            name="ck_beneficiary_profiles_relationship",
        ),
        sa.CheckConstraint(
            "residence_type IS NULL OR residence_type IN ('rural', 'urban', 'semi_urban')",
            name="ck_beneficiary_profiles_residence_type",
        ),
        sa.CheckConstraint(
            "annual_family_income IS NULL OR annual_family_income >= 0",
            name="ck_beneficiary_profiles_annual_income",
        ),
    )
    op.create_index("ix_beneficiary_profiles_user_id", "beneficiary_profiles", ["user_id"])
    op.create_index("ix_beneficiary_profiles_user_rel", "beneficiary_profiles", ["user_id", "relationship"])


def downgrade() -> None:
    """Drop beneficiary_profiles table."""
    op.drop_index("ix_beneficiary_profiles_user_rel", table_name="beneficiary_profiles")
    op.drop_index("ix_beneficiary_profiles_user_id", table_name="beneficiary_profiles")
    op.drop_table("beneficiary_profiles")
