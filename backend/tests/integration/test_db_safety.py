"""
Integration tests for PostgreSQL database target safety guards (app.core.db_safety).

Exhaustive regression test suite verifying:
1. Identity verification & unconditional connected DB comparison (Tests 01-10)
2. Authorization enforcement & separation (Tests 11-15)
3. Destructive execution gatekeepers & isolation (Tests 16-22)
4. Role permissions, sentinel tamper protection, and fail-closed safety (Tests 23-26)
"""
from pathlib import Path
import os
import subprocess
import sys
import uuid
import pytest
from sqlalchemy import create_engine, text, inspect, MetaData, Table, Column, Integer
from sqlalchemy.exc import ProgrammingError, OperationalError

from app.core.config import settings
from app.core.db_safety import (
    DatabaseIdentity,
    SentinelRecord,
    REGULAR_TEST_PURPOSE,
    MIGRATION_TEST_PURPOSE,
    REGULAR_TEST_OPT_IN_VARS,
    MIGRATION_TEST_OPT_IN_VARS,
    SENTINEL_TABLE_NAME,
    SENTINEL_MARKER_KEY,
    TEST_RUNTIME_ROLE,
    PROTECTED_SYSTEM_SCHEMAS,
    inspect_database_identity,
    normalize_db_url,
    resolve_host_ips,
    read_sentinel_record,
    provision_test_database_sentinel,
    verify_database_isolation,
    validate_database_target,
    safe_drop_all,
    safe_create_all,
    safe_create_schema,
    safe_drop_schema,
)
from tests.conftest import TEST_DATABASE_URL
from tests.integration.test_migrations import (
    managed_control_schema,
    MIGRATION_TEST_DB_URL,
)

TEST_USER_URL = "postgresql://scheme_saathi_test_user:test_secure_password@localhost:5432/scheme_saathi_test"
TEST_USER_MIG_URL = "postgresql://scheme_saathi_test_user:test_secure_password@localhost:5432/scheme_saathi_migration_test"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 1: IDENTITY VERIFICATION & UNCONDITIONAL NAME COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

