"""create_application_records

Revision ID: a9b7c5d3e102
Revises: f4a9c3d8210b
Create Date: 2026-11-12 07:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a9b7c5d3e102"
down_revision: Union[str, Sequence[str], None] = "f4a9c3d8210b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create persistent application_records table for normalized Step 5 tracking."""
    op.create_table(
        "application_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", sa.String(128), nullable=False),
        sa.Column("citizen_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schemes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheme_code", sa.String(100), nullable=False),
        sa.Column("scheme_name", sa.String(255), nullable=False),
        sa.Column("official_reference_number", sa.String(128), nullable=True),
        sa.Column("reference_source", sa.String(64), nullable=True),
        sa.Column("submission_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("portal_url", sa.String(500), nullable=False, server_default="https://www.india.gov.in/"),
        sa.Column("tracking_url", sa.String(500), nullable=True),
        sa.Column("application_status", sa.String(64), nullable=False, server_default="draft"),
        sa.Column("submission_method", sa.String(64), nullable=False, server_default="portal_assisted"),
        sa.Column("confirmation_version", sa.Integer(), nullable=True),
        sa.Column("confirmation_hash", sa.String(128), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("application_id", name="uq_application_records_application_id"),
        sa.UniqueConstraint("citizen_id", "application_id", name="uq_application_records_citizen_app"),
    )
    op.create_index("ix_application_records_application_id", "application_records", ["application_id"])
    op.create_index("ix_application_records_citizen_id", "application_records", ["citizen_id"])
    op.create_index("ix_application_records_scheme_id", "application_records", ["scheme_id"])
    op.create_index("ix_application_records_scheme_code", "application_records", ["scheme_code"])
    op.create_index("ix_application_records_official_ref", "application_records", ["official_reference_number"])
    op.create_index("ix_application_records_citizen_status", "application_records", ["citizen_id", "application_status"])


def downgrade() -> None:
    """Drop application_records table."""
    op.drop_index("ix_application_records_citizen_status", table_name="application_records")
    op.drop_index("ix_application_records_official_ref", table_name="application_records")
    op.drop_index("ix_application_records_scheme_code", table_name="application_records")
    op.drop_index("ix_application_records_scheme_id", table_name="application_records")
    op.drop_index("ix_application_records_citizen_id", table_name="application_records")
    op.drop_index("ix_application_records_application_id", table_name="application_records")
    op.drop_table("application_records")
