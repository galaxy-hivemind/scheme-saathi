"""create_scheme_catalogue_tables

Revision ID: e7b2c419fa01
Revises: bb1bf3e30acc
Create Date: 2026-11-10 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7b2c419fa01"
down_revision: Union[str, Sequence[str], None] = "bb1bf3e30acc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create schemes, scheme_rule_versions, and scheme_documents tables
    with check constraints, foreign-key RESTRICT rules, and FTS indexing.
    """
    # 1. schemes table
    op.create_table(
        "schemes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scheme_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_title", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ministry", sa.String(255), nullable=False),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("geographic_scope", sa.String(20), nullable=False, server_default="central"),
        sa.Column("target_beneficiaries", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("benefits", sa.Text(), nullable=False),
        sa.Column("official_url", sa.String(1000), nullable=True),
        sa.Column("application_url", sa.String(1000), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("scheme_status", sa.String(30), nullable=False, server_default="pending_verification"),
        sa.Column("last_retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("scheme_code", name="uq_schemes_scheme_code"),
        sa.CheckConstraint(
            "category IN ('agriculture', 'education', 'health', 'housing', 'employment', 'women_welfare', 'children_welfare', 'senior_citizens', 'disability', 'financial_inclusion', 'social_security', 'skill_development')",
            name="ck_schemes_category",
        ),
        sa.CheckConstraint("geographic_scope = 'central'", name="ck_schemes_geographic_scope"),
        sa.CheckConstraint("scheme_status IN ('active', 'inactive', 'pending_verification')", name="ck_schemes_status"),
    )

    op.create_index("ix_schemes_status_category", "schemes", ["scheme_status", "category"])
    op.execute(
        "CREATE INDEX ix_schemes_fts ON schemes USING gin ("
        "(to_tsvector('english', coalesce(scheme_code, '') || ' ' || coalesce(name, '') || ' ' || "
        "coalesce(description, '') || ' ' || coalesce(ministry, '') || ' ' || coalesce(category, '') || ' ' || "
        "coalesce(benefits, '')) || array_to_tsvector(target_beneficiaries))"
        ");"
    )

    # 2. scheme_rule_versions table
    op.create_table(
        "scheme_rule_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scheme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schemes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("eligibility_criteria", postgresql.JSONB(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("scheme_id", "version", name="uq_scheme_rule_versions_scheme_version"),
        sa.CheckConstraint("version >= 1", name="ck_scheme_rule_versions_version"),
    )

    op.create_index("ix_scheme_rule_versions_scheme_id", "scheme_rule_versions", ["scheme_id"])
    op.create_index(
        "uq_scheme_rule_versions_active",
        "scheme_rule_versions",
        ["scheme_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # 3. scheme_documents table
    op.create_table(
        "scheme_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scheme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schemes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("alternatives", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("issuing_authority", sa.String(255), nullable=True),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("scheme_id", "document_type", name="uq_scheme_documents_scheme_doc_type"),
    )

    op.create_index("ix_scheme_documents_scheme_id", "scheme_documents", ["scheme_id"])


def downgrade() -> None:
    """
    Revert Phase 2 tables, indexes, and constraints cleanly.
    """
    op.drop_index("ix_scheme_documents_scheme_id", table_name="scheme_documents")
    op.drop_table("scheme_documents")

    op.drop_index(
        "uq_scheme_rule_versions_active",
        table_name="scheme_rule_versions",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_index("ix_scheme_rule_versions_scheme_id", table_name="scheme_rule_versions")
    op.drop_table("scheme_rule_versions")

    op.execute("DROP INDEX IF EXISTS ix_schemes_fts;")
    op.drop_index("ix_schemes_status_category", table_name="schemes")
    op.drop_table("schemes")