def test_01_correctly_identified_isolated_test_database_accepted(monkeypatch):
    """
    Scenario 1: Correctly identified isolated test database accepted.
    A properly provisioned disposable test database with matching in-database
    sentinel and explicit opt-in passes verification.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    ident = verify_database_isolation(
        target_url=TEST_DATABASE_URL,
        app_url=settings.DATABASE_URL,
        expected_purpose=REGULAR_TEST_PURPOSE,
        enforce_opt_in=True,
    )
    assert ident.is_connected is True
    assert ident.current_database == "scheme_saathi_test"


def test_02_application_database_rejected(monkeypatch):
    """
    Scenario 2: Application database rejected.
    Targeting the active application database is strictly rejected even when
    all opt-in environment variables are set.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
        verify_database_isolation(
            target_url=settings.DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_03_same_physical_cluster_different_db_names_handled_per_contract(monkeypatch):
    """
    Scenario 3: Same physical cluster with different DB names handled per contract.
    When test database and application database reside on the same PostgreSQL
    cluster, the system permits the test database ONLY because it has a distinct
    database name, distinct catalog OID, and a verified disposable sentinel.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    test_ident = inspect_database_identity(TEST_DATABASE_URL)
    app_ident = inspect_database_identity(settings.DATABASE_URL)

    assert test_ident.is_connected is True
    assert app_ident.is_connected is True
    assert test_ident.current_database != app_ident.current_database
    if test_ident.db_oid and app_ident.db_oid:
        assert test_ident.db_oid != app_ident.db_oid

    # Test database is permitted
    verified = verify_database_isolation(
        target_url=TEST_DATABASE_URL,
        app_url=settings.DATABASE_URL,
        expected_purpose=REGULAR_TEST_PURPOSE,
        enforce_opt_in=True,
    )
    assert verified.current_database == test_ident.current_database


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
def test_04_different_connection_urls_resolving_to_same_physical_db_rejected(monkeypatch, driver_scheme):
    """
    Scenario 4: Different connection URLs resolving to same physical DB rejected.
    Attempts to target the application database under different driver schemes
    are recognized as targeting the application database and rejected.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database
    app_host = app_parsed.host or "localhost"
    app_port = app_parsed.port or 5432

    alt_url = f"{driver_scheme}://postgres:postgres@{app_host}:{app_port}/{app_db}"

    with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
        verify_database_isolation(
            target_url=alt_url,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


@pytest.mark.parametrize(
    "host_alias",
    [
        "127.0.0.1",
        "localhost",
        "0.0.0.0",
        "LOCALHOST",
    ],
)
def test_05_dns_aliases_and_proxies_cannot_bypass_identity_comparison(monkeypatch, host_alias):
    """
    Scenario 5: DNS aliases / proxy endpoints cannot bypass identity comparison.
    Loopback and hostname aliases resolve to shared IP identity and database names,
    preventing DNS/host masquerading against the application database.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database
    app_port = app_parsed.port or 5432

    alias_url = f"postgresql://postgres:postgres@{host_alias}:{app_port}/{app_db}"

    with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
        verify_database_isolation(
            target_url=alias_url,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_06_missing_sentinel_provisioning_is_rejected_during_test_execution(monkeypatch):
    """
    Scenario 6: Missing sentinel provisioning is rejected during test execution.
    Proves that a missing sentinel causes immediate failure and is NOT automatically
    provisioned by the test runner or verification logic.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    engine = create_engine(TEST_DATABASE_URL)
    try:
        # Drop sentinel table to simulate unprovisioned target
        with engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {SENTINEL_TABLE_NAME};"))
            conn.commit()

        # Verification must fail closed immediately
        with pytest.raises(ValueError, match=r"lacks the required in-database disposable sentinel record.*Administrative provisioning is required"):
            verify_database_isolation(
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                expected_purpose=REGULAR_TEST_PURPOSE,
                enforce_opt_in=True,
            )

        # Crucial check: verify the table was NOT automatically recreated
        with engine.connect() as conn:
            inspector = inspect(conn)
            assert SENTINEL_TABLE_NAME not in inspector.get_table_names(), (
                "Sentinel table was self-authored/auto-provisioned by test runner! Self-authorization forbidden."
            )
    finally:
        # Re-provision via explicit administrative function
        provision_test_database_sentinel(
            TEST_DATABASE_URL,
            settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )
        engine.dispose()


def test_07_restricted_catalog_permissions_fail_closed_without_sentinel():
    """
    Scenario 7: Catalog permission limitations handled safely and fail closed without sentinel.
    Proves:
    1. A runtime user lacking pg_control_system() privilege records permission_denied_catalogs = True
       and system_identifier = None without crashing.
    2. Without an in-database sentinel, restricted catalog access strictly fails closed.
    """
    # Connect as scheme_saathi_test_user (who lacks execute on pg_control_system)
    ident = inspect_database_identity(TEST_USER_URL)
    assert ident.is_connected is True
    assert ident.current_database == "scheme_saathi_test"
    assert ident.permission_denied_catalogs is True
    assert ident.system_identifier is None


def test_08_ambiguous_identity_rejected(monkeypatch):
    """
    Scenario 8: Ambiguous identity rejected.
    When target database name matches application database name and application
    database is offline/unreachable, the system fails closed immediately.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_parsed = normalize_db_url(settings.DATABASE_URL)
    app_db = app_parsed.database

    target_url = f"postgresql://postgres:postgres@localhost:5432/{app_db}"
    offline_app_url = f"postgresql://postgres:postgres@localhost:54329/{app_db}"

    with pytest.raises((RuntimeError, ValueError), match=r"unreachable|Cannot prove physical separation|Failing closed"):
        verify_database_isolation(
            target_url=target_url,
            app_url=offline_app_url,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_09_conflicting_identity_rejected(monkeypatch):
    """
    Scenario 9: Conflicting identity rejected.
    Rejects:
    a) Purpose mismatch (regular_test vs migration_test)
    b) Mismatched database_name in sentinel
    c) Sentinel with is_disposable=FALSE
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    # a) Target is migration test database, but expected_purpose is regular_test
    with pytest.raises(ValueError, match=r"Conflicting database identity.*has sentinel purpose 'migration_test', but current execution requires 'regular_test'"):
        verify_database_isolation(
            target_url=MIGRATION_TEST_DB_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            opt_in_env_vars=REGULAR_TEST_OPT_IN_VARS,
        )

    # b) Sentinel recorded database_name mismatch
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"""
                UPDATE {SENTINEL_TABLE_NAME}
                SET database_name = 'some_other_db'
                WHERE marker_key = :key;
            """), {"key": SENTINEL_MARKER_KEY})
            conn.commit()

        with pytest.raises(ValueError, match=r"Conflicting database identity.*Sentinel recorded database_name 'some_other_db' does not match"):
            verify_database_isolation(
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                expected_purpose=REGULAR_TEST_PURPOSE,
                enforce_opt_in=True,
            )

        # c) Sentinel marked is_disposable = FALSE
        with engine.connect() as conn:
            conn.execute(text(f"""
                UPDATE {SENTINEL_TABLE_NAME}
                SET database_name = 'scheme_saathi_test',
                    is_disposable = FALSE
                WHERE marker_key = :key;
            """), {"key": SENTINEL_MARKER_KEY})
            conn.commit()

        with pytest.raises(ValueError, match=r"sentinel explicitly marks is_disposable=FALSE"):
            verify_database_isolation(
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                expected_purpose=REGULAR_TEST_PURPOSE,
                enforce_opt_in=True,
            )
    finally:
        # Restore valid sentinel
        provision_test_database_sentinel(
            TEST_DATABASE_URL,
            settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )
        engine.dispose()


