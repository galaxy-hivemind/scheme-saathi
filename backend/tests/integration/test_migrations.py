"""
Integration tests for Alembic schema migrations against an isolated PostgreSQL schema.
Validates safety guards, explicit opt-in enforcement, target database identity checks,
schema isolation (never dropping public), fresh upgrade to head, incremental upgrade/downgrade,
foreign key constraint actions (RESTRICT vs CASCADE), and preservation of unrelated schemas.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import sys
import uuid
import warnings

import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.db_safety import validate_database_target, normalize_db_url

MIGRATION_TEST_DB_URL = os.getenv(
    "MIGRATION_TEST_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test",
)

MIGRATION_OPT_IN_VARS = ["ALLOW_MIGRATION_TESTS", "ALLOW_DESTRUCTIVE_MIGRATION_TESTS"]


def validate_migration_test_target(test_url: str, app_url: str, enforce_opt_in: bool = True) -> None:
    """Pre-flight validation for migration test execution using shared db_safety engine."""
    validate_database_target(
        target_url=test_url,
        app_url=app_url,
        target_label="migration test database",
        enforce_opt_in=enforce_opt_in,
        opt_in_env_vars=MIGRATION_OPT_IN_VARS,
    )


@contextmanager
def isolated_test_schema(engine, prefix: str = "migtest"):
    """
    Context manager providing a genuinely isolated, ephemeral PostgreSQL schema.
    Creates schema '{prefix}_{uuid}' for the test run.
    Guarantees teardown via DROP SCHEMA CASCADE, preserving any in-flight test exceptions.
    Never drops or modifies the public schema.
    """
    schema_name = f"{prefix}_{uuid.uuid4().hex[:12]}"
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema_name}";'))
        conn.commit()

    try:
        yield schema_name
    finally:
        exc_type, _, _ = sys.exc_info()
        try:
            with engine.connect() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;'))
                conn.commit()
        except Exception as teardown_exc:
            if exc_type is not None:
                warnings.warn(f"Teardown error dropping schema {schema_name}: {teardown_exc}", stacklevel=2)
            else:
                raise


@contextmanager
def managed_control_schema(engine, prefix: str = "control"):
    """
    Context manager that safely manages an isolated control schema.
    Guarantees cleanup of the schema even if setup or testing fails partially,
    preserving any active exception during teardown.
    """
    schema_name = f"{prefix}_{uuid.uuid4().hex[:12]}"
    created = False
    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema_name}";'))
            conn.commit()
            created = True
        yield schema_name
    finally:
        if created:
            exc_type, _, _ = sys.exc_info()
            try:
                with engine.connect() as conn:
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;'))
                    conn.commit()
            except Exception as teardown_exc:
                if exc_type is not None:
                    warnings.warn(
                        f"Teardown error dropping control schema {schema_name}: {teardown_exc}",
                        stacklevel=2,
                    )
                else:
                    raise


def get_pg_foreign_key_ondelete(conn, table_name: str, constraint_name: str, schema_name: str = "public") -> str:
    """
    Queries PostgreSQL's pg_constraint catalog filtered by schema namespace for authoritative confdeltype.
    confdeltype values: 'r' = RESTRICT, 'c' = CASCADE, 'a' = NO ACTION, 'n' = SET NULL.
    """
    query = text("""
        SELECT c.confdeltype
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = :schema
          AND t.relname = :table
          AND c.conname = :conname;
    """)
    result = conn.execute(query, {"schema": schema_name, "table": table_name, "conname": constraint_name}).scalar()
    mapping = {"r": "RESTRICT", "c": "CASCADE", "a": "NO ACTION", "n": "SET NULL"}
    return mapping.get(result, str(result))


def configure_alembic_for_schema(test_url: str, schema_name: str) -> Config:
    """Helper to configure Alembic Config for an isolated schema."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", test_url)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("schema_name", schema_name)
    alembic_cfg.set_main_option("version_table_schema", schema_name)
    return alembic_cfg


# ── Safety Guard Tests ────────────────────────────────────────────────────────

def test_safety_guard_rejects_missing_opt_in(monkeypatch):
    """Verify that migration tests refuse to run without explicit opt-in environment variable."""
    monkeypatch.delenv("ALLOW_MIGRATION_TESTS", raising=False)
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_MIGRATION_TESTS", raising=False)
    monkeypatch.delenv("ALLOW_TEST_DB_RESET", raising=False)
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_TESTS", raising=False)
    monkeypatch.delenv("ALLOW_TEST_DB_WIPE", raising=False)

    with pytest.raises(PermissionError, match="explicit opt-in required"):
        validate_migration_test_target(
            test_url=MIGRATION_TEST_DB_URL,
            app_url=settings.DATABASE_URL,
            enforce_opt_in=True,
        )


