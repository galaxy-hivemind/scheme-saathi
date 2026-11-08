"""
Integration tests for PostgreSQL database target safety guards (app.core.db_safety).
Validates driver scheme detection, hostname/IP alias resolution, cluster/database identity checks,
permission error handling, opt-in enforcement, and partial setup failure handling.
"""
from pathlib import Path
import os
import subprocess
import sys
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.db_safety import (
    validate_database_target,
    inspect_database_identity,
    normalize_db_url,
    resolve_host_ips,
    DatabaseIdentity,
    REGULAR_TEST_OPT_IN_VARS,
    MIGRATION_TEST_OPT_IN_VARS,
)
from tests.conftest import TEST_DATABASE_URL
from tests.integration.test_migrations import (
    managed_control_schema,
    MIGRATION_TEST_DB_URL,
)


# ── Explicit Opt-In Enforcement Tests ─────────────────────────────────────────

def test_running_without_opt_in_fails(monkeypatch):
    """Verify that destructive operations on test databases are rejected when opt-in is absent."""
    for var in REGULAR_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(PermissionError, match="explicit opt-in required"):
        validate_database_target(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            target_label="regular test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


def test_setting_explicit_opt_in_allows_valid_disposable_test_db(monkeypatch):
    """Verify that explicitly setting ALLOW_TEST_DB_RESET=1 permits execution on a valid disposable test database."""
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    validate_database_target(
        target_url=TEST_DATABASE_URL,
        app_url=settings.DATABASE_URL,
        target_label="regular test database",
        enforce_opt_in=True,
        opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
    )


def test_opt_in_not_automatically_inserted_into_environ():
    """
    Verify that importing conftest or db_safety does NOT automatically set or inject
    opt-in variables into os.environ.
    """
    backend_dir = Path(__file__).resolve().parent.parent.parent
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("ALLOW_")}
    clean_env["PYTHONPATH"] = str(backend_dir)
    cmd = [
        sys.executable,
        "-c",
        (
            "import os; "
            "assert 'ALLOW_TEST_DB_RESET' not in os.environ, 'Already in environ'; "
            "import tests.conftest; "
            "assert 'ALLOW_TEST_DB_RESET' not in os.environ, 'conftest automatically set ALLOW_TEST_DB_RESET'; "
            "assert 'ALLOW_DESTRUCTIVE_TESTS' not in os.environ, 'conftest set ALLOW_DESTRUCTIVE_TESTS'; "
            "assert 'ALLOW_TEST_DB_WIPE' not in os.environ, 'conftest set ALLOW_TEST_DB_WIPE';"
        ),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=backend_dir, env=clean_env)
    assert res.returncode == 0, f"Opt-in was automatically inserted into environ: {res.stderr}"