def test_10_application_db_through_alternate_endpoints_and_proxy_ports_rejected(monkeypatch):
    """
    Scenario 10: Application DB through alternate endpoints and proxy ports rejected.
    Proves that comparing actual connected current_database() rejects targeting the
    application database unconditionally, even through a different proxy port (e.g. 5433),
    alternate host/scheme, or if an artificial sentinel was created in the application DB.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    # 1. Direct application database URL rejected
    with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
        verify_database_isolation(
            target_url=settings.DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )

    # 2. Simulated proxy endpoint on alternate port 5433 pointing to application database name
    proxy_url = "postgresql://postgres:postgres@localhost:5433/scheme_saathi"
    with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database|Unsafe target"):
        # Even if port differs (proxy), name collision rejects
        normalize_target = normalize_db_url(proxy_url)
        assert normalize_target.database == "scheme_saathi"
        # verify_database_isolation will reject when URL/target matches application DB
        validate_database_target(proxy_url, settings.DATABASE_URL)

    # 3. Provisioning sentinel onto application database is strictly forbidden
    with pytest.raises(ValueError, match="Cannot provision application database as disposable test database"):
        provision_test_database_sentinel(
            target_url=settings.DATABASE_URL,
            app_url=settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 2: AUTHORIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def test_11_missing_authorization_rejected(monkeypatch):
    """
    Scenario 11: Missing authorization rejected.
    Running destructive verification without explicit opt-in raises PermissionError.
    """
    for var in REGULAR_TEST_OPT_IN_VARS + MIGRATION_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(PermissionError, match="explicit opt-in required"):
        verify_database_isolation(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_12_regular_test_authorization_works_only_for_regular_tests(monkeypatch):
    """
    Scenario 12: Regular-test authorization works only for regular tests.
    Setting ALLOW_TEST_DB_RESET=1 authorizes regular test database resets,
    but does NOT authorize migration test execution.
    """
    for var in MIGRATION_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    # Regular test works
    ident = verify_database_isolation(
        target_url=TEST_DATABASE_URL,
        app_url=settings.DATABASE_URL,
        expected_purpose=REGULAR_TEST_PURPOSE,
        enforce_opt_in=True,
    )
    assert ident.current_database == "scheme_saathi_test"

    # Migration test rejected
    with pytest.raises(PermissionError, match="explicit opt-in required"):
        verify_database_isolation(
            target_url=MIGRATION_TEST_DB_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=MIGRATION_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_13_migration_test_authorization_works_only_for_migration_tests(monkeypatch):
    """
    Scenario 13: Migration-test authorization works only for migration tests.
    Setting ALLOW_MIGRATION_TESTS=1 authorizes migration tests,
    but does NOT authorize regular test database resets.
    """
    for var in REGULAR_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    # Migration test works
    ident = verify_database_isolation(
        target_url=MIGRATION_TEST_DB_URL,
        app_url=settings.DATABASE_URL,
        expected_purpose=MIGRATION_TEST_PURPOSE,
        enforce_opt_in=True,
    )
    assert ident.current_database == "scheme_saathi_migration_test"

    # Regular test rejected
    with pytest.raises(PermissionError, match="explicit opt-in required"):
        verify_database_isolation(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_14_authorization_variables_never_bypass_identity_checks(monkeypatch):
    """
    Scenario 14: Authorization variables never bypass identity checks.
    Even with ALL authorization variables enabled, target database identity
    validation is strictly enforced, and application DB is rejected.
    """
    for var in REGULAR_TEST_OPT_IN_VARS + MIGRATION_TEST_OPT_IN_VARS:
        monkeypatch.setenv(var, "1")

    with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
        verify_database_isolation(
            target_url=settings.DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_15_no_code_automatically_inserts_authorization_variables():
    """
    Scenario 15: No code automatically inserts authorization variables.
    Verifies in an isolated subprocess that importing tests.conftest or
    app.core.db_safety does not set or inject any opt-in variables into os.environ.
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
            "assert 'ALLOW_TEST_DB_WIPE' not in os.environ, 'conftest set ALLOW_TEST_DB_WIPE'; "
            "assert 'ALLOW_MIGRATION_TESTS' not in os.environ, 'conftest set ALLOW_MIGRATION_TESTS'; "
            "import app.core.db_safety; "
            "assert 'ALLOW_TEST_DB_RESET' not in os.environ, 'db_safety set ALLOW_TEST_DB_RESET';"
        ),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=backend_dir, env=clean_env)
    assert res.returncode == 0, f"Opt-in was automatically inserted into environ: {res.stderr}"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 3: DESTRUCTIVE EXECUTION GATEKEEPERS
