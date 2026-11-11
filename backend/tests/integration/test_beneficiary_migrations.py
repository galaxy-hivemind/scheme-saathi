"""
Integration tests for Phase 3 Beneficiary Profiles Alembic schema migration:
- Upgrade from Phase 2 head (e7b2c419fa01) to Phase 3 head (f2c4b5e6d7a8).
- Verify table existence, constraints, foreign keys (CASCADE to users), and indexes.
- Downgrade to e7b2c419fa01 and verify beneficiary_profiles table is dropped while prior tables remain intact.
- Re-upgrade to f2c4b5e6d7a8.
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


def test_beneficiary_profiles_migration_lifecycle(monkeypatch):
    """
    Test complete lifecycle of f2c4b5e6d7a8 (beneficiary_profiles):
    1. Upgrade to e7b2c419fa01 (Phase 2 head).
    2. Upgrade to f2c4b5e6d7a8 (Phase 3 beneficiary_profiles).
    3. Verify table schema, constraints, foreign keys, and indexes.
    4. Downgrade to e7b2c419fa01 and verify table is cleanly dropped.
    5. Re-upgrade to f2c4b5e6d7a8.
    """
    _setup_container_migration_db_if_needed(monkeypatch)

    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with isolated_test_schema(engine, prefix="migtest_beneficiary") as test_schema:
        alembic_cfg = configure_alembic_for_schema(test_url, test_schema)

        # 1. Start at Phase 2 head
        command.upgrade(alembic_cfg, "e7b2c419fa01")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "e7b2c419fa01"

        # 2. Upgrade to Phase 3 head
        command.upgrade(alembic_cfg, "f2c4b5e6d7a8")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "f2c4b5e6d7a8"

            # Check foreign key delete rule is CASCADE to users
            user_fk = get_pg_foreign_key_ondelete(
                conn, "beneficiary_profiles", "beneficiary_profiles_user_id_fkey", schema_name=test_schema
            )
            assert user_fk == "CASCADE"

        inspector = inspect(engine)
        tables = set(inspector.get_table_names(schema=test_schema))
        assert "beneficiary_profiles" in tables
        assert {"users", "user_profiles", "schemes", "scheme_rule_versions"}.issubset(tables)

        columns = {c["name"]: c for c in inspector.get_columns("beneficiary_profiles", schema=test_schema)}
        assert "id" in columns
        assert "user_id" in columns
        assert "full_name" in columns
        assert "relationship" in columns
        assert "date_of_birth" in columns
        assert "gender" in columns
        assert "residence_type" in columns
        assert "annual_family_income" in columns
        assert "profile_data" in columns

        indexes = {ix["name"] for ix in inspector.get_indexes("beneficiary_profiles", schema=test_schema)}
        assert "ix_beneficiary_profiles_user_id" in indexes
        assert "ix_beneficiary_profiles_user_rel" in indexes

        # 3. Downgrade back to e7b2c419fa01
        command.downgrade(alembic_cfg, "e7b2c419fa01")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "e7b2c419fa01"

        inspector_downgraded = inspect(engine)
        downgraded_tables = set(inspector_downgraded.get_table_names(schema=test_schema))
        assert "beneficiary_profiles" not in downgraded_tables
        assert {"users", "user_profiles", "schemes", "scheme_rule_versions"}.issubset(downgraded_tables)

        # 4. Re-upgrade back to Phase 3 head
        command.upgrade(alembic_cfg, "f2c4b5e6d7a8")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "f2c4b5e6d7a8"

        inspector_reupgraded = inspect(engine)
        reupgraded_tables = set(inspector_reupgraded.get_table_names(schema=test_schema))
        assert "beneficiary_profiles" in reupgraded_tables

    engine.dispose()
