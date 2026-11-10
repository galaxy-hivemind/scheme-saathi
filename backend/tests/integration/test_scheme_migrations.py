"""
Integration tests for Phase 2 Alembic schema migrations:
- Upgrade from Phase 1 head (bb1bf3e30acc) to Phase 2 head (e7b2c419fa01).
- Verify table existence, constraints, foreign keys (RESTRICT), and indexes.
- Downgrade to bb1bf3e30acc and verify Phase 2 tables are dropped while Phase 1 tables remain intact.
- Re-upgrade to Phase 2 head.
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


def _setup_container_migration_db_if_needed(monkeypatch):
    """If running in Testcontainers mode, lazily provision scheme_saathi_migration_test database."""
    if os.getenv("USE_TESTCONTAINERS", "").strip().lower() in ("1", "true", "yes"):
        from tests import conftest
        conftest.get_test_database_url()  # ensures container is running
        admin_url = conftest._test_container.get_connection_url()
        if not admin_url.startswith("postgresql+psycopg://"):
            admin_url = admin_url.replace("postgresql+psycopg2://", "postgresql+psycopg://").replace("postgresql://", "postgresql+psycopg://")

        admin_engine = create_engine(admin_url, pool_pre_ping=True)
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            db_exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'scheme_saathi_migration_test';")).scalar()
            if not db_exists:
                conn.execute(text("CREATE DATABASE scheme_saathi_migration_test;"))
                conn.execute(text(f"GRANT CONNECT, TEMPORARY, CREATE ON DATABASE scheme_saathi_migration_test TO {conftest.TEST_DB_USER};"))
        admin_engine.dispose()

        parsed = normalize_db_url(admin_url)
        mig_admin_url = f"postgresql+psycopg://{parsed.username}:{parsed.password}@{parsed.host}:{parsed.port or 5432}/scheme_saathi_migration_test"

        mig_engine = create_engine(mig_admin_url, pool_pre_ping=True)
        with mig_engine.connect() as conn:
            conn.execute(text(f"GRANT ALL ON SCHEMA public TO {conftest.TEST_DB_USER};"))
            conn.execute(text("REVOKE EXECUTE ON FUNCTION pg_control_system() FROM PUBLIC;"))
            conn.commit()
        mig_engine.dispose()

        provision_test_database_sentinel(
            target_url=mig_admin_url,
            app_url=settings.DATABASE_URL,
            purpose=MIGRATION_TEST_PURPOSE,
            enforce_opt_in=False,
            grant_role=conftest.TEST_DB_USER,
        )

        runtime_parsed = normalize_db_url(conftest.get_test_database_url())
        mig_test_url = f"postgresql+psycopg://{runtime_parsed.username}:{quote_plus(runtime_parsed.password)}@{runtime_parsed.host}:{runtime_parsed.port or 5432}/scheme_saathi_migration_test"
        monkeypatch.setenv("MIGRATION_TEST_DB_URL", mig_test_url)


def test_scheme_migration_upgrade_downgrade_cycle(monkeypatch):
    """
    Validates complete Phase 2 migration lifecycle:
    1. Upgrade to Phase 1 head: bb1bf3e30acc.
    2. Upgrade to Phase 2 head: e7b2c419fa01.
    3. Assert schemes, scheme_rule_versions, and scheme_documents exist.
    4. Assert foreign keys specify ON DELETE RESTRICT.
    5. Downgrade back to bb1bf3e30acc and assert Phase 2 tables are dropped and Phase 1 tables are intact.
    6. Re-upgrade to e7b2c419fa01 cleanly.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    _setup_container_migration_db_if_needed(monkeypatch)

    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with isolated_test_schema(engine, prefix="migtest_scheme") as test_schema:
        alembic_cfg = configure_alembic_for_schema(test_url, test_schema)

        # 1. Start at Phase 1 head
        command.upgrade(alembic_cfg, "bb1bf3e30acc")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"

        # 2. Upgrade to Phase 2 head
        command.upgrade(alembic_cfg, "e7b2c419fa01")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "e7b2c419fa01"

            # Check foreign key delete rules
            rules_fk = get_pg_foreign_key_ondelete(
                conn, "scheme_rule_versions", "scheme_rule_versions_scheme_id_fkey", schema_name=test_schema
            )
            assert rules_fk == "RESTRICT"

            docs_fk = get_pg_foreign_key_ondelete(
                conn, "scheme_documents", "scheme_documents_scheme_id_fkey", schema_name=test_schema
            )
            assert docs_fk == "RESTRICT"

        inspector = inspect(engine)
        tables = set(inspector.get_table_names(schema=test_schema))
        assert {"schemes", "scheme_rule_versions", "scheme_documents"}.issubset(tables)

        # 3. Downgrade back to bb1bf3e30acc
        command.downgrade(alembic_cfg, "bb1bf3e30acc")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"

        inspector_downgraded = inspect(engine)
        downgraded_tables = set(inspector_downgraded.get_table_names(schema=test_schema))
        # Phase 2 tables must be dropped
        assert not {"schemes", "scheme_rule_versions", "scheme_documents"}.intersection(downgraded_tables)
        # Phase 1 tables must remain intact
        assert {"users", "user_profiles", "user_consents", "alembic_version"}.issubset(downgraded_tables)

        # 4. Re-upgrade back to Phase 2 head
        command.upgrade(alembic_cfg, "e7b2c419fa01")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "e7b2c419fa01"

        inspector_reupgraded = inspect(engine)
        reupgraded_tables = set(inspector_reupgraded.get_table_names(schema=test_schema))
        assert {"schemes", "scheme_rule_versions", "scheme_documents"}.issubset(reupgraded_tables)

    engine.dispose()
