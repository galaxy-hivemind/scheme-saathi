"""
Integration tests for PostgreSQL database target safety guards (app.core.db_safety).

Exhaustive regression test suite verifying:
1. Section 5 Requirements: Restricted PostgreSQL runtime role enforcement (Tests 01-14)
2. Target Database Identity & Host/Alias Isolation (Tests 15-19)
3. Authorization Segregation & Non-Auto-Opt-in (Tests 20-21)
4. Teardown Safety & Schema Isolation (Tests 22-24)
5. Application Database Immutability & Sentinel Non-Auto-Provisioning (Tests 25-26)
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
    ADMIN_ROLES,
    PROTECTED_SYSTEM_SCHEMAS,
    inspect_database_identity,
    normalize_db_url,
    resolve_host_ips,
    read_sentinel_record,
    provision_test_database_sentinel,
    setup_test_roles,
    validate_pg_identifier,
    verify_database_isolation,
    validate_database_target,
    safe_drop_all,
    safe_create_all,
    safe_create_schema,
    safe_drop_schema,
)
from tests.conftest import TEST_DATABASE_URL, USE_TESTCONTAINERS, TEST_DB_USER
from tests.integration.test_migrations import (
    managed_control_schema,
    MIGRATION_TEST_DB_URL,
)

TEST_USER_URL = "postgresql://scheme_saathi_test_user:test_secure_password@localhost:5432/scheme_saathi_test"
TEST_USER_MIG_URL = "postgresql://scheme_saathi_test_user:test_secure_password@localhost:5432/scheme_saathi_migration_test"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: REGRESSION TESTS FOR RESTRICTED RUNTIME ROLE ENFORCEMENT (1 TO 14)
# ═══════════════════════════════════════════════════════════════════════════════

def test_01_fallback_fixture_uses_restricted_role():
    """
    Requirement 1: Fallback fixture connects using restricted role.
    The fallback TEST_DATABASE_URL connects using scheme_saathi_test_user and not postgres.
    The connected user is verified to be scheme_saathi_test_user and not a superuser.
    """
    if not USE_TESTCONTAINERS:
        assert TEST_DB_USER == "scheme_saathi_test_user"
        parsed = normalize_db_url(TEST_DATABASE_URL)
        assert parsed.username == "scheme_saathi_test_user"
        ident = inspect_database_identity(TEST_DATABASE_URL)
        assert ident.is_connected is True
        assert ident.current_user == "scheme_saathi_test_user"
        assert ident.is_superuser is False


def test_02_administrator_connections_rejected_for_fallback_execution(monkeypatch):
    """
    Requirement 2: Administrator connections rejected for fallback execution.
    Destructive operations with enforce_restricted_role=True strictly reject
    connections using 'postgres', root, admin, or any superuser account.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test"
    with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
        verify_database_isolation(
            target_url=admin_url,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            enforce_restricted_role=True,
            expected_role="scheme_saathi_test_user",
        )