def test_safety_guard_rejects_empty_target(monkeypatch):
    """Verify that an empty test URL is rejected."""
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    with pytest.raises(ValueError, match="Database URL cannot be empty"):
        validate_migration_test_target(
            test_url="",
            app_url=settings.DATABASE_URL,
            enforce_opt_in=True,
        )


def test_safety_guard_rejects_app_database_url(monkeypatch):
    """Verify that target matching settings.DATABASE_URL is rejected."""
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    with pytest.raises(ValueError, match="matches.*active application database|points to the active application database"):
        validate_migration_test_target(
            test_url=settings.DATABASE_URL,
            app_url=settings.DATABASE_URL,
            enforce_opt_in=True,
        )


def test_safety_guard_rejects_hostname_and_driver_aliases(monkeypatch):
    """
    Verify that pointing to the application database via IP alias (127.0.0.1 vs localhost)
    or alternate driver scheme (postgresql+psycopg://) is rejected.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database

    alias_url = f"postgresql+psycopg://postgres:postgres@127.0.0.1:{app_parsed.port or 5432}/{app_db}"
    with pytest.raises(ValueError, match="matches.*active application database|points to the active application database"):
        validate_migration_test_target(
            test_url=alias_url,
            app_url=settings.DATABASE_URL,
            enforce_opt_in=True,
        )


def test_safety_guard_accepts_valid_isolated_target(monkeypatch):
    """Verify that a distinct target database with opt-in enabled passes validation."""
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    validate_migration_test_target(
        test_url=MIGRATION_TEST_DB_URL,
        app_url=settings.DATABASE_URL,
        enforce_opt_in=True,
    )


def test_teardown_preserves_original_test_failure(monkeypatch):
    """Verify that teardown cleans up the schema without masking an in-flight test assertion error."""
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    validate_migration_test_target(MIGRATION_TEST_DB_URL, settings.DATABASE_URL)
    engine = create_engine(MIGRATION_TEST_DB_URL)

    created_schema = None
    try:
        with pytest.raises(ZeroDivisionError, match="division by zero"):
            with isolated_test_schema(engine, prefix="test_fail") as schema_name:
                created_schema = schema_name
                # Verify schema exists during block
                with engine.connect() as conn:
                    exists = conn.execute(
                        text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                        {"s": schema_name},
                    ).scalar()
                    assert exists is True
                # Trigger intentional exception
                _ = 1 / 0
    finally:
        # Verify schema was cleaned up despite the exception
        if created_schema:
            with engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                    {"s": created_schema},
                ).scalar()
                assert exists is False
        engine.dispose()


# ── Schema Isolation & Unrelated Schema Protection Tests ──────────────────────

def test_unrelated_schemas_and_public_remain_untouched(monkeypatch):
    """
    Requirement 8:
    Proves that running migrations inside an isolated schema:
    1. Leaves existing unrelated schemas and their tables 100% untouched.
    2. Leaves the public schema completely untouched (zero migration tables created in public).
    3. Guarantees that dropping the isolated schema does not affect the unrelated schema.
    4. Ensures control-schema creation, sentinel records, and testing run in an exception-safe structure.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    validate_migration_test_target(MIGRATION_TEST_DB_URL, settings.DATABASE_URL)
    engine = create_engine(MIGRATION_TEST_DB_URL)

    # Wrap entire control schema lifecycle inside managed_control_schema context
    with managed_control_schema(engine, prefix="control") as control_schema:
        # Set up an unrelated control schema with baseline data inside protected context
        with engine.connect() as conn:
            conn.execute(text(f'CREATE TABLE "{control_schema}".sentinel_records (id INT PRIMARY KEY, name TEXT);'))
            conn.execute(text(f'INSERT INTO "{control_schema}".sentinel_records VALUES (42, \'untouched_data\');'))
            conn.commit()

        # Run migrations in an isolated test schema
        with isolated_test_schema(engine, prefix="migtest_iso") as test_schema:
            alembic_cfg = configure_alembic_for_schema(MIGRATION_TEST_DB_URL, test_schema)

            # Run full migration to head
            command.upgrade(alembic_cfg, "head")

            inspector = inspect(engine)

            # 1. Migration tables exist in isolated test schema
            test_tables = set(inspector.get_table_names(schema=test_schema))
            assert {"users", "user_profiles", "user_consents", "alembic_version"}.issubset(test_tables)

            # 2. Public schema has NO migration tables created in it
            public_tables = set(inspector.get_table_names(schema="public"))
            assert not {"users", "user_profiles", "user_consents", "alembic_version"}.intersection(public_tables)

            # 3. Control schema remains completely untouched during migration
            control_tables = set(inspector.get_table_names(schema=control_schema))
            assert control_tables == {"sentinel_records"}

            with engine.connect() as conn:
                sentinel_val = conn.execute(
                    text(f'SELECT name FROM "{control_schema}".sentinel_records WHERE id = 42')
                ).scalar()
                assert sentinel_val == "untouched_data"

        # After isolated test schema teardown, control schema must STILL exist and be intact
        inspector_post = inspect(engine)
        control_tables_post = set(inspector_post.get_table_names(schema=control_schema))
        assert control_tables_post == {"sentinel_records"}

        with engine.connect() as conn:
            sentinel_val_post = conn.execute(
                text(f'SELECT name FROM "{control_schema}".sentinel_records WHERE id = 42')
            ).scalar()
            assert sentinel_val_post == "untouched_data"

    engine.dispose()


