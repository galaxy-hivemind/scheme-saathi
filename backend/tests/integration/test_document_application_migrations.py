"""
Integration tests for Phase 3 / Increment 3 Citizen Documents and Application Drafts Alembic schema migration:
- Upgrade from Conversational Intake head (a1b2c3d4e5f6) to Documents & Applications head (b2c3d4e5f6a7).
- Verify table existence, constraints, foreign keys (CASCADE to users, RESTRICT to schemes, etc.), and indexes.
- Downgrade to a1b2c3d4e5f6 and verify citizen_documents, application_drafts tables are dropped.
- Re-upgrade to b2c3d4e5f6a7.
"""
from pathlib import Path
from urllib.parse import quote_plus
import os
import uuid
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings
from app.core.db_safety import provision_test_database_sentinel, MIGRATION_TEST_PURPOSE, normalize_db_url
from tests.integration.test_migrations import (
    get_migration_test_db_url,
    validate_migration_test_target,
    verify_migration_connected_role,
    isolated_test_schema,
    configure_alembic_for_schema,
    get_pg_foreign_key_ondelete,
)
from tests.integration.test_scheme_migrations import _setup_container_migration_db_if_needed


def test_document_and_application_migration_lifecycle(monkeypatch):
    """
    Test complete lifecycle of b2c3d4e5f6a7 (citizen_documents, application_drafts):
    1. Upgrade to a1b2c3d4e5f6 (Phase 3 Increment 2 chat head).
    2. Upgrade to b2c3d4e5f6a7 (Phase 3 Increment 3 documents & applications).
    3. Verify table schema, constraints, foreign keys, and indexes.
    4. Downgrade to a1b2c3d4e5f6 and verify tables are cleanly dropped.
    5. Re-upgrade to b2c3d4e5f6a7.
    """
    _setup_container_migration_db_if_needed(monkeypatch)

    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with isolated_test_schema(engine, prefix="migtest_docs_apps") as test_schema:
        alembic_cfg = configure_alembic_for_schema(test_url, test_schema)

        # 1. Start at a1b2c3d4e5f6
        command.upgrade(alembic_cfg, "a1b2c3d4e5f6")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "a1b2c3d4e5f6"

        # 2. Upgrade to b2c3d4e5f6a7
        command.upgrade(alembic_cfg, "b2c3d4e5f6a7")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "b2c3d4e5f6a7"

            # Check foreign key delete rules
            doc_user_fk = get_pg_foreign_key_ondelete(
                conn, "citizen_documents", "citizen_documents_user_id_fkey", schema_name=test_schema
            )
            assert doc_user_fk == "CASCADE"

            doc_ben_fk = get_pg_foreign_key_ondelete(
                conn, "citizen_documents", "citizen_documents_beneficiary_id_fkey", schema_name=test_schema
            )
            assert doc_ben_fk == "CASCADE"

            app_user_fk = get_pg_foreign_key_ondelete(
                conn, "application_drafts", "application_drafts_user_id_fkey", schema_name=test_schema
            )
            assert app_user_fk == "CASCADE"

            app_ben_fk = get_pg_foreign_key_ondelete(
                conn, "application_drafts", "application_drafts_beneficiary_id_fkey", schema_name=test_schema
            )
            assert app_ben_fk == "CASCADE"

            app_scheme_fk = get_pg_foreign_key_ondelete(
                conn, "application_drafts", "application_drafts_scheme_id_fkey", schema_name=test_schema
            )
            assert app_scheme_fk == "RESTRICT"

            # Check indexes on citizen_documents
            doc_indexes = conn.execute(
                text(
                    f"SELECT indexname FROM pg_indexes WHERE schemaname = '{test_schema}' AND tablename = 'citizen_documents'"
                )
            ).scalars().all()
            assert "ix_citizen_documents_user_id" in doc_indexes
            assert "ix_citizen_documents_beneficiary_id" in doc_indexes
            assert "ix_citizen_documents_user_type" in doc_indexes
            assert "ix_citizen_documents_checksum" in doc_indexes

            # Check indexes on application_drafts
            app_indexes = conn.execute(
                text(
                    f"SELECT indexname FROM pg_indexes WHERE schemaname = '{test_schema}' AND tablename = 'application_drafts'"
                )
            ).scalars().all()
            assert "ix_application_drafts_user_id" in app_indexes
            assert "ix_application_drafts_beneficiary_id" in app_indexes
            assert "ix_application_drafts_scheme_id" in app_indexes
            assert "ix_application_drafts_user_scheme_status" in app_indexes

        # 3. Downgrade to a1b2c3d4e5f6
        command.downgrade(alembic_cfg, "a1b2c3d4e5f6")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "a1b2c3d4e5f6"

            insp = inspect(conn)
            tables = insp.get_table_names(schema=test_schema)
            assert "citizen_documents" not in tables
            assert "application_drafts" not in tables

        # 4. Re-upgrade to b2c3d4e5f6a7
        command.upgrade(alembic_cfg, "b2c3d4e5f6a7")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "b2c3d4e5f6a7"
            insp = inspect(conn)
            tables = insp.get_table_names(schema=test_schema)
            assert "citizen_documents" in tables
            assert "application_drafts" in tables
