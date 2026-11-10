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
from app.core.db_safety import (
    verify_database_isolation,
    validate_database_target,
    normalize_db_url,
    safe_create_schema,
    safe_drop_schema,
    MIGRATION_TEST_PURPOSE,
    MIGRATION_TEST_OPT_IN_VARS,
    TEST_RUNTIME_ROLE,
    ADMIN_ROLES,
)

TEST_DB_USER = os.getenv("TEST_DB_USER", TEST_RUNTIME_ROLE)
TEST_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
TEST_DB_PORT = os.getenv("TEST_DB_PORT", "5432")
MIGRATION_DB_NAME = os.getenv("MIGRATION_DB_NAME", "scheme_saathi_migration_test")


def get_migration_test_db_url() -> str:
    """
    Return the active migration test database URL.
    Requires explicit TEST_DB_PASSWORD in fallback mode. Never uses hardcoded or placeholder passwords.
    """
    explicit_url = os.getenv("MIGRATION_TEST_DB_URL")
    if explicit_url:
        parsed = normalize_db_url(explicit_url)
        pwd = parsed.password
        if not pwd or not pwd.strip() or pwd.strip() in ("placeholder", "password"):
            raise ValueError(
                "MIGRATION_TEST_DB_URL was provided without valid credentials. "
                "An explicit, non-placeholder password is required for migration test fallback execution."
            )
        return explicit_url

    pwd = os.getenv("TEST_DB_PASSWORD")
    if not pwd or not pwd.strip() or pwd.strip() in ("placeholder", "password"):
        raise ValueError(
            "Missing required migration test database credentials: TEST_DB_PASSWORD must be "
            "explicitly configured in the environment for migration fallback execution. "
            "Example: TEST_DB_PASSWORD=<password> ALLOW_MIGRATION_TESTS=1 pytest tests/integration/test_migrations.py -v"
        )

    from urllib.parse import quote_plus
    safe_pwd = quote_plus(pwd.strip())
    return f"postgresql://{TEST_DB_USER}:{safe_pwd}@{TEST_DB_HOST}:{TEST_DB_PORT}/{MIGRATION_DB_NAME}"


def __getattr__(name: str):
    """Provide lazy access to module-level properties so unit tests never trigger eager DB setup."""
    if name == "MIGRATION_TEST_DB_URL":
        return get_migration_test_db_url()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def validate_migration_test_target(
    test_url: str,
    app_url: str,
    enforce_opt_in: bool = True,
    expected_role: str = TEST_DB_USER,
) -> None:
    """Pre-flight validation for migration test execution with mandatory restricted role enforcement."""
    verify_database_isolation(
        target_url=test_url,
        app_url=app_url,
        expected_purpose=MIGRATION_TEST_PURPOSE,
        enforce_opt_in=enforce_opt_in,
        opt_in_env_vars=MIGRATION_TEST_OPT_IN_VARS,
        expected_role=expected_role,
    )


def verify_migration_connected_role(engine, expected_role: str = TEST_DB_USER) -> None:
    """Verifies that the migration engine connects using the expected restricted runtime role."""
    with engine.connect() as conn:
        connected_user = conn.execute(text("SELECT current_user;")).scalar()
        is_super = conn.execute(text("SELECT current_setting('is_superuser');")).scalar()
    if is_super == "on" or (connected_user and connected_user.lower() in ADMIN_ROLES):
        raise PermissionError(
            f"Migration test execution with administrative/superuser role '{connected_user}' is forbidden. "
            f"Fallback execution must use the restricted runtime role '{expected_role}'."
        )
    if connected_user != expected_role:
        raise PermissionError(
            f"Expected migration fallback execution to connect as restricted role '{expected_role}', "
            f"but connected as '{connected_user}'."
        )


@contextmanager
def isolated_test_schema(engine, prefix: str = "migtest"):
    """
    Context manager providing a genuinely isolated, ephemeral PostgreSQL schema.
    Uses safe_create_schema and safe_drop_schema with restricted role enforcement.
    Never drops or modifies the public schema.
    """
    test_url = get_migration_test_db_url()
    schema_name = f"{prefix}_{uuid.uuid4().hex[:12]}"
    safe_create_schema(
        engine,
        schema_name,
        test_url,
        settings.DATABASE_URL,
        purpose=MIGRATION_TEST_PURPOSE,
        expected_role=TEST_DB_USER,
    )

    try:
        yield schema_name
    finally:
        exc_type, _, _ = sys.exc_info()
        try:
            safe_drop_schema(
                engine,
                schema_name,
                test_url,
                settings.DATABASE_URL,
                purpose=MIGRATION_TEST_PURPOSE,
                expected_role=TEST_DB_USER,
            )
        except Exception as teardown_exc:
            if exc_type is not None:
                warnings.warn(f"Teardown error dropping schema {schema_name}: {teardown_exc}", stacklevel=2)
            else:
                raise