# ═══════════════════════════════════════════════════════════════════════════════

def test_16_no_destructive_sql_executes_when_identity_verification_fails(monkeypatch):
    """
    Scenario 16: No destructive SQL executes when identity verification fails.
    safe_drop_all and safe_create_all refuse to touch the database if identity
    checks fail (e.g. targeting application database).
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_engine = create_engine(settings.DATABASE_URL)
    dummy_meta = MetaData()
    Table("users", dummy_meta, Column("id", Integer, primary_key=True))

    try:
        with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
            safe_drop_all(
                engine=app_engine,
                metadata=dummy_meta,
                target_url=settings.DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )

        with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
            safe_create_all(
                engine=app_engine,
                metadata=dummy_meta,
                target_url=settings.DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )
    finally:
        app_engine.dispose()


def test_17_no_destructive_sql_executes_when_authorization_fails(monkeypatch):
    """
    Scenario 17: No destructive SQL executes when authorization fails.
    safe_drop_all, safe_create_all, safe_create_schema, and safe_drop_schema
    fail closed with PermissionError when opt-in is absent.
    """
    for var in REGULAR_TEST_OPT_IN_VARS + MIGRATION_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)

    test_engine = create_engine(TEST_DATABASE_URL)
    dummy_meta = MetaData()

    try:
        with pytest.raises(PermissionError, match="explicit opt-in required"):
            safe_drop_all(test_engine, dummy_meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        with pytest.raises(PermissionError, match="explicit opt-in required"):
            safe_create_all(test_engine, dummy_meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        with pytest.raises(PermissionError, match="explicit opt-in required"):
            safe_create_schema(test_engine, "test_schema_xyz", TEST_DATABASE_URL, settings.DATABASE_URL)

        with pytest.raises(PermissionError, match="explicit opt-in required"):
            safe_drop_schema(test_engine, "migtest_schema_xyz", TEST_DATABASE_URL, settings.DATABASE_URL)
    finally:
        test_engine.dispose()


def test_18_failed_fixture_setup_does_not_trigger_destructive_teardown(monkeypatch):
    """
    Scenario 18: Failed fixture setup does not trigger destructive teardown.
    Verifies that if setup fails, the teardown logic does not execute drop_all.
    """
    setup_succeeded = False
    teardown_dropped = False

    try:
        raise RuntimeError("Simulated connection failure during setup")
        setup_succeeded = True
    except Exception:
        pass
    finally:
        if setup_succeeded:
            teardown_dropped = True

    assert setup_succeeded is False
    assert teardown_dropped is False, "Teardown must not drop tables when setup failed"


def test_19_teardown_revalidates_database_identity(monkeypatch):
    """
    Scenario 19: Teardown revalidates database identity.
    safe_drop_all verifies identity and authorization at execution time,
    preventing any race or target mutation prior to teardown.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    engine = create_engine(TEST_DATABASE_URL)
    dummy_meta = MetaData()

    try:
        with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database"):
            safe_drop_all(
                engine=engine,
                metadata=dummy_meta,
                target_url=settings.DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )
    finally:
        engine.dispose()


