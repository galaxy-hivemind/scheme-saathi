"""
Integration tests for Alembic schema migrations against an isolated PostgreSQL database.
Validates clean upgrade to head, expected schema elements, revision tracking, and downgrade.
"""
from pathlib import Path
import os
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text

MIGRATION_TEST_DB_URL = os.getenv(
    "MIGRATION_TEST_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test",
)


def test_alembic_migrations_lifecycle():
    """
    Validates the complete migration lifecycle:
    1. Start from an empty clean schema.
    2. Upgrade to head.
    3. Verify expected tables, columns, indexes, and constraints.
    4. Verify recorded migration revision.
    5. Test downgrade to base.
    6. Verify re-upgrade to head.
    """
    engine = create_engine(MIGRATION_TEST_DB_URL)

    # 1. Clean disposable test database schema
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()

    # 2. Configure Alembic with test database target
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", MIGRATION_TEST_DB_URL)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # 3. Apply migration to head
    command.upgrade(alembic_cfg, "head")

    # 4. Verify tables exist
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "users" in tables
    assert "user_profiles" in tables
    assert "user_consents" in tables
    assert "alembic_version" in tables

    # 5. Verify columns in users table
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    expected_user_cols = {"id", "email", "password_hash", "is_active", "created_at", "updated_at", "auth_provider_id"}
    assert expected_user_cols.issubset(user_cols)

    # 6. Verify columns in user_profiles table
    profile_cols = {col["name"] for col in inspector.get_columns("user_profiles")}
    expected_profile_cols = {
        "id", "user_id", "full_name", "date_of_birth", "gender",
        "state", "district", "residence_type", "occupation",
        "annual_family_income", "preferred_language", "profile_data",
        "created_at", "updated_at",
    }
    assert expected_profile_cols.issubset(profile_cols)

    # 7. Verify columns in user_consents table
    consent_cols = {col["name"] for col in inspector.get_columns("user_consents")}
    expected_consent_cols = {"id", "user_id", "consent_type", "consent_status", "recorded_at", "revoked_at"}
    assert expected_consent_cols.issubset(consent_cols)

    # 8. Verify unique index on users.email
    user_indexes = {idx["name"]: idx for idx in inspector.get_indexes("users")}
    assert "ix_users_email" in user_indexes
    assert user_indexes["ix_users_email"]["unique"] is True

    # 9. Verify current migration revision matches expected head
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "d60b841ec91c"

    # 10. Verify downgrade to base
    command.downgrade(alembic_cfg, "base")
    inspector_downgraded = inspect(engine)
    remaining_tables = set(inspector_downgraded.get_table_names())
    assert "users" not in remaining_tables
    assert "user_profiles" not in remaining_tables
    assert "user_consents" not in remaining_tables

    # 11. Re-upgrade to head confirms idempotency
    command.upgrade(alembic_cfg, "head")
    inspector_reup = inspect(engine)
    assert "users" in set(inspector_reup.get_table_names())

    # 12. Final cleanup
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()
    engine.dispose()