@contextmanager
def managed_control_schema(engine, prefix: str = "control"):
    """
    Context manager that safely manages an isolated control schema.
    Uses centralized safe schema gateways with restricted role enforcement.
    """
    test_url = get_migration_test_db_url()
    schema_name = f"{prefix}_{uuid.uuid4().hex[:12]}"
    created = False
    try:
        safe_create_schema(
            engine,
            schema_name,
            test_url,
            settings.DATABASE_URL,
            purpose=MIGRATION_TEST_PURPOSE,
            expected_role=TEST_DB_USER,
        )
        created = True
        yield schema_name
    finally:
        if created:
            exc_type, _, _ = sys.exc_info()
            try:
                safe_drop_schema(
                    engine,
                    schema_name,
                    test_url,
                    settings.DATABASE_URL,
                    purpose=MIGRATION_TEST_PURPOSE,
                    expected_role=TEST_DB_USER,
                )
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
    for var in MIGRATION_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(PermissionError, match="explicit opt-in required"):
        validate_migration_test_target(
            test_url=get_migration_test_db_url(),
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
    with pytest.raises(ValueError, match="matches.*active application database|Target URL points to the active application database"):
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
    with pytest.raises(ValueError, match="matches.*active application database|Target URL points to the active application database"):
        validate_migration_test_target(
            test_url=alias_url,
            app_url=settings.DATABASE_URL,
            enforce_opt_in=True,
        )


def test_safety_guard_accepts_valid_isolated_target(monkeypatch):
    """Verify that a distinct target database with opt-in enabled and provisioned sentinel passes validation."""
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    validate_migration_test_target(
        test_url=get_migration_test_db_url(),
        app_url=settings.DATABASE_URL,
        enforce_opt_in=True,
    )


def test_teardown_preserves_original_test_failure(monkeypatch):
    """Verify that teardown cleans up the schema without masking an in-flight test assertion error."""
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    created_schema = None
    try:
        with pytest.raises(ZeroDivisionError, match="division by zero"):
            with isolated_test_schema(engine, prefix="test_fail") as schema_name:
                created_schema = schema_name
                with engine.connect() as conn:
                    exists = conn.execute(
                        text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                        {"s": schema_name},
                    ).scalar()
                    assert exists is True
                _ = 1 / 0
    finally:
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
    Requirement:
    Proves that running migrations inside an isolated schema:
    1. Leaves existing unrelated schemas and their tables 100% untouched.
    2. Leaves the public schema completely untouched (zero migration tables created in public).
    3. Guarantees that dropping the isolated schema does not affect the unrelated schema.
    4. Ensures control-schema creation, sentinel records, and testing run in an exception-safe structure.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with managed_control_schema(engine, prefix="control") as control_schema:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE TABLE "{control_schema}".sentinel_records (id INT PRIMARY KEY, name TEXT);'))
            conn.execute(text(f'INSERT INTO "{control_schema}".sentinel_records VALUES (42, \'untouched_data\');'))
            conn.commit()

        with isolated_test_schema(engine, prefix="migtest_iso") as test_schema:
            alembic_cfg = configure_alembic_for_schema(test_url, test_schema)
            command.upgrade(alembic_cfg, "head")

            inspector = inspect(engine)
            test_tables = set(inspector.get_table_names(schema=test_schema))
            assert {"users", "user_profiles", "user_consents", "alembic_version"}.issubset(test_tables)

            public_tables = set(inspector.get_table_names(schema="public"))
            assert not {"users", "user_profiles", "user_consents", "alembic_version"}.intersection(public_tables)

            control_tables = set(inspector.get_table_names(schema=control_schema))
            assert control_tables == {"sentinel_records"}

            with engine.connect() as conn:
                sentinel_val = conn.execute(
                    text(f'SELECT name FROM "{control_schema}".sentinel_records WHERE id = 42')
                ).scalar()
                assert sentinel_val == "untouched_data"

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
    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with isolated_test_schema(engine, prefix="migtest_fresh") as test_schema:
        alembic_cfg = configure_alembic_for_schema(test_url, test_schema)
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(engine)
        test_tables = set(inspector.get_table_names(schema=test_schema))
        assert {"users", "user_profiles", "user_consents", "alembic_version"}.issubset(test_tables)

        public_tables = set(inspector.get_table_names(schema="public"))
        assert not {"users", "user_profiles", "user_consents", "alembic_version"}.intersection(public_tables)

        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"

            consent_fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert consent_fk_action == "RESTRICT"

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
    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with isolated_test_schema(engine, prefix="migtest_cycle") as test_schema:
        alembic_cfg = configure_alembic_for_schema(test_url, test_schema)

        command.upgrade(alembic_cfg, "d60b841ec91c")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "d60b841ec91c"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "CASCADE"

        command.upgrade(alembic_cfg, "bb1bf3e30acc")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "RESTRICT"

        command.downgrade(alembic_cfg, "d60b841ec91c")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "d60b841ec91c"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "CASCADE"

        command.upgrade(alembic_cfg, "head")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "bb1bf3e30acc"
            fk_action = get_pg_foreign_key_ondelete(
                conn, "user_consents", "user_consents_user_id_fkey", schema_name=test_schema
            )
            assert fk_action == "RESTRICT"

    engine.dispose()