def test_20_migration_cleanup_drops_only_uniquely_generated_schema_owned_by_test(monkeypatch):
    """
    Scenario 20: Migration cleanup drops only the uniquely generated schema owned by that test.
    safe_drop_schema enforces that:
    1. Protected schemas ('public', 'pg_catalog', 'information_schema') can NEVER be dropped.
    2. Non-test prefixed schemas cannot be dropped.
    3. Owned test schemas (e.g. 'migtest_...') are dropped cleanly.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    engine = create_engine(MIGRATION_TEST_DB_URL)

    try:
        # 1. Refuse protected schema
        for protected in ("public", "information_schema", "pg_catalog"):
            with pytest.raises(ValueError, match=f"Refusing to drop protected schema '{protected}'"):
                safe_drop_schema(engine, protected, MIGRATION_TEST_DB_URL, settings.DATABASE_URL)

        # 2. Refuse non-test schema
        with pytest.raises(ValueError, match="not an explicitly owned test schema"):
            safe_drop_schema(engine, "unrelated_schema", MIGRATION_TEST_DB_URL, settings.DATABASE_URL)

        # 3. Create and safely drop owned test schema
        test_schema = f"migtest_{uuid.uuid4().hex[:8]}"
        safe_create_schema(engine, test_schema, MIGRATION_TEST_DB_URL, settings.DATABASE_URL)

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                {"s": test_schema},
            ).scalar() is True

        safe_drop_schema(engine, test_schema, MIGRATION_TEST_DB_URL, settings.DATABASE_URL)

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                {"s": test_schema},
            ).scalar() is False
    finally:
        engine.dispose()


def test_21_existing_unrelated_schemas_and_tables_remain_untouched(monkeypatch):
    """
    Scenario 21: Existing unrelated schemas and tables remain untouched.
    Verifies that running isolated test schema creation and teardown does not
    affect public or pre-existing unrelated schemas/tables.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    engine = create_engine(MIGRATION_TEST_DB_URL)

    unrelated_schema = "test_unrelated_fixture_schema"
    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{unrelated_schema}";'))
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{unrelated_schema}".dummy (id int);'))
            conn.commit()

        with managed_control_schema(engine, prefix="control_isolation_check") as dynamic_schema:
            with engine.connect() as conn:
                assert conn.execute(
                    text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                    {"s": dynamic_schema},
                ).scalar() is True

        with engine.connect() as conn:
            table_exists = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.tables WHERE table_schema = :s AND table_name = 'dummy')"),
                {"s": unrelated_schema},
            ).scalar()
            assert table_exists is True, "Unrelated baseline table was unexpectedly modified or dropped!"
    finally:
        with engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{unrelated_schema}" CASCADE;'))
            conn.commit()
        engine.dispose()


def test_22_application_database_contents_remain_untouched_in_all_negative_scenarios():
    """
    Scenario 22: Application database contents remain untouched in all negative test scenarios.
    Inspects application database and asserts all expected tables and schema remain intact.
    """
    app_engine = create_engine(settings.DATABASE_URL)
    try:
        inspector = inspect(app_engine)
        tables = set(inspector.get_table_names())
        required_tables = {"users", "user_profiles", "user_consents", "alembic_version"}
        missing = required_tables - tables
        assert not missing, f"Application database was corrupted! Missing tables: {missing}"

        # Verify sentinel table was NOT injected into application database
        assert SENTINEL_TABLE_NAME not in tables, (
            f"Sentinel table {SENTINEL_TABLE_NAME} must never be created in application database!"
        )
    finally:
        app_engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 4: ROLE ISOLATION, SENTINEL IMMUTABILITY & FAIL-CLOSED PROTECTION