# ── Migration Lifecycle & Constraint Assertion Tests ──────────────────────────

def test_alembic_fresh_database_upgrade_head_and_foreign_keys(monkeypatch):
    """
    Validates fresh database path inside an isolated PostgreSQL schema:
    1. Pre-flight validation and opt-in enforcement.
    2. Ephemeral schema creation.
    3. Direct upgrade to head without touching public.
    4. Asserts user_consents.user_id ondelete is RESTRICT.
    5. Asserts user_profiles.user_id ondelete is CASCADE.
    6. Verifies public schema has zero migration tables.
    7. Clean teardown dropping only the ephemeral test schema.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    validate_migration_test_target(MIGRATION_TEST_DB_URL, settings.DATABASE_URL)
    engine = create_engine(MIGRATION_TEST_DB_URL)

    with isolated_test_schema(engine, prefix="migtest_fresh") as test_schema:
        alembic_cfg = configure_alembic_for_schema(MIGRATION_TEST_DB_URL, test_schema)

        # Upgrade to head
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(engine)
        test_tables = set(inspector.get_table_names(schema=test_schema))
        assert {"users", "user_profiles", "user_consents", "alembic_version"}.issubset(test_tables)

        # Verify public schema untouched
        public_tables = set(inspector.get_table_names(schema="public"))
        assert not {"users", "user_profiles", "user_consents", "alembic_version"}.intersection(public_tables)

        # Verify revision and foreign key constraints inside isolated schema
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"

            # user_consents.user_id -> RESTRICT
            consent_fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert consent_fk_action == "RESTRICT"

            # user_profiles.user_id -> CASCADE
            profile_fk_action = get_pg_foreign_key_ondelete(
                conn, "user_profiles", "user_profiles_user_id_fkey", schema_name=test_schema
            )
            assert profile_fk_action == "CASCADE"

    engine.dispose()


def test_alembic_upgrade_from_previous_revision_and_downgrade(monkeypatch):
    """
    Validates existing database upgrade path inside an isolated PostgreSQL schema:
    1. Upgrade to previous revision d60b841ec91c (constraint had CASCADE).
    2. Upgrade to new revision bb1bf3e30acc (constraint altered to RESTRICT).
    3. Downgrade back to d60b841ec91c (constraint restored to CASCADE).
    4. Re-upgrade back to bb1bf3e30acc (constraint restored to RESTRICT).
    5. Clean teardown dropping only the ephemeral test schema.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    validate_migration_test_target(MIGRATION_TEST_DB_URL, settings.DATABASE_URL)
    engine = create_engine(MIGRATION_TEST_DB_URL)

    with isolated_test_schema(engine, prefix="migtest_cycle") as test_schema:
        alembic_cfg = configure_alembic_for_schema(MIGRATION_TEST_DB_URL, test_schema)

        # Step 1: Upgrade to previous revision d60b841ec91c
        command.upgrade(alembic_cfg, "d60b841ec91c")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "d60b841ec91c"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "CASCADE"

        # Step 2: Apply new migration to head (bb1bf3e30acc)
        command.upgrade(alembic_cfg, "bb1bf3e30acc")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "RESTRICT"

        # Step 3: Downgrade back to d60b841ec91c
        command.downgrade(alembic_cfg, "d60b841ec91c")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "d60b841ec91c"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "CASCADE"

        # Step 4: Re-upgrade back to head
        command.upgrade(alembic_cfg, "head")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "RESTRICT"

    engine.dispose()