def test_migration_opt_in_alone_does_not_authorize_regular_test_db(monkeypatch):
    """
    Verify that setting migration-test opt-in (ALLOW_MIGRATION_TESTS) alone
    does NOT authorize regular test database resets.
    """
    for var in REGULAR_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    with pytest.raises(PermissionError, match="explicit opt-in required"):
        validate_database_target(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            target_label="regular test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


def test_regular_test_opt_in_alone_does_not_authorize_migration_tests(monkeypatch):
    """
    Verify that setting regular-test opt-in (ALLOW_TEST_DB_RESET) alone
    does NOT authorize migration tests.
    """
    for var in MIGRATION_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    with pytest.raises(PermissionError, match="explicit opt-in required"):
        validate_database_target(
            target_url=MIGRATION_TEST_DB_URL,
            app_url=settings.DATABASE_URL,
            target_label="migration test database",
            enforce_opt_in=True,
            opt_in_env_vars=MIGRATION_TEST_OPT_IN_VARS,
        )


def test_configured_app_database_is_still_rejected_with_all_opt_ins(monkeypatch):
    """
    Verify that even with all opt-in environment variables set, targeting the configured
    application database is strictly rejected.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
        validate_database_target(
            target_url=settings.DATABASE_URL,
            app_url=settings.DATABASE_URL,
            target_label="regular test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


def test_safety_guard_rejects_empty_target_url(monkeypatch):
    """Verify that an empty target URL raises ValueError."""
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    with pytest.raises(ValueError, match="Database URL cannot be empty"):
        validate_database_target(
            target_url="",
            app_url=settings.DATABASE_URL,
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


# ── Driver Scheme Equivalency Tests ───────────────────────────────────────────

@pytest.mark.parametrize(
    "driver_scheme",
    [
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
        "postgresql+asyncpg",
        "postgres",
    ],
)
def test_safety_guard_rejects_different_driver_schemes_for_app_db(monkeypatch, driver_scheme):
    """
    Verify that pointing to the application database using various PostgreSQL driver schemes
    (postgresql://, postgresql+psycopg://, postgresql+psycopg2://, etc.) is detected and rejected.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database
    app_host = app_parsed.host or "localhost"
    app_port = app_parsed.port or 5432

    test_url = f"{driver_scheme}://postgres:postgres@{app_host}:{app_port}/{app_db}"

    with pytest.raises(ValueError, match="Target URL points to the active application database|matches the active application database"):
        validate_database_target(
            target_url=test_url,
            app_url=settings.DATABASE_URL,
            target_label="test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


# ── Hostname & IP Alias Resolution Tests ──────────────────────────────────────

@pytest.mark.parametrize(
    "host_alias",
    [
        "127.0.0.1",
        "localhost",
        "0.0.0.0",
        "LOCALHOST",
    ],
)
def test_safety_guard_rejects_hostname_ip_aliases(monkeypatch, host_alias):
    """
    Verify that loopback aliases (127.0.0.1, localhost, 0.0.0.0) targeting the application
    database are resolved to common network identity and rejected.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database
    app_port = app_parsed.port or 5432

    alias_url = f"postgresql://postgres:postgres@{host_alias}:{app_port}/{app_db}"

    with pytest.raises(ValueError, match="Target URL points to the active application database|matches the active application database"):
        validate_database_target(
            target_url=alias_url,
            app_url=settings.DATABASE_URL,
            target_label="test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


def test_safety_guard_rejects_same_dbname_port_with_resolved_host_overlap(monkeypatch):
    """
    Verify that when the database name, port, and resolved host IPs match the application database,
    the target is rejected.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database
    app_port = app_parsed.port or 5432

    # Using 127.0.0.1 with query param
    target_url = f"postgresql+psycopg://postgres:postgres@127.0.0.1:{app_port}/{app_db}?sslmode=prefer"

    with pytest.raises(ValueError, match="Target URL points to the active application database|matches the active application database"):
        validate_database_target(
            target_url=target_url,
            app_url=settings.DATABASE_URL,
            target_label="test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


# ── Identity Verification & Ambiguity Handling Tests ──────────────────────────

def test_safety_guard_identity_verification_handles_permission_limitations():
    """
    Verify that inspect_database_identity distinguishes catalog permission limitations
    without failing or claiming cluster verification succeeded.
    """
    ident = inspect_database_identity(MIGRATION_TEST_DB_URL)
    assert ident.is_connected is True
    assert ident.current_database == "scheme_saathi_migration_test"
    assert ident.connection_error is None or "permission" in str(ident.connection_error).lower()


def test_safety_guard_fails_closed_when_app_db_unreachable_and_target_ambiguous(monkeypatch):
    """
    Verify that when the target has the same database name as application database,
    and application database connectivity fails, the safety guard fails closed rather than
    silently assuming the target is safe.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database

    target_url = f"postgresql://postgres:postgres@localhost:5432/{app_db}"
    # Offline app URL on unreachable port
    offline_app_url = f"postgresql://postgres:postgres@localhost:54329/{app_db}"

    with pytest.raises(ValueError, match=r"Cannot prove physical separation\. Failing closed"):
        validate_database_target(
            target_url=target_url,
            app_url=offline_app_url,
            target_label="test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


def test_safety_guard_fails_closed_when_test_db_cannot_connect(monkeypatch):
    """Verify that if the target test database cannot be connected to, the guard fails closed."""
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    unreachable_test_url = "postgresql://postgres:postgres@localhost:54329/nonexistent_db"

    with pytest.raises(RuntimeError, match="Cannot verify.*safety: connection to target failed"):
        validate_database_target(
            target_url=unreachable_test_url,
            app_url=settings.DATABASE_URL,
            target_label="test database",
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )


def test_safety_guard_accepts_valid_isolated_test_database(monkeypatch):
    """
    Verify that a properly provisioned disposable test database passes all checks:
    - scheme_saathi_test or scheme_saathi_migration_test
    - Opt-in enabled
    - Distinct from application database
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    validate_database_target(
        target_url=TEST_DATABASE_URL,
        app_url=settings.DATABASE_URL,
        target_label="test database",
        enforce_opt_in=True,
        opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
    )


# ── Partial Control Schema Setup Failure & Teardown Safety ────────────────────

def test_control_schema_partial_setup_failure_and_cleanup():
    """
    Requirement 4 & Section 3:
    Proves that when an error occurs during control schema setup (e.g. after schema
    creation, but during table or data initialization), the cleanup structure guarantees
    the schema is dropped and the original exception is preserved.
    """
    engine = create_engine(MIGRATION_TEST_DB_URL)
    created_schema_name = None

    class CustomSetupError(Exception):
        pass

    try:
        with pytest.raises(CustomSetupError, match="Simulated table creation failure"):
            with managed_control_schema(engine, prefix="control_fail") as schema_name:
                created_schema_name = schema_name

                # Schema was created
                with engine.connect() as conn:
                    exists = conn.execute(
                        text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                        {"s": schema_name},
                    ).scalar()
                    assert exists is True

                # Simulate partial setup failure (e.g. during DDL or insert)
                raise CustomSetupError("Simulated table creation failure")
    finally:
        # Verify that schema was dropped cleanly despite the setup failure
        if created_schema_name:
            with engine.connect() as conn:
                exists_post = conn.execute(
                    text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                    {"s": created_schema_name},
                ).scalar()
                assert exists_post is False, f"Schema {created_schema_name} was not cleaned up!"
        engine.dispose()