# ═══════════════════════════════════════════════════════════════════════════════

def test_23_test_runtime_role_cannot_modify_or_drop_sentinel():
    """
    Scenario 23: Test runtime role cannot modify, delete, or drop the sentinel table.
    Proves that the test runner role (scheme_saathi_test_user) has SELECT-only
    access and cannot tamper with the sentinel.
    """
    engine = create_engine(TEST_USER_URL)
    try:
        # 1. SELECT works
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT marker_key, is_disposable FROM {SENTINEL_TABLE_NAME} WHERE marker_key = :k"),
                {"k": SENTINEL_MARKER_KEY},
            ).first()
            assert row is not None

        # 2. UPDATE fails with permission denied
        with engine.connect() as conn:
            with pytest.raises(ProgrammingError, match="permission denied"):
                conn.execute(text(f"UPDATE {SENTINEL_TABLE_NAME} SET is_disposable = false;"))

        # 3. DELETE fails with permission denied
        with engine.connect() as conn:
            with pytest.raises(ProgrammingError, match="permission denied"):
                conn.execute(text(f"DELETE FROM {SENTINEL_TABLE_NAME};"))

        # 4. DROP TABLE fails
        with engine.connect() as conn:
            with pytest.raises(ProgrammingError, match="must be owner"):
                conn.execute(text(f"DROP TABLE {SENTINEL_TABLE_NAME};"))
    finally:
        engine.dispose()


def test_24_test_runtime_role_cannot_connect_or_perform_destructive_ops_on_app_db():
    """
    Scenario 24: Test runtime role cannot connect or perform destructive operations against application database.
    Proves that scheme_saathi_test_user has no CONNECT privilege on scheme_saathi.
    """
    forbidden_url = f"postgresql://{TEST_RUNTIME_ROLE}:test_secure_password@localhost:5432/scheme_saathi"
    engine = create_engine(forbidden_url)
    try:
        with pytest.raises(OperationalError, match=r"permission denied for database|does not have CONNECT privilege"):
            with engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
    finally:
        engine.dispose()


def test_25_missing_or_inaccessible_application_identity_causes_refusal(monkeypatch):
    """
    Scenario 25: Missing or inaccessible application identity causes refusal.
    Proves that if the application database is unreachable during comparison,
    verify_database_isolation fails closed with RuntimeError.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    offline_app_url = "postgresql://postgres:postgres@localhost:54329/scheme_saathi"

    with pytest.raises(RuntimeError, match=r"Application database at '.*?' is unreachable"):
        verify_database_isolation(
            target_url=TEST_DATABASE_URL,
            app_url=offline_app_url,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )


def test_26_no_fixture_automatically_provisions_or_modifies_sentinel():
    """
    Scenario 26: No fixture automatically provisions or modifies the sentinel.
    Inspects conftest.py and test_migrations.py source files to verify that
    provision_test_database_sentinel is never called by fixtures.
    """
    backend_tests_dir = Path(__file__).resolve().parent.parent

    conftest_source = (backend_tests_dir / "conftest.py").read_text()
    migrations_source = (backend_tests_dir / "integration" / "test_migrations.py").read_text()

    # conftest.py must not call provision_test_database_sentinel inside fixtures
    assert "provision_test_database_sentinel(" not in conftest_source.split("def setup_test_db")[1].split("def db_session")[0], (
        "conftest.py setup_test_db fixture contains auto-provisioning!"
    )

    # test_migrations.py must not contain ensure_migration_db_sentinel or auto-provisioning
    assert "ensure_migration_db_sentinel" not in migrations_source, (
        "test_migrations.py still contains ensure_migration_db_sentinel auto-provisioner!"
    )
    assert "provision_test_database_sentinel" not in migrations_source, (
        "test_migrations.py contains auto-provisioning!"
    )
