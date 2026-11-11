"""create_citizen_documents_and_application_drafts_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-11 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create citizen_documents and application_drafts tables."""
    # 1. citizen_documents
    op.create_table(
        "citizen_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "beneficiary_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beneficiary_profiles.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column(
            "extracted_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "verification_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(
            "char_length(trim(document_type)) > 0",
            name="ck_citizen_documents_type_nonempty",
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name="ck_citizen_documents_file_size",
        ),
        sa.CheckConstraint(
            "mime_type IN ('application/pdf', 'image/jpeg', 'image/png')",
            name="ck_citizen_documents_mime",
        ),
        sa.CheckConstraint(
            "verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED')",
            name="ck_citizen_documents_status",
        ),
    )
    op.create_index(
        "ix_citizen_documents_user_id", "citizen_documents", ["user_id"]
    )
    op.create_index(
        "ix_citizen_documents_beneficiary_id",
        "citizen_documents",
        ["beneficiary_id"],
    )
    op.create_index(
        "ix_citizen_documents_user_type",
        "citizen_documents",
        ["user_id", "document_type"],
    )
    op.create_index(
        "ix_citizen_documents_checksum",
        "citizen_documents",
        ["user_id", "checksum_sha256"],
    )

    # 2. application_drafts
    op.create_table(
        "application_drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "beneficiary_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("beneficiary_profiles.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "scheme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schemes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'DRAFT'"),
        ),
        sa.Column(
            "prefilled_data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "attached_documents",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("official_portal_url", sa.String(1000), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("external_reference_number", sa.String(100), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'READY', 'SUBMITTED', 'ARCHIVED')",
            name="ck_application_drafts_status",
        ),
    )
    op.create_index(
        "ix_application_drafts_user_id", "application_drafts", ["user_id"]
    )
    op.create_index(
        "ix_application_drafts_beneficiary_id",
        "application_drafts",
        ["beneficiary_id"],
    )
    op.create_index(
        "ix_application_drafts_scheme_id",
        "application_drafts",
        ["scheme_id"],
    )
    op.create_index(
        "ix_application_drafts_user_scheme_status",
        "application_drafts",
        ["user_id", "scheme_id", "status"],
    )


def downgrade() -> None:
    """Drop application_drafts and citizen_documents tables."""
    # 1. Drop application_drafts
    op.drop_index(
        "ix_application_drafts_user_scheme_status",
        table_name="application_drafts",
    )
    op.drop_index(
        "ix_application_drafts_scheme_id", table_name="application_drafts"
    )
    op.drop_index(
        "ix_application_drafts_beneficiary_id",
        table_name="application_drafts",
    )
    op.drop_index(
        "ix_application_drafts_user_id", table_name="application_drafts"
    )
    op.drop_table("application_drafts")

    # 2. Drop citizen_documents
    op.drop_index(
        "ix_citizen_documents_checksum", table_name="citizen_documents"
    )
    op.drop_index(
        "ix_citizen_documents_user_type", table_name="citizen_documents"
    )
    op.drop_index(
        "ix_citizen_documents_beneficiary_id", table_name="citizen_documents"
    )
    op.drop_index(
        "ix_citizen_documents_user_id", table_name="citizen_documents"
    )
    op.drop_table("citizen_documents")