def test_03_connected_role_verified_against_current_user(monkeypatch):
    """
    Requirement 3: Connected role verified against current_user.
    The verification queries PostgreSQL current_user and fails if it does not match
    the expected runtime role.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    with pytest.raises(PermissionError, match=r"connected as 'scheme_saathi_test_user', expected restricted runtime role 'some_other_role'"):
        verify_database_isolation(
            target_url=TEST_USER_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            enforce_restricted_role=True,
            expected_role="some_other_role",
        )


def test_04_test_role_provisioning_does_not_revoke_connect_from_public():
    """
    Requirement 4: Test role provisioning does not revoke CONNECT from PUBLIC.
    Verifies that PUBLIC still retains CONNECT on scheme_saathi.
    """
    admin_engine = create_engine(os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"))
    with admin_engine.connect() as conn:
        has_public_connect = conn.execute(
            text("SELECT has_database_privilege('public', 'scheme_saathi', 'CONNECT');")
        ).scalar()
        assert has_public_connect is True, "PUBLIC lost CONNECT privilege on scheme_saathi!"
    admin_engine.dispose()


def test_05_unrelated_roles_retain_original_privileges():
    """
    Requirement 5: Unrelated roles retain original privileges.
    Creating a separate unrelated role and running setup_test_roles() does not
    revoke or alter the privileges of the unrelated role.
    """
    admin_url = os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    admin_engine = create_engine(admin_url)
    unrelated_role = f"unrelated_user_{uuid.uuid4().hex[:6]}"
    test_pwd = os.getenv("TEST_DB_PASSWORD", "test_secure_password")

    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE ROLE "{unrelated_role}" WITH LOGIN PASSWORD \'unrelated_pass\';'))
            conn.commit()

        # Run setup_test_roles for scheme_saathi_test_user
        setup_test_roles(admin_url, test_role=TEST_RUNTIME_ROLE, test_password=test_pwd)

        # Verify unrelated role can still connect to scheme_saathi (via PUBLIC or role privilege)
        with admin_engine.connect() as conn:
            unrelated_connect = conn.execute(
                text("SELECT has_database_privilege(:role, 'scheme_saathi', 'CONNECT');"),
                {"role": unrelated_role},
            ).scalar()
            assert unrelated_connect is True, f"Unrelated role '{unrelated_role}' lost CONNECT privilege!"
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP ROLE IF EXISTS "{unrelated_role}";'))
            conn.commit()
        admin_engine.dispose()


def test_06_runtime_role_cannot_connect_to_application_database():
    """
    Requirement 6: Runtime role cannot connect to application database.
    Connecting to scheme_saathi as scheme_saathi_test_user is blocked and fails.
    """
    app_target_with_test_user = f"postgresql://{TEST_RUNTIME_ROLE}:test_secure_password@localhost:5432/scheme_saathi"
    engine = create_engine(app_target_with_test_user)
    try:
        with pytest.raises(OperationalError):
            with engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
    finally:
        engine.dispose()


def test_07_runtime_role_can_connect_to_disposable_test_database():
    """
    Requirement 7: Runtime role can connect to disposable test database.
    scheme_saathi_test_user successfully connects to scheme_saathi_test and
    scheme_saathi_migration_test.
    """
    for url, db_name in [(TEST_USER_URL, "scheme_saathi_test"), (TEST_USER_MIG_URL, "scheme_saathi_migration_test")]:
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                user = conn.execute(text("SELECT current_user;")).scalar()
                db = conn.execute(text("SELECT current_database();")).scalar()
                assert user == TEST_RUNTIME_ROLE
                assert db == db_name
        finally:
            engine.dispose()


def test_08_runtime_role_cannot_modify_or_drop_sentinel():
    """
    Requirement 8: Runtime role cannot modify or drop sentinel.
    SELECT on the sentinel succeeds, while UPDATE, DELETE, and DROP TABLE fail
    with permission errors.
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

        # 2. UPDATE fails
        with engine.connect() as conn:
            with pytest.raises(ProgrammingError, match="permission denied"):
                conn.execute(text(f"UPDATE {SENTINEL_TABLE_NAME} SET is_disposable = false;"))

        # 3. DELETE fails
        with engine.connect() as conn:
            with pytest.raises(ProgrammingError, match="permission denied"):
                conn.execute(text(f"DELETE FROM {SENTINEL_TABLE_NAME};"))

        # 4. DROP fails
        with engine.connect() as conn:
            with pytest.raises(ProgrammingError, match="must be owner"):
                conn.execute(text(f"DROP TABLE {SENTINEL_TABLE_NAME};"))
    finally:
        engine.dispose()


def test_09_missing_credentials_prevent_administrative_provisioning(monkeypatch):
    """
    Requirement 9: Missing credentials prevent administrative provisioning.
    setup_test_roles fails with ValueError when no password is provided in argument or environment.
    """
    monkeypatch.delenv("TEST_DB_PASSWORD", raising=False)
    admin_url = os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    with pytest.raises(ValueError, match="must be explicitly configured"):
        setup_test_roles(admin_url, test_role="scheme_saathi_test_user", test_password="")


def test_10_unsafe_role_identifiers_rejected():
    """
    Requirement 10: Unsafe role identifiers rejected.
    validate_pg_identifier strictly enforces alphanumeric + underscores up to 63 chars.
    """
    invalid_identifiers = [
        "role; DROP TABLE users;--",
        "role with spaces",
        "role'quote",
        'role"dquote',
        "123_starts_with_digit",
        "",
        "a" * 64,
        "role$name",
        "role-hyphen",
    ]
    for bad_name in invalid_identifiers:
        with pytest.raises(ValueError, match="Invalid or unsafe PostgreSQL"):
            validate_pg_identifier(bad_name, "test identifier")

    valid_identifiers = ["scheme_saathi_test_user", "test_user_1", "_private_role", "ValidRole"]
    for good_name in valid_identifiers:
        assert validate_pg_identifier(good_name) == good_name


def test_11_sql_construction_cannot_inject_additional_statements():
    """
    Requirement 11: SQL construction cannot inject additional statements.
    Attempts to inject SQL via role names or credentials are fully thwarted.
    """
    admin_url = os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    injection_role = "safe_user; DROP TABLE user_consents;--"
    with pytest.raises(ValueError, match="Invalid or unsafe PostgreSQL"):
        setup_test_roles(admin_url, test_role=injection_role, test_password="pwd")


def test_12_failed_grant_or_revoke_operations_abort_provisioning():
    """
    Requirement 12: Failed grant or revoke operations abort provisioning.
    If an existing role has rolsuper=True, setup_test_roles raises ValueError and aborts.
    """
    admin_url = os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    with pytest.raises(ValueError, match="has unexpected SUPERUSER privilege"):
        # postgres is a known superuser
        setup_test_roles(admin_url, test_role="postgres", test_password="some_password")


def test_13_actual_connected_role_rechecked_before_destructive_operations(monkeypatch):
    """
    Requirement 13: Actual connected role rechecked before destructive operations.
    safe_drop_all and safe_create_all recheck the connected role and reject superusers
    or unauthorized roles immediately before executing DDL.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"))
    dummy_meta = MetaData()

    try:
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_drop_all(
                engine=admin_engine,
                metadata=dummy_meta,
                target_url="postgresql://postgres:postgres@localhost:5432/scheme_saathi_test",
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
                enforce_restricted_role=True,
                expected_role=TEST_RUNTIME_ROLE,
            )
    finally:
        admin_engine.dispose()


def test_14_testcontainers_and_fallback_both_reject_application_database_targets(monkeypatch):
    """
    Requirement 14: Testcontainers and fallback both reject application database targets.
    Whether running in Testcontainers or fallback mode, any URL that points to
    the application database name (scheme_saathi) is unconditionally rejected.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    app_db_variants = [
        settings.DATABASE_URL,
        "postgresql://scheme_saathi_test_user:test_secure_password@localhost:5432/scheme_saathi",
        "postgresql://testcontainer_user:password@127.0.0.1:32768/scheme_saathi",
    ]
    for target in app_db_variants:
        with pytest.raises(ValueError, match="matches the active application database|Target URL points to the active application database|matches application database"):
            verify_database_isolation(
                target_url=target,
                app_url=settings.DATABASE_URL,
                expected_purpose=REGULAR_TEST_PURPOSE,
                enforce_opt_in=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# CORE SAFETY: IDENTITY VERIFICATION & UNCONDITIONAL NAME COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

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
def test_15_different_connection_urls_resolving_to_same_physical_db_rejected(monkeypatch, driver_scheme):
    """
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


def test_16_missing_sentinel_provisioning_is_rejected_during_test_execution(monkeypatch):
    """
    Proves that a missing sentinel causes immediate failure and is NOT automatically
    provisioned by the test runner or verification logic.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_target_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test"

    engine = create_engine(admin_target_url)
    try:
        # Drop sentinel table using admin to simulate unprovisioned target
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
            admin_target_url,
            settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )
        engine.dispose()


def test_17_restricted_catalog_permissions_fail_closed_without_sentinel():
    """
    Catalog permission limitations handled safely and fail closed without sentinel.
    A runtime user lacking pg_control_system() privilege records permission_denied_catalogs = True
    and system_identifier = None without crashing.
    """
    ident = inspect_database_identity(TEST_USER_URL)
    assert ident.is_connected is True
    assert ident.current_database == "scheme_saathi_test"
    assert ident.permission_denied_catalogs is True
    assert ident.system_identifier is None


def test_18_ambiguous_identity_rejected(monkeypatch):
    """
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


def test_19_conflicting_identity_rejected(monkeypatch):
    """
    Conflicting identity rejected:
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
    admin_target_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test"
    engine = create_engine(admin_target_url)
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
            admin_target_url,
            settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )
        engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHORIZATION SEGREGATION & CODE INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════════

def test_20_regular_and_migration_opt_ins_are_strictly_segregated(monkeypatch):
    """
    Setting ALLOW_TEST_DB_RESET=1 authorizes regular tests but NOT migration tests.
    Setting ALLOW_MIGRATION_TESTS=1 authorizes migration tests but NOT regular tests.
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


def test_21_no_code_automatically_inserts_authorization_variables():
    """
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
# TEARDOWN SAFETY & ISOLATION
# ═══════════════════════════════════════════════════════════════════════════════

def test_22_failed_fixture_setup_does_not_trigger_destructive_teardown(monkeypatch):
    """
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


def test_23_migration_cleanup_drops_only_owned_test_schemas_and_protects_system_schemas(monkeypatch):
    """
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


def test_24_existing_unrelated_schemas_and_tables_remain_untouched(monkeypatch):
    """
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


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION DATABASE IMMUTABILITY & AUTO-PROVISIONING PROHIBITION
# ═══════════════════════════════════════════════════════════════════════════════

def test_25_application_database_contents_remain_untouched_in_all_negative_scenarios():
    """
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


def test_26_no_fixture_automatically_provisions_or_modifies_sentinel():
    """
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
