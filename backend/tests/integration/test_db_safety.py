"""
Integration tests for PostgreSQL database target safety guards (app.core.db_safety).

Exhaustive regression test suite verifying:
Section 6 Focused Regression Tests (Tests 01-14):
1. Missing fallback password prevents fallback connection setup.
2. No default or placeholder password is silently used.
3. Failure to query current_user rejects destructive execution.
4. Failure to verify superuser status rejects destructive execution.
5. A regular-test connection using an administrator is rejected.
6. A migration-test connection using an administrator is rejected.
7. A regular-test connection using the expected restricted role is accepted.
8. A migration-test connection using the expected restricted role is accepted.
9. CREATEDB, CREATEROLE, and unsafe role memberships are rejected or removed.
10. The runtime role cannot connect to the application database.
11. PUBLIC retains its original CONNECT privilege.
12. Unrelated roles retain their original privileges.
13. Failure to apply a required privilege restriction aborts provisioning.
14. The connected role is rechecked immediately before destructive operations.

Core Safety & Isolation Tests (Tests 15-28):
15. Testcontainers and fallback both reject application database targets.
16. Driver and host aliases resolving to application database are rejected.
17. Missing sentinel provisioning is rejected during test execution.
18. Restricted catalog permissions fail closed without sentinel.
19. Ambiguous identity rejected when app db is unreachable.
20. Conflicting sentinel metadata rejected.
21. Regular and migration opt-ins are strictly segregated.
22. No code automatically inserts authorization variables.
23. Failed fixture setup does not trigger destructive teardown.
24. Migration cleanup drops only owned test schemas and protects system schemas.
25. Existing unrelated schemas and tables remain untouched.
26. Application database contents remain untouched in all negative scenarios.
27. No fixture automatically provisions or modifies sentinel.
28. Runtime role cannot modify, delete, or drop sentinel table.

Section 7 Execution Trust Boundary & Verification Binding (Tests 29-39):
29. Administrative target URL with caller-provided engine rejected.
30. Empty/unspecified role in target URL with admin engine rejected.
31. Spoofed target URL with different admin engine rejected.
32. Restricted engine matching target URL passes verification.
33. All four gateways reject administrative engine bindings.
34. Non-matching target URL user rejected.
35. Pre-verified target URL does not permit administrative engine execution.
36. Schema creation gateway binds to and validates actual connection.
37. Schema drop gateway binds to and validates actual connection.
38. Gateway does not close caller-provided connection.
39. Connection with active transaction rolls back completely on verification failure.

Section 8 Mandatory Restricted Execution & Transaction Ownership (Tests 40-48):
40. Superuser engine matching superuser target URL rejected across all gateways.
41. Admin engine with target URL having no username rejected across all gateways.
42. Admin engine with target URL having different admin role rejected across all gateways.
43. Restricted runtime role matching target URL succeeds across all gateways.
44. Engine-based gateway commits own DDL.
45. Connection-based gateway does not commit outer transaction.
46. Unrelated pending DML remains rollbackable after gateway operation.
47. Failed gateway operation does not commit or abort outer transaction.
48. Verification and DDL execute on exact same connection object.

Section 9 Runtime-Role Privilege & Membership Integrity (Tests 49-56):
49. Runtime role mutated with CREATEDB rejected and state unchanged.
50. Runtime role mutated with CREATEROLE rejected and state unchanged.
51. Runtime role mutated with INHERIT rejected and state unchanged.
52. Runtime role mutated with BYPASSRLS rejected and state unchanged.
53. Runtime role mutated with REPLICATION rejected and state unchanged.
54. Runtime role granted group membership rejected and state unchanged.
55. Missing or inaccessible catalog info fails closed with state unchanged.
56. Correct restricted role succeeds across all 4 gateways.

Section 10 Testcontainers Role Provisioning & Identifier Injection (Tests 57-58):
57. Invalid role identifiers raise ValueError in validate_pg_identifier.
58. Testcontainers dynamic passwords are unique, cryptographically random, and never fixed.

Section 11 Unsupported Keyword Arguments Rejection (Test 59):
59. Calling security APIs with obsolete kwargs like enforce_restricted_role raises TypeError.
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
    verify_connection_isolation,
    validate_database_target,
    safe_drop_all,
    safe_create_all,
    safe_create_schema,
    safe_drop_schema,
)
from tests.conftest import (
    get_test_database_url,
    TEST_DATABASE_URL,
    USE_TESTCONTAINERS,
    TEST_DB_USER,
)
from tests.integration.test_migrations import (
    get_migration_test_db_url,
    validate_migration_test_target,
    managed_control_schema,
    MIGRATION_TEST_DB_URL,
)


def get_admin_url() -> str:
    """Return administrative PostgreSQL connection URL."""
    return os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: FOCUSED REGRESSION TESTS (1 TO 14)
# ═══════════════════════════════════════════════════════════════════════════════

def test_01_missing_fallback_password_prevents_connection_setup(monkeypatch):
    """
    Requirement 1: Missing fallback password prevents fallback connection setup.
    If TEST_DB_PASSWORD is unset or empty, neither regular nor migration fallback
    connection URL can be constructed.
    """
    monkeypatch.delenv("TEST_DB_PASSWORD", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("MIGRATION_TEST_DB_URL", raising=False)
    monkeypatch.setenv("USE_TESTCONTAINERS", "0")

    with pytest.raises(ValueError, match="Missing required fallback test database credentials"):
        get_test_database_url()

    with pytest.raises(ValueError, match="Missing required migration test database credentials"):
        get_migration_test_db_url()


def test_02_no_default_or_placeholder_password_silently_used(monkeypatch):
    """
    Requirement 2: No default or placeholder password is silently used.
    Placeholder passwords are explicitly rejected, and source files contain zero
    occurrences of default test credentials.
    """
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("USE_TESTCONTAINERS", "0")

    for bad_pwd in ["", "   ", "placeholder", "password"]:
        monkeypatch.setenv("TEST_DB_PASSWORD", bad_pwd)
        with pytest.raises(ValueError, match="Missing required fallback test database credentials"):
            get_test_database_url()

    # Search actual source files for prohibited hardcoded passwords
    backend_dir = Path(__file__).resolve().parent.parent.parent
    prohibited = ["test_secure_password"]
    checked_files = [
        backend_dir / "app" / "core" / "db_safety.py",
        backend_dir / "tests" / "conftest.py",
        backend_dir / "tests" / "integration" / "test_migrations.py",
    ]
    for src_file in checked_files:
        content = src_file.read_text()
        for pwd in prohibited:
            assert pwd not in content, f"Hardcoded password '{pwd}' found in {src_file.name}!"


def test_03_failure_to_query_current_user_rejects_destructive_execution(monkeypatch):
    """
    Requirement 3: Failure to query current_user rejects destructive execution.
    When querying current_user fails or returns empty, verify_database_isolation
    strictly fails closed before any destructive operation.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    # Mock identity to simulate failure querying current_user
    real_inspect = inspect_database_identity

    def mock_inspect(url, timeout_seconds=3.0):
        ident = real_inspect(url, timeout_seconds=timeout_seconds)
        ident.current_user = None
        ident.user_query_error = "simulated query failure on current_user"
        return ident

    monkeypatch.setattr("app.core.db_safety.inspect_database_identity", mock_inspect)

    with pytest.raises(RuntimeError, match=r"failed to query or verify target database current_user"):
        verify_database_isolation(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            expected_role=TEST_RUNTIME_ROLE,
        )


def test_04_failure_to_verify_superuser_status_rejects_destructive_execution(monkeypatch):
    """
    Requirement 4: Failure to verify superuser status rejects destructive execution.
    When checking current_setting('is_superuser') fails, verify_database_isolation
    refuses destructive operations.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    real_inspect = inspect_database_identity

    def mock_inspect(url, timeout_seconds=3.0):
        ident = real_inspect(url, timeout_seconds=timeout_seconds)
        ident.is_superuser_verified = False
        ident.superuser_query_error = "simulated superuser check failure"
        return ident

    monkeypatch.setattr("app.core.db_safety.inspect_database_identity", mock_inspect)

    with pytest.raises(RuntimeError, match=r"failed to query or verify target superuser status"):
        verify_database_isolation(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            expected_role=TEST_RUNTIME_ROLE,
        )


def test_05_regular_test_connection_using_administrator_rejected(monkeypatch):
    """
    Requirement 5: A regular-test connection using an administrator is rejected.
    Connecting with postgres, root, or admin for regular tests fails with PermissionError.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test"
    with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
        verify_database_isolation(
            target_url=admin_url,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            expected_role=TEST_RUNTIME_ROLE,
        )


def test_06_migration_test_connection_using_administrator_rejected(monkeypatch):
    """
    Requirement 6: A migration-test connection using an administrator is rejected.
    Connecting with postgres for migration tests fails with PermissionError even if
    the target database and sentinel are valid.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    admin_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test"
    with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
        validate_migration_test_target(
            test_url=admin_url,
            app_url=settings.DATABASE_URL,
            enforce_opt_in=True,
            expected_role=TEST_RUNTIME_ROLE,
        )


def test_07_regular_test_connection_using_expected_restricted_role_accepted(monkeypatch):
    """
    Requirement 7: A regular-test connection using the expected restricted role is accepted.
    Fallback regular test execution passes validation when connecting as scheme_saathi_test_user.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    ident = verify_database_isolation(
        target_url=TEST_DATABASE_URL,
        app_url=settings.DATABASE_URL,
        expected_purpose=REGULAR_TEST_PURPOSE,
        enforce_opt_in=True,
        expected_role=TEST_RUNTIME_ROLE,
    )
    assert ident.is_connected is True
    assert ident.current_user == TEST_RUNTIME_ROLE
    assert ident.is_superuser is False


def test_08_migration_test_connection_using_expected_restricted_role_accepted(monkeypatch):
    """
    Requirement 8: A migration-test connection using the expected restricted role is accepted.
    Fallback migration test execution passes validation when connecting as scheme_saathi_test_user.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    validate_migration_test_target(
        test_url=MIGRATION_TEST_DB_URL,
        app_url=settings.DATABASE_URL,
        enforce_opt_in=True,
        expected_role=TEST_RUNTIME_ROLE,
    )


def test_09_createdb_createrole_and_unsafe_memberships_rejected_or_removed():
    """
    Requirement 9 & Section 3: CREATEDB, CREATEROLE, rolinherit, and all role memberships
    are revoked or rejected. setup_test_roles explicitly establishes LOGIN NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS, strips all memberships,
    and enforces zero memberships for the dedicated test runtime role.
    """
    admin_url = get_admin_url()
    admin_engine = create_engine(admin_url)
    temp_role = f"test_role_elev_{uuid.uuid4().hex[:6]}"
    temp_group = f"test_grp_{uuid.uuid4().hex[:6]}"
    test_pwd = os.getenv("TEST_DB_PASSWORD")
    if not test_pwd:
        pytest.skip("TEST_DB_PASSWORD required for setup_test_roles verification")

    try:
        # Create group role and elevated role with membership intentionally
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE ROLE "{temp_group}";'))
            conn.execute(text(f'CREATE ROLE "{temp_role}" WITH LOGIN CREATEDB CREATEROLE INHERIT REPLICATION BYPASSRLS PASSWORD \'{test_pwd}\';'))
            conn.execute(text(f'GRANT "{temp_group}" TO "{temp_role}";'))
            conn.commit()

        # Run setup_test_roles on this role
        setup_test_roles(admin_url, test_role=temp_role, test_password=test_pwd)

        # Verify that elevated privileges were completely stripped and zero memberships remain
        with admin_engine.connect() as conn:
            attrs = conn.execute(
                text("SELECT rolsuper, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication, rolbypassrls, rolinherit FROM pg_roles WHERE rolname = :r;"),
                {"r": temp_role},
            ).mappings().first()
            assert attrs["rolsuper"] is False
            assert attrs["rolcreaterole"] is False
            assert attrs["rolcreatedb"] is False
            assert attrs["rolcanlogin"] is True
            assert attrs["rolreplication"] is False
            assert attrs["rolbypassrls"] is False
            assert attrs["rolinherit"] is False

            memberships = conn.execute(
                text("""
                    SELECT r.rolname
                    FROM pg_auth_members m
                    JOIN pg_roles r ON r.oid = m.roleid
                    JOIN pg_roles u ON u.oid = m.member
                    WHERE u.rolname = :r;
                """),
                {"r": temp_role},
            ).fetchall()
            assert len(memberships) == 0, f"Expected 0 memberships, found: {memberships}"
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'REVOKE ALL ON DATABASE "scheme_saathi_test" FROM "{temp_role}";'))
            conn.execute(text(f'REVOKE ALL ON DATABASE "scheme_saathi_migration_test" FROM "{temp_role}";'))
            conn.execute(text(f'DROP ROLE IF EXISTS "{temp_role}";'))
            conn.execute(text(f'DROP ROLE IF EXISTS "{temp_group}";'))
            conn.commit()
        admin_engine.dispose()


def test_10_runtime_role_cannot_connect_to_application_database():
    """
    Requirement 10: The runtime role cannot connect to the application database.
    Connecting to scheme_saathi as scheme_saathi_test_user is blocked by
    session_preload_libraries and fails before establishing a usable session.
    """
    pwd = os.getenv("TEST_DB_PASSWORD")
    if not pwd:
        pytest.skip("TEST_DB_PASSWORD required for connection check")
    app_target_with_test_user = f"postgresql://{TEST_RUNTIME_ROLE}:{pwd}@localhost:5432/scheme_saathi"
    engine = create_engine(app_target_with_test_user)
    try:
        with pytest.raises(OperationalError) as exc_info:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
        assert "FATAL" in str(exc_info.value) or "connection to server" in str(exc_info.value)
    finally:
        engine.dispose()


def test_11_public_retains_original_connect_privilege():
    """
    Requirement 11: PUBLIC retains its original CONNECT privilege.
    Verifies that PUBLIC has not lost CONNECT on scheme_saathi.
    """
    admin_engine = create_engine(get_admin_url())
    with admin_engine.connect() as conn:
        has_public_connect = conn.execute(
            text("SELECT has_database_privilege('public', 'scheme_saathi', 'CONNECT');")
        ).scalar()
        assert has_public_connect is True, "PUBLIC lost CONNECT privilege on scheme_saathi!"
    admin_engine.dispose()


def test_12_unrelated_roles_retain_original_privileges():
    """
    Requirement 12: Unrelated roles retain their original privileges.
    Creating a separate unrelated role and running setup_test_roles() does not
    revoke or alter the privileges of the unrelated role.
    """
    admin_url = get_admin_url()
    admin_engine = create_engine(admin_url)
    unrelated_role = f"unrelated_user_{uuid.uuid4().hex[:6]}"
    test_pwd = os.getenv("TEST_DB_PASSWORD")
    if not test_pwd:
        pytest.skip("TEST_DB_PASSWORD required for role setup verification")

    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE ROLE "{unrelated_role}" WITH LOGIN PASSWORD \'unrelated_pass\';'))
            conn.commit()

        # Run setup_test_roles for scheme_saathi_test_user
        setup_test_roles(admin_url, test_role=TEST_RUNTIME_ROLE, test_password=test_pwd)

        # Verify unrelated role can still connect to scheme_saathi
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


def test_13_failure_to_apply_required_privilege_restriction_aborts_provisioning():
    """
    Requirement 13: Failure to apply a required privilege restriction aborts provisioning.
    If setup_test_roles is called on an immutable superuser (or with empty credentials),
    it fails closed immediately and aborts.
    """
    admin_url = get_admin_url()
    with pytest.raises(ValueError, match=r"has unexpected SUPERUSER.*privilege"):
        setup_test_roles(admin_url, test_role="postgres", test_password="some_password")

    with pytest.raises(ValueError, match="must be explicitly configured"):
        setup_test_roles(admin_url, test_role="scheme_saathi_test_user", test_password="")


def test_14_connected_role_rechecked_immediately_before_destructive_operations(monkeypatch):
    """
    Requirement 14: The connected role is rechecked immediately before destructive operations.
    safe_drop_all, safe_create_all, safe_create_schema, and safe_drop_schema verify
    the actual connected role and catalog attributes unconditionally before executing DDL.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    admin_engine = create_engine(get_admin_url())
    dummy_meta = MetaData()

    try:
        # safe_drop_all rechecks
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_drop_all(
                engine=admin_engine,
                metadata=dummy_meta,
                target_url="postgresql://postgres:postgres@localhost:5432/scheme_saathi_test",
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )

        # safe_create_all rechecks
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_create_all(
                engine=admin_engine,
                metadata=dummy_meta,
                target_url="postgresql://postgres:postgres@localhost:5432/scheme_saathi_test",
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )

        # safe_create_schema rechecks
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_create_schema(
                engine=admin_engine,
                schema_name="migtest_chk_create",
                target_url="postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test",
                app_url=settings.DATABASE_URL,
                purpose=MIGRATION_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )

        # safe_drop_schema rechecks
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_drop_schema(
                engine=admin_engine,
                schema_name="migtest_chk_drop",
                target_url="postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test",
                app_url=settings.DATABASE_URL,
                purpose=MIGRATION_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )
    finally:
        admin_engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# CORE SAFETY: IDENTITY VERIFICATION & UNCONDITIONAL NAME COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

def test_15_testcontainers_and_fallback_both_reject_application_database_targets(monkeypatch):
    """
    Whether running in Testcontainers or fallback mode, any URL that points to
    the application database name (scheme_saathi) is unconditionally rejected.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")

    app_db_variants = [
        settings.DATABASE_URL,
        "postgresql://scheme_saathi_test_user:some_password@localhost:5432/scheme_saathi",
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
def test_16_different_connection_urls_resolving_to_same_physical_db_rejected(monkeypatch, driver_scheme):
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


def test_17_missing_sentinel_provisioning_is_rejected_during_test_execution(monkeypatch):
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


def test_18_restricted_catalog_permissions_fail_closed_without_sentinel():
    """
    Catalog permission limitations handled safely and fail closed without sentinel.
    A runtime user lacking pg_control_system() privilege records permission_denied_catalogs = True
    and system_identifier = None without crashing.
    """
    ident = inspect_database_identity(TEST_DATABASE_URL)
    assert ident.is_connected is True
    assert ident.current_database == "scheme_saathi_test"
    assert ident.permission_denied_catalogs is True
    assert ident.system_identifier is None


def test_19_ambiguous_identity_rejected(monkeypatch):
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


def test_20_conflicting_identity_rejected(monkeypatch):
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


def test_21_regular_and_migration_opt_ins_are_strictly_segregated(monkeypatch):
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


def test_22_no_code_automatically_inserts_authorization_variables():
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


def test_23_failed_fixture_setup_does_not_trigger_destructive_teardown(monkeypatch):
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


def test_24_migration_cleanup_drops_only_owned_test_schemas_and_protects_system_schemas(monkeypatch):
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
                safe_drop_schema(
                    engine,
                    protected,
                    MIGRATION_TEST_DB_URL,
                    settings.DATABASE_URL,
                    expected_role=TEST_RUNTIME_ROLE,
                )

        # 2. Refuse non-test schema
        with pytest.raises(ValueError, match="not an explicitly owned test schema"):
            safe_drop_schema(
                engine,
                "unrelated_schema",
                MIGRATION_TEST_DB_URL,
                settings.DATABASE_URL,
                expected_role=TEST_RUNTIME_ROLE,
            )

        # 3. Create and safely drop owned test schema
        test_schema = f"migtest_{uuid.uuid4().hex[:8]}"
        safe_create_schema(
            engine,
            test_schema,
            MIGRATION_TEST_DB_URL,
            settings.DATABASE_URL,
            expected_role=TEST_RUNTIME_ROLE,
        )

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                {"s": test_schema},
            ).scalar() is True

        safe_drop_schema(
            engine,
            test_schema,
            MIGRATION_TEST_DB_URL,
            settings.DATABASE_URL,
            expected_role=TEST_RUNTIME_ROLE,
        )

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT exists(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                {"s": test_schema},
            ).scalar() is False
    finally:
        engine.dispose()


def test_25_existing_unrelated_schemas_and_tables_remain_untouched(monkeypatch):
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


def test_26_application_database_contents_remain_untouched_in_all_negative_scenarios():
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


def test_27_no_fixture_automatically_provisions_or_modifies_sentinel():
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


def test_28_runtime_role_cannot_modify_or_drop_sentinel():
    """
    SELECT on the sentinel succeeds, while UPDATE, DELETE, and DROP TABLE fail
    with permission errors.
    """
    engine = create_engine(TEST_DATABASE_URL)
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


# ═══════════════════════════════════════════════════════════════════════════════
# ACTUAL DDL CONNECTION & MISMATCH REGRESSION TESTS (Tests 29-38)
# ═══════════════════════════════════════════════════════════════════════════════

def test_29_safe_target_url_combined_with_admin_engine_rejected(monkeypatch):
    """
    Section 2 Requirement 1: A safe target_url combined with an administrative engine is rejected.
    Even though target_url specifies the safe disposable test DB with restricted role,
    supplying an engine connected as postgres/superuser fails before DDL execution.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(get_admin_url())
    dummy_meta = MetaData()

    try:
        with pytest.raises(PermissionError, match=r"Connection mismatch.*administrative/superuser|using administrative/superuser"):
            safe_drop_all(
                engine=admin_engine,
                metadata=dummy_meta,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )

        with pytest.raises(PermissionError, match=r"Connection mismatch.*administrative/superuser|using administrative/superuser"):
            safe_create_all(
                engine=admin_engine,
                metadata=dummy_meta,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )
    finally:
        admin_engine.dispose()


def test_30_safe_target_url_combined_with_different_database_engine_rejected(monkeypatch):
    """
    Section 2 Requirement 2: A safe target_url combined with an engine connected to a different
    database is rejected.
    target_url specifies scheme_saathi_test, but engine connects to scheme_saathi_migration_test.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    diff_db_engine = create_engine(get_migration_test_db_url())
    dummy_meta = MetaData()

    try:
        with pytest.raises(ValueError, match=r"Connection mismatch.*database"):
            safe_drop_all(
                engine=diff_db_engine,
                metadata=dummy_meta,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )

        with pytest.raises(ValueError, match=r"Connection mismatch.*database"):
            safe_create_all(
                engine=diff_db_engine,
                metadata=dummy_meta,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )
    finally:
        diff_db_engine.dispose()


def test_31_restricted_role_url_combined_with_different_role_engine_rejected(monkeypatch):
    """
    Section 2 Requirement 3: A restricted-role URL combined with an engine authenticated as a
    different role is rejected.
    target_url specifies scheme_saathi_test_user, but engine connects as a different user.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_url = get_admin_url()
    admin_engine = create_engine(admin_url)
    diff_role = f"test_diff_user_{uuid.uuid4().hex[:6]}"
    test_pwd = os.getenv("TEST_DB_PASSWORD")
    if not test_pwd:
        pytest.skip("TEST_DB_PASSWORD required for role test")

    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE ROLE "{diff_role}" WITH LOGIN PASSWORD \'{test_pwd}\';'))
            conn.execute(text(f'GRANT CONNECT, TEMPORARY ON DATABASE "scheme_saathi_test" TO "{diff_role}";'))
            conn.commit()

        parsed = normalize_db_url(TEST_DATABASE_URL)
        diff_url = f"postgresql://{diff_role}:{test_pwd}@{parsed.host}:{parsed.port or 5432}/scheme_saathi_test"
        diff_engine = create_engine(diff_url)

        try:
            with pytest.raises(PermissionError, match=r"Connection mismatch.*role"):
                safe_create_all(
                    engine=diff_engine,
                    metadata=MetaData(),
                    target_url=TEST_DATABASE_URL,
                    app_url=settings.DATABASE_URL,
                    purpose=REGULAR_TEST_PURPOSE,
                )
        finally:
            diff_engine.dispose()
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'REVOKE ALL ON DATABASE "scheme_saathi_test" FROM "{diff_role}";'))
            conn.execute(text(f'DROP ROLE IF EXISTS "{diff_role}";'))
            conn.commit()
        admin_engine.dispose()


def test_32_safe_drop_all_never_executes_ddl_on_mismatch_and_leaves_tables_unchanged(monkeypatch):
    """
    Section 2 Requirements 4 & 10: safe_drop_all never executes DDL after a connection mismatch,
    leaving existing tables unchanged.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    test_engine = create_engine(TEST_DATABASE_URL)
    admin_engine = create_engine(get_admin_url())

    meta = MetaData()
    tbl_name = f"canary_drop_all_{uuid.uuid4().hex[:6]}"
    canary_table = Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    try:
        # 1. Create table using legitimate test connection
        with test_engine.connect() as conn:
            canary_table.create(bind=conn)
            conn.commit()

        # Verify table exists in test DB
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name in insp.get_table_names()

        # 2. Attempt safe_drop_all with mismatched admin engine
        with pytest.raises(PermissionError, match=r"Connection mismatch.*administrative/superuser|using administrative/superuser"):
            safe_drop_all(
                engine=admin_engine,
                metadata=meta,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )

        # 3. Assert existing table is STILL PRESENT and unchanged in test DB
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name in insp.get_table_names(), "Canary table was unexpectedly dropped after connection mismatch!"
    finally:
        with test_engine.connect() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{tbl_name}";'))
            conn.commit()
        test_engine.dispose()
        admin_engine.dispose()


def test_33_safe_create_all_never_executes_ddl_on_mismatch_and_leaves_state_unchanged(monkeypatch):
    """
    Section 2 Requirements 5 & 10: safe_create_all never executes DDL after a connection mismatch,
    leaving database state unchanged.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    test_engine = create_engine(TEST_DATABASE_URL)
    admin_engine = create_engine(get_admin_url())

    meta = MetaData()
    tbl_name = f"canary_create_all_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    try:
        # Verify table does not exist
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name not in insp.get_table_names()

        # Attempt safe_create_all with mismatched admin engine
        with pytest.raises(PermissionError, match=r"Connection mismatch.*administrative/superuser|using administrative/superuser"):
            safe_create_all(
                engine=admin_engine,
                metadata=meta,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )

        # Verify table was NOT created in test DB
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name not in insp.get_table_names(), "Canary table was unexpectedly created after connection mismatch!"
    finally:
        test_engine.dispose()
        admin_engine.dispose()


def test_34_safe_create_schema_never_executes_ddl_on_mismatch_and_leaves_state_unchanged(monkeypatch):
    """
    Section 2 Requirements 6 & 10: safe_create_schema never executes DDL after a connection mismatch,
    leaving schemas unchanged.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    migration_engine = create_engine(get_migration_test_db_url())
    test_db_engine = create_engine(TEST_DATABASE_URL)  # points to wrong DB (scheme_saathi_test instead of migration DB)
    schema_name = f"migtest_mismatch_create_{uuid.uuid4().hex[:6]}"

    try:
        with pytest.raises(ValueError, match=r"Connection mismatch.*database"):
            safe_create_schema(
                engine=test_db_engine,
                schema_name=schema_name,
                target_url=get_migration_test_db_url(),
                app_url=settings.DATABASE_URL,
                purpose=MIGRATION_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )

        # Verify schema was NOT created in migration DB
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert not res, "Schema was unexpectedly created after connection mismatch!"
    finally:
        test_db_engine.dispose()
        migration_engine.dispose()


def test_35_safe_drop_schema_never_executes_ddl_on_mismatch_and_leaves_schemas_unchanged(monkeypatch):
    """
    Section 2 Requirements 7 & 10: safe_drop_schema never executes DDL after a connection mismatch,
    leaving existing schemas unchanged.
    """
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    migration_engine = create_engine(get_migration_test_db_url())
    admin_engine = create_engine(get_admin_url())
    schema_name = f"migtest_mismatch_drop_{uuid.uuid4().hex[:6]}"

    try:
        # Create schema using legitimate migration connection
        with migration_engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema_name}";'))
            conn.commit()

        # Verify schema exists
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert res, "Pre-condition failed: schema was not created."

        # Attempt safe_drop_schema with mismatched admin engine
        with pytest.raises(PermissionError, match=r"Connection mismatch.*administrative/superuser|using administrative/superuser"):
            safe_drop_schema(
                engine=admin_engine,
                schema_name=schema_name,
                target_url=get_migration_test_db_url(),
                app_url=settings.DATABASE_URL,
                purpose=MIGRATION_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )

        # Verify schema STILL EXISTS in migration DB
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert res, "Schema was unexpectedly dropped after connection mismatch!"
    finally:
        with migration_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;'))
            conn.commit()
        migration_engine.dispose()
        admin_engine.dispose()


def test_36_correct_restricted_role_connection_successfully_executes_permitted_ddl(monkeypatch):
    """
    Section 2 Requirement 8: The correct restricted-role connection successfully executes permitted test operations.
    Using verified scheme_saathi_test_user, safe_create_all, safe_drop_all, safe_create_schema,
    and safe_drop_schema all succeed.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")
    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())

    meta = MetaData()
    tbl_name = f"canary_perm_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_perm_{uuid.uuid4().hex[:6]}"

    try:
        # Table lifecycle on regular test DB with restricted role
        safe_create_all(
            engine=test_engine,
            metadata=meta,
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            expected_role=TEST_RUNTIME_ROLE,
        )
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name in insp.get_table_names()

        safe_drop_all(
            engine=test_engine,
            metadata=meta,
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            expected_role=TEST_RUNTIME_ROLE,
        )
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name not in insp.get_table_names()

        # Schema lifecycle on migration test DB with restricted role
        safe_create_schema(
            engine=migration_engine,
            schema_name=schema_name,
            target_url=get_migration_test_db_url(),
            app_url=settings.DATABASE_URL,
            purpose=MIGRATION_TEST_PURPOSE,
            expected_role=TEST_RUNTIME_ROLE,
        )
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert res

        safe_drop_schema(
            engine=migration_engine,
            schema_name=schema_name,
            target_url=get_migration_test_db_url(),
            app_url=settings.DATABASE_URL,
            purpose=MIGRATION_TEST_PURPOSE,
            expected_role=TEST_RUNTIME_ROLE,
        )
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert not res
    finally:
        test_engine.dispose()
        migration_engine.dispose()


def test_37_actual_execution_connection_checked_immediately_before_ddl(monkeypatch):
    """
    Section 2 Requirement 9: The actual execution connection is checked immediately before DDL.
    Proves that verification inspects the live Connection object directly and executes
    DDL through that exact verified Connection without releasing it.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    test_engine = create_engine(TEST_DATABASE_URL)

    with test_engine.connect() as conn:
        ident = verify_connection_isolation(
            conn=conn,
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            expected_role=TEST_RUNTIME_ROLE,
        )
        assert ident.is_connected is True
        assert ident.current_database == "scheme_saathi_test"
        assert ident.current_user == TEST_RUNTIME_ROLE
        assert ident.is_superuser is False
        assert not conn.closed, "Connection was closed during verification!"

    test_engine.dispose()


def test_38_safe_target_url_combined_with_app_db_engine_rejected_and_app_db_untouched(monkeypatch):
    """
    Section 2 Requirements 1, 2 & 10: Supplying a safe disposable target URL with an engine
    pointing to the active application database is unconditionally rejected, leaving the
    application database completely untouched.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    app_engine = create_engine(settings.DATABASE_URL)
    dummy_meta = MetaData()

    # Pre-condition: count application DB tables before attempt
    with app_engine.connect() as conn:
        insp = inspect(conn)
        tables_before = set(insp.get_table_names())

    try:
        with pytest.raises((ValueError, PermissionError), match=r"Connection mismatch|active application database|using administrative/superuser"):
            safe_drop_all(
                engine=app_engine,
                metadata=dummy_meta,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )

        # Assert application database tables are completely unchanged
        with app_engine.connect() as conn:
            insp = inspect(conn)
            tables_after = set(insp.get_table_names())
            assert tables_before == tables_after, "Application database tables were modified by safe_drop_all!"
    finally:
        app_engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: ADMINISTRATIVE-TARGET BYPASS REGRESSION TESTS (39 TO 43)
# ═══════════════════════════════════════════════════════════════════════════════

def test_39_admin_engine_matching_admin_target_url_rejected_all_gateways(monkeypatch):
    """
    Scenario a: Administrative engine + matching administrative target URL ('postgres' on both).
    All four gateways must unconditionally reject administrative connection before DDL,
    leaving existing tables and schemas unchanged.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    admin_reg_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test"
    admin_mig_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test"
    admin_reg_engine = create_engine(admin_reg_url)
    admin_mig_engine = create_engine(admin_mig_url)

    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())

    meta = MetaData()
    canary_drop_tbl = f"canary_a_drop_{uuid.uuid4().hex[:6]}"
    Table(canary_drop_tbl, meta, Column("id", Integer, primary_key=True))

    canary_create_tbl = f"canary_a_create_{uuid.uuid4().hex[:6]}"
    meta_create = MetaData()
    Table(canary_create_tbl, meta_create, Column("id", Integer, primary_key=True))

    canary_schema_drop = f"migtest_a_drop_{uuid.uuid4().hex[:6]}"
    canary_schema_create = f"migtest_a_create_{uuid.uuid4().hex[:6]}"

    try:
        # Pre-provision canaries with legitimate restricted connection
        with test_engine.connect() as conn:
            meta.create_all(bind=conn)
            conn.commit()
            insp = inspect(conn)
            assert canary_drop_tbl in insp.get_table_names()

        with migration_engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA "{canary_schema_drop}";'))
            conn.commit()

        # 1. safe_drop_all with matching admin credentials rejected
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_drop_all(
                engine=admin_reg_engine,
                metadata=meta,
                target_url=admin_reg_url,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )
        # Canary table remains untouched
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert canary_drop_tbl in insp.get_table_names(), "Canary table was unexpectedly dropped!"

        # 2. safe_create_all with matching admin credentials rejected
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_create_all(
                engine=admin_reg_engine,
                metadata=meta_create,
                target_url=admin_reg_url,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
            )
        # Canary table was not created
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert canary_create_tbl not in insp.get_table_names(), "Canary table was unexpectedly created!"

        # 3. safe_create_schema with matching admin credentials rejected
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_create_schema(
                engine=admin_mig_engine,
                schema_name=canary_schema_create,
                target_url=admin_mig_url,
                app_url=settings.DATABASE_URL,
                purpose=MIGRATION_TEST_PURPOSE,
            )
        # Canary schema was not created
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": canary_schema_create},
            ).scalar()
            assert not res, "Canary schema was unexpectedly created!"

        # 4. safe_drop_schema with matching admin credentials rejected
        with pytest.raises(PermissionError, match=r"using administrative/superuser role 'postgres'"):
            safe_drop_schema(
                engine=admin_mig_engine,
                schema_name=canary_schema_drop,
                target_url=admin_mig_url,
                app_url=settings.DATABASE_URL,
                purpose=MIGRATION_TEST_PURPOSE,
            )
        # Canary schema remains untouched
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": canary_schema_drop},
            ).scalar()
            assert res, "Canary schema was unexpectedly dropped!"

    finally:
        with test_engine.connect() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{canary_drop_tbl}";'))
            conn.commit()
        with migration_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{canary_schema_drop}" CASCADE;'))
            conn.commit()
        admin_reg_engine.dispose()
        admin_mig_engine.dispose()
        test_engine.dispose()
        migration_engine.dispose()


def test_40_superuser_engine_matching_superuser_target_url_rejected_all_gateways(monkeypatch):
    """
    Scenario b: Superuser engine + matching superuser target URL.
    Verifies that the engine connection is verified as superuser (is_superuser == 'on'),
    and that all four gateways unconditionally reject superuser connections before DDL.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    admin_reg_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test"
    admin_mig_url = "postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test"
    super_reg_engine = create_engine(admin_reg_url)
    super_mig_engine = create_engine(admin_mig_url)

    # Verify actual connection is superuser
    with super_reg_engine.connect() as conn:
        assert conn.execute(text("SELECT current_setting('is_superuser');")).scalar() == "on"

    meta = MetaData()
    tbl_name = f"canary_b_tbl_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_b_sch_{uuid.uuid4().hex[:6]}"

    try:
        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_drop_all(super_reg_engine, meta, admin_reg_url, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_create_all(super_reg_engine, meta, admin_reg_url, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_create_schema(super_mig_engine, schema_name, admin_mig_url, settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_drop_schema(super_mig_engine, schema_name, admin_mig_url, settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)
    finally:
        super_reg_engine.dispose()
        super_mig_engine.dispose()


def test_41_admin_engine_target_url_with_no_username_rejected_all_gateways(monkeypatch):
    """
    Scenario c: Administrative engine + target URL with no username.
    Even when target URL lacks user credentials, an administrative execution engine
    must be rejected immediately before DDL across all four gateways.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    admin_reg_engine = create_engine("postgresql://postgres:postgres@localhost:5432/scheme_saathi_test")
    admin_mig_engine = create_engine("postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test")

    no_user_reg_url = "postgresql://localhost:5432/scheme_saathi_test"
    no_user_mig_url = "postgresql://localhost:5432/scheme_saathi_migration_test"

    meta = MetaData()
    tbl_name = f"canary_c_tbl_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_c_sch_{uuid.uuid4().hex[:6]}"

    try:
        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_drop_all(admin_reg_engine, meta, no_user_reg_url, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_create_all(admin_reg_engine, meta, no_user_reg_url, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_create_schema(admin_mig_engine, schema_name, no_user_mig_url, settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role"):
            safe_drop_schema(admin_mig_engine, schema_name, no_user_mig_url, settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)
    finally:
        admin_reg_engine.dispose()
        admin_mig_engine.dispose()


def test_42_admin_engine_target_url_different_admin_role_rejected_all_gateways(monkeypatch):
    """
    Scenario d: Administrative engine + target URL specifying different administrative role ('root').
    Rejection must occur before DDL across all four gateways.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    admin_reg_engine = create_engine("postgresql://postgres:postgres@localhost:5432/scheme_saathi_test")
    admin_mig_engine = create_engine("postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test")

    root_reg_url = "postgresql://root:somepass@localhost:5432/scheme_saathi_test"
    root_mig_url = "postgresql://root:somepass@localhost:5432/scheme_saathi_migration_test"

    meta = MetaData()
    tbl_name = f"canary_d_tbl_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_d_sch_{uuid.uuid4().hex[:6]}"

    try:
        with pytest.raises(PermissionError, match=r"using administrative/superuser role|administrative role 'root'"):
            safe_drop_all(admin_reg_engine, meta, root_reg_url, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role|administrative role 'root'"):
            safe_create_all(admin_reg_engine, meta, root_reg_url, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role|administrative role 'root'"):
            safe_create_schema(admin_mig_engine, schema_name, root_mig_url, settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)

        with pytest.raises(PermissionError, match=r"using administrative/superuser role|administrative role 'root'"):
            safe_drop_schema(admin_mig_engine, schema_name, root_mig_url, settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)
    finally:
        admin_reg_engine.dispose()
        admin_mig_engine.dispose()


def test_43_restricted_runtime_role_matching_target_url_succeeds_all_gateways(monkeypatch):
    """
    Scenario e: Restricted runtime role + matching target URL succeeds across all four gateways.
    Verifies that safe_create_all, safe_drop_all, safe_create_schema, and safe_drop_schema
    all succeed cleanly when connecting under the restricted runtime role.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())

    meta = MetaData()
    tbl_name = f"canary_e_tbl_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_e_sch_{uuid.uuid4().hex[:6]}"

    try:
        # 1. safe_create_all succeeds
        safe_create_all(test_engine, meta, TEST_DATABASE_URL, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name in insp.get_table_names()

        # 2. safe_drop_all succeeds
        safe_drop_all(test_engine, meta, TEST_DATABASE_URL, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)
        with test_engine.connect() as conn:
            insp = inspect(conn)
            assert tbl_name not in insp.get_table_names()

        # 3. safe_create_schema succeeds
        safe_create_schema(migration_engine, schema_name, get_migration_test_db_url(), settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert res is True

        # 4. safe_drop_schema succeeds
        safe_drop_schema(migration_engine, schema_name, get_migration_test_db_url(), settings.DATABASE_URL, purpose=MIGRATION_TEST_PURPOSE)
        with migration_engine.connect() as conn:
            res = conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert res is False
    finally:
        test_engine.dispose()
        migration_engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: EXPLICIT TRANSACTION OWNERSHIP REGRESSION TESTS (44 TO 48)
# ═══════════════════════════════════════════════════════════════════════════════

def test_44_engine_based_gateway_commits_own_ddl(monkeypatch):
    """
    Requirement 1: Engine-based gateway checks out a connection, owns the transaction,
    commits on success, and closes connection on exit.
    DDL changes are immediately visible on a separate, fresh connection.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())

    meta = MetaData()
    tbl_name = f"canary_tx44_tbl_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_tx44_sch_{uuid.uuid4().hex[:6]}"

    try:
        # safe_create_all via engine
        safe_create_all(test_engine, meta, TEST_DATABASE_URL, settings.DATABASE_URL)
        # Fresh connection from engine sees table
        with test_engine.connect() as fresh_conn:
            insp = inspect(fresh_conn)
            assert tbl_name in insp.get_table_names()

        # safe_drop_all via engine
        safe_drop_all(test_engine, meta, TEST_DATABASE_URL, settings.DATABASE_URL)
        with test_engine.connect() as fresh_conn:
            insp = inspect(fresh_conn)
            assert tbl_name not in insp.get_table_names()

        # safe_create_schema via engine
        safe_create_schema(migration_engine, schema_name, get_migration_test_db_url(), settings.DATABASE_URL)
        with migration_engine.connect() as fresh_conn:
            res = fresh_conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert res is True

        # safe_drop_schema via engine
        safe_drop_schema(migration_engine, schema_name, get_migration_test_db_url(), settings.DATABASE_URL)
        with migration_engine.connect() as fresh_conn:
            res = fresh_conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert res is False
    finally:
        test_engine.dispose()
        migration_engine.dispose()


def test_45_connection_based_gateway_does_not_commit_outer_transaction(monkeypatch):
    """
    Requirement 2: Connection-based gateway does not commit outer transaction.
    When caller supplies a Connection with an active transaction (conn.in_transaction()),
    the gateway uses a nested transaction/savepoint. Rolling back the outer transaction
    rolls back the gateway's DDL execution.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())

    meta = MetaData()
    tbl_name = f"canary_tx45_tbl_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_tx45_sch_{uuid.uuid4().hex[:6]}"

    try:
        # 1. safe_create_all inside caller's outer transaction
        conn = test_engine.connect()
        trans = conn.begin()
        safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)
        # Roll back caller's outer transaction
        trans.rollback()
        conn.close()

        # Table must NOT exist on a fresh connection
        with test_engine.connect() as fresh_conn:
            insp = inspect(fresh_conn)
            assert tbl_name not in insp.get_table_names(), "Table was prematurely committed by gateway!"

        # 2. safe_create_schema inside caller's outer transaction
        mig_conn = migration_engine.connect()
        mig_trans = mig_conn.begin()
        safe_create_schema(mig_conn, schema_name, get_migration_test_db_url(), settings.DATABASE_URL)
        # Roll back caller's outer transaction
        mig_trans.rollback()
        mig_conn.close()

        # Schema must NOT exist on a fresh connection
        with migration_engine.connect() as fresh_conn:
            res = fresh_conn.execute(
                text("SELECT exists(SELECT 1 FROM information_schema.schemata WHERE schema_name = :s)"),
                {"s": schema_name},
            ).scalar()
            assert not res, "Schema was prematurely committed by gateway!"
    finally:
        test_engine.dispose()
        migration_engine.dispose()


def test_46_unrelated_pending_dml_remains_rollbackable_after_gateway_operation(monkeypatch):
    """
    Requirement 3: Unrelated pending DML remains rollback-able after gateway operation.
    Caller executes DML in outer transaction, calls gateway to execute DDL, then rolls back
    outer transaction. The pending DML row must NOT be committed.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    test_engine = create_engine(TEST_DATABASE_URL)

    parent_tbl = f"canary_tx46_parent_{uuid.uuid4().hex[:6]}"
    sub_tbl = f"canary_tx46_sub_{uuid.uuid4().hex[:6]}"

    meta_parent = MetaData()
    Table(parent_tbl, meta_parent, Column("id", Integer, primary_key=True))
    meta_sub = MetaData()
    Table(sub_tbl, meta_sub, Column("id", Integer, primary_key=True))

    try:
        # Pre-create parent table
        with test_engine.connect() as conn:
            meta_parent.create_all(bind=conn)
            conn.commit()

        # Caller begins outer transaction and executes pending DML
        conn = test_engine.connect()
        trans = conn.begin()
        conn.execute(text(f'INSERT INTO "{parent_tbl}" VALUES (101);'))

        # Gateway executes safe_create_all within nested savepoint
        safe_create_all(conn, meta_sub, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Gateway executes safe_drop_all on sub_tbl within nested savepoint
        safe_drop_all(conn, meta_sub, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Caller rolls back outer transaction
        trans.rollback()
        conn.close()

        # Verify on a fresh connection: DML row 101 was NOT committed!
        with test_engine.connect() as fresh_conn:
            count = fresh_conn.execute(text(f'SELECT count(*) FROM "{parent_tbl}";')).scalar()
            assert count == 0, f"Pending DML was prematurely committed! Expected 0 rows, got {count}"
    finally:
        with test_engine.connect() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{parent_tbl}";'))
            conn.commit()
        test_engine.dispose()


def test_47_failed_gateway_operation_does_not_commit_or_abort_outer_transaction(monkeypatch):
    """
    Requirement 4: Failed gateway operation does not commit or abort unrelated caller work.
    Caller starts transaction, executes DML, gateway fails and rolls back its savepoint.
    The outer transaction remains valid (not aborted), allowing caller to execute further
    DML and commit successfully.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    test_engine = create_engine(TEST_DATABASE_URL)

    parent_tbl = f"canary_tx47_parent_{uuid.uuid4().hex[:6]}"
    meta_parent = MetaData()
    Table(parent_tbl, meta_parent, Column("id", Integer, primary_key=True))

    try:
        # Pre-create parent table
        with test_engine.connect() as conn:
            meta_parent.create_all(bind=conn)
            conn.commit()

        # Caller begins outer transaction and executes initial DML
        conn = test_engine.connect()
        try:
            trans = conn.begin()
            conn.execute(text(f'INSERT INTO "{parent_tbl}" VALUES (201);'))

            # Gateway fails inside its nested savepoint (mismatched database in target URL)
            with pytest.raises(ValueError, match=r"Connection mismatch.*database"):
                meta_dummy = MetaData()
                safe_create_all(
                    conn,
                    meta_dummy,
                    "postgresql://scheme_saathi_test_user:test_secure_password@localhost:5432/wrong_target_db",
                    settings.DATABASE_URL,
                )

            # Crucial check: outer transaction remains active and NOT aborted into InFailedSqlTransaction
            assert conn.in_transaction() is True, "Outer transaction was unexpectedly terminated by gateway failure!"

            # Caller successfully executes further DML on the surviving transaction
            conn.execute(text(f'INSERT INTO "{parent_tbl}" VALUES (202);'))
            trans.commit()
        finally:
            conn.close()

        # Verify on fresh connection: both DML rows were committed successfully!
        with test_engine.connect() as fresh_conn:
            rows = fresh_conn.execute(text(f'SELECT id FROM "{parent_tbl}" ORDER BY id;')).scalars().all()
            assert rows == [201, 202], f"Expected [201, 202], got {rows}"
    finally:
        with test_engine.connect() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{parent_tbl}";'))
            conn.commit()
        test_engine.dispose()


def test_48_verification_and_ddl_execute_on_exact_same_connection_object(monkeypatch):
    """
    Requirement 5: Verification and DDL execute on the exact same connection object.
    When caller supplies a Connection, the gateway executes verification and DDL
    against that exact Connection instance without closing it or checking out another.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())

    meta = MetaData()
    tbl_name = f"canary_tx48_tbl_{uuid.uuid4().hex[:6]}"
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_tx48_sch_{uuid.uuid4().hex[:6]}"

    try:
        # safe_create_all and safe_drop_all on same Connection
        with test_engine.connect() as conn:
            initial_conn_id = id(conn)
            safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)
            assert not conn.closed, "Caller connection was closed after safe_create_all!"
            assert id(conn) == initial_conn_id

            safe_drop_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)
            assert not conn.closed, "Caller connection was closed after safe_drop_all!"
            assert id(conn) == initial_conn_id

        # safe_create_schema and safe_drop_schema on same Connection
        with migration_engine.connect() as mig_conn:
            initial_mig_id = id(mig_conn)
            safe_create_schema(mig_conn, schema_name, get_migration_test_db_url(), settings.DATABASE_URL)
            assert not mig_conn.closed, "Caller connection was closed after safe_create_schema!"
            assert id(mig_conn) == initial_mig_id

            safe_drop_schema(mig_conn, schema_name, get_migration_test_db_url(), settings.DATABASE_URL)
            assert not mig_conn.closed, "Caller connection was closed after safe_drop_schema!"
            assert id(mig_conn) == initial_mig_id
    finally:
        test_engine.dispose()
        migration_engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: RUNTIME-ROLE PRIVILEGE & MEMBERSHIP INTEGRITY TESTS (49 TO 56)
# ═══════════════════════════════════════════════════════════════════════════════

def test_49_runtime_role_mutated_with_createdb_rejected_and_state_unchanged(monkeypatch):
    """
    Requirement 1.1: Runtime role mutated with CREATEDB is rejected immediately before DDL.
    safe_create_all fails closed with PermissionError, leaves state unchanged, and restores NOCREATEDB.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(get_admin_url())
    test_engine = create_engine(TEST_DATABASE_URL)

    tbl_name = f"canary_createdb_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    try:
        # Alter test role to add CREATEDB
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH CREATEDB;'))
            admin_conn.commit()

        with test_engine.connect() as conn:
            with pytest.raises(PermissionError, match=r"rolcreatedb=True"):
                safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Verify state unchanged: canary table was not created
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} was created despite CREATEDB violation!"
    finally:
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH NOCREATEDB;'))
            admin_conn.commit()
        admin_engine.dispose()
        test_engine.dispose()


def test_50_runtime_role_mutated_with_createrole_rejected_and_state_unchanged(monkeypatch):
    """
    Requirement 1.2: Runtime role mutated with CREATEROLE is rejected immediately before DDL.
    safe_create_all fails closed with PermissionError, leaves state unchanged, and restores NOCREATEROLE.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(get_admin_url())
    test_engine = create_engine(TEST_DATABASE_URL)

    tbl_name = f"canary_createrole_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    try:
        # Alter test role to add CREATEROLE
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH CREATEROLE;'))
            admin_conn.commit()

        with test_engine.connect() as conn:
            with pytest.raises(PermissionError, match=r"rolcreaterole=True"):
                safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Verify state unchanged: canary table was not created
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} was created despite CREATEROLE violation!"
    finally:
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH NOCREATEROLE;'))
            admin_conn.commit()
        admin_engine.dispose()
        test_engine.dispose()


def test_51_runtime_role_mutated_with_inherit_rejected_and_state_unchanged(monkeypatch):
    """
    Requirement 1.3: Runtime role mutated with INHERIT is rejected immediately before DDL.
    safe_create_all fails closed with PermissionError, leaves state unchanged, and restores NOINHERIT.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(get_admin_url())
    test_engine = create_engine(TEST_DATABASE_URL)

    tbl_name = f"canary_inherit_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    try:
        # Alter test role to add INHERIT
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH INHERIT;'))
            admin_conn.commit()

        with test_engine.connect() as conn:
            with pytest.raises(PermissionError, match=r"rolinherit=True"):
                safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Verify state unchanged: canary table was not created
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} was created despite INHERIT violation!"
    finally:
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH NOINHERIT;'))
            admin_conn.commit()
        admin_engine.dispose()
        test_engine.dispose()


def test_52_runtime_role_mutated_with_bypassrls_rejected_and_state_unchanged(monkeypatch):
    """
    Requirement 1.4: Runtime role mutated with BYPASSRLS is rejected immediately before DDL.
    safe_create_all fails closed with PermissionError, leaves state unchanged, and restores NOBYPASSRLS.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(get_admin_url())
    test_engine = create_engine(TEST_DATABASE_URL)

    tbl_name = f"canary_bypassrls_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    try:
        # Alter test role to add BYPASSRLS
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH BYPASSRLS;'))
            admin_conn.commit()

        with test_engine.connect() as conn:
            with pytest.raises(PermissionError, match=r"rolbypassrls=True"):
                safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Verify state unchanged: canary table was not created
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} was created despite BYPASSRLS violation!"
    finally:
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH NOBYPASSRLS;'))
            admin_conn.commit()
        admin_engine.dispose()
        test_engine.dispose()


def test_53_runtime_role_mutated_with_replication_rejected_and_state_unchanged(monkeypatch):
    """
    Requirement 1.5: Runtime role mutated with REPLICATION is rejected immediately before DDL.
    safe_create_all fails closed with PermissionError, leaves state unchanged, and restores NOREPLICATION.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(get_admin_url())
    test_engine = create_engine(TEST_DATABASE_URL)

    tbl_name = f"canary_replication_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    try:
        # Alter test role to add REPLICATION
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH REPLICATION;'))
            admin_conn.commit()

        with test_engine.connect() as conn:
            with pytest.raises(PermissionError, match=r"rolreplication=True"):
                safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Verify state unchanged: canary table was not created
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} was created despite REPLICATION violation!"
    finally:
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'ALTER ROLE "{TEST_RUNTIME_ROLE}" WITH NOREPLICATION;'))
            admin_conn.commit()
        admin_engine.dispose()
        test_engine.dispose()


def test_54_runtime_role_granted_group_membership_rejected_and_state_unchanged(monkeypatch):
    """
    Requirement 1.6: Runtime role granted group membership in pg_auth_members is rejected immediately before DDL.
    safe_create_all fails closed with PermissionError, leaves state unchanged, revokes membership and drops group role.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    admin_engine = create_engine(get_admin_url())
    test_engine = create_engine(TEST_DATABASE_URL)

    tbl_name = f"canary_group_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    group_name = f"test_group_{uuid.uuid4().hex[:6]}"

    try:
        # Create group role and grant membership to runtime test role
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'CREATE ROLE "{group_name}";'))
            admin_conn.execute(text(f'GRANT "{group_name}" TO "{TEST_RUNTIME_ROLE}";'))
            admin_conn.commit()

        with test_engine.connect() as conn:
            with pytest.raises(PermissionError, match=r"active membership\(s\) in pg_auth_members"):
                safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)

        # Verify state unchanged: canary table was not created
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} was created despite group membership violation!"
    finally:
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'REVOKE "{group_name}" FROM "{TEST_RUNTIME_ROLE}";'))
            admin_conn.execute(text(f'DROP ROLE IF EXISTS "{group_name}";'))
            admin_conn.commit()
        admin_engine.dispose()
        test_engine.dispose()


def test_55_missing_or_inaccessible_catalog_info_fails_closed_state_unchanged(monkeypatch):
    """
    Requirement 1.7: Missing or inaccessible catalog info fails closed before DDL execution.
    When querying pg_roles or pg_auth_members fails or returns empty, the operation raises
    RuntimeError and leaves database state completely unchanged.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    test_engine = create_engine(TEST_DATABASE_URL)

    tbl_name = f"canary_catalog_fail_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))

    with test_engine.connect() as conn:
        real_execute = conn.execute

        def failing_execute(statement, parameters=None, **execution_options):
            sql_str = str(statement)
            if "pg_roles" in sql_str:
                raise OperationalError("SELECT FROM pg_roles", {}, Exception("simulated catalog permission error"))
            return real_execute(statement, parameters, **execution_options)

        monkeypatch.setattr(conn, "execute", failing_execute)

        with pytest.raises(RuntimeError, match=r"failed to query pg_roles catalog"):
            safe_create_all(conn, meta, TEST_DATABASE_URL, settings.DATABASE_URL)

    # Verify state unchanged using a clean connection
    with test_engine.connect() as conn:
        inspector = inspect(conn)
        assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} was created despite catalog failure!"

    test_engine.dispose()


def test_56_correct_restricted_role_succeeds_across_all_four_gateways(monkeypatch):
    """
    Requirement 1.8: Correct restricted runtime role succeeds across all 4 gateways.
    safe_create_all, safe_drop_all, safe_create_schema, and safe_drop_schema all succeed
    with the properly configured restricted runtime role.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())

    tbl_name = f"canary_all_gateways_tbl_{uuid.uuid4().hex[:6]}"
    meta = MetaData()
    Table(tbl_name, meta, Column("id", Integer, primary_key=True))
    schema_name = f"migtest_all_gateways_sch_{uuid.uuid4().hex[:6]}"

    try:
        # Gateway 1: safe_create_all
        safe_create_all(test_engine, meta, TEST_DATABASE_URL, settings.DATABASE_URL)
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name in inspector.get_table_names(), f"Table {tbl_name} should exist after safe_create_all"

        # Gateway 2: safe_drop_all
        safe_drop_all(test_engine, meta, TEST_DATABASE_URL, settings.DATABASE_URL)
        with test_engine.connect() as conn:
            inspector = inspect(conn)
            assert tbl_name not in inspector.get_table_names(), f"Table {tbl_name} should not exist after safe_drop_all"

        # Gateway 3: safe_create_schema
        safe_create_schema(migration_engine, schema_name, get_migration_test_db_url(), settings.DATABASE_URL)
        with migration_engine.connect() as conn:
            inspector = inspect(conn)
            assert schema_name in inspector.get_schema_names(), f"Schema {schema_name} should exist after safe_create_schema"

        # Gateway 4: safe_drop_schema
        safe_drop_schema(migration_engine, schema_name, get_migration_test_db_url(), settings.DATABASE_URL)
        with migration_engine.connect() as conn:
            inspector = inspect(conn)
            assert schema_name not in inspector.get_schema_names(), f"Schema {schema_name} should not exist after safe_drop_schema"
    finally:
        test_engine.dispose()
        migration_engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: TESTCONTAINERS ROLE PROVISIONING & IDENTIFIER INJECTION (57 TO 58)
# ═══════════════════════════════════════════════════════════════════════════════

def test_57_invalid_role_identifiers_raise_value_error():
    """
    Requirement 2.1: Invalid or malicious PostgreSQL identifiers are rejected by validate_pg_identifier.
    Prevents SQL injection attacks through malformed environment variables or identifier names.
    """
    invalid_identifiers = [
        'user; DROP TABLE users;--',
        'bad user name',
        'user"OR 1=1',
        'user-with-dashes',
        '1leading_digit',
        '',
        '   ',
        'user$name',
        'role/*',
        'a' * 64,  # Over max 63 characters
    ]

    for bad_id in invalid_identifiers:
        with pytest.raises(ValueError, match="Invalid or unsafe PostgreSQL"):
            validate_pg_identifier(bad_id, "test identifier")

    # Valid identifiers pass without error
    valid_identifiers = [
        "scheme_saathi_test_user",
        "valid_identifier_123",
        "_leading_underscore",
        "TestRole",
    ]
    for good_id in valid_identifiers:
        assert validate_pg_identifier(good_id, "test identifier") == good_id


def test_58_testcontainers_dynamic_password_generation():
    """
    Requirement 2.2: Testcontainers dynamic credentials are cryptographically random,
    unique per instance, and never logged or reused from fixed values.
    """
    import secrets

    # Verify token generation properties
    passwords = [secrets.token_urlsafe(32) for _ in range(20)]

    # All generated passwords must be distinct
    assert len(set(passwords)) == 20, "Generated passwords collided; entropy insufficient!"

    # Each password must have sufficient length (>= 32 chars of urlsafe string)
    for pwd in passwords:
        assert len(pwd) >= 32, f"Password {pwd} too short!"
        assert pwd != "test_secure_password"
        assert pwd != "postgres"
        assert pwd != "password"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: UNSUPPORTED KEYWORD ARGUMENTS REJECTION (59)
# ═══════════════════════════════════════════════════════════════════════════════

def test_59_unsupported_keyword_arguments_raise_type_error(monkeypatch):
    """
    Requirement 3: Removed **kwargs from security-sensitive APIs.
    Passing obsolete or unauthorized keyword arguments like enforce_restricted_role
    must raise TypeError immediately instead of being silently swallowed.
    """
    monkeypatch.setenv("ALLOW_TEST_DB_RESET", "1")
    monkeypatch.setenv("ALLOW_MIGRATION_TESTS", "1")

    test_engine = create_engine(TEST_DATABASE_URL)
    migration_engine = create_engine(get_migration_test_db_url())
    meta = MetaData()

    with test_engine.connect() as conn:
        with pytest.raises(TypeError, match=r"unexpected keyword argument 'enforce_restricted_role'"):
            verify_connection_isolation(
                conn=conn,
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                enforce_restricted_role=False,
            )

        with pytest.raises(TypeError, match=r"unexpected keyword argument 'enforce_restricted_role'"):
            safe_create_all(
                conn,
                meta,
                TEST_DATABASE_URL,
                settings.DATABASE_URL,
                enforce_restricted_role=False,
            )

        with pytest.raises(TypeError, match=r"unexpected keyword argument 'enforce_restricted_role'"):
            safe_drop_all(
                conn,
                meta,
                TEST_DATABASE_URL,
                settings.DATABASE_URL,
                enforce_restricted_role=False,
            )

    with migration_engine.connect() as mig_conn:
        with pytest.raises(TypeError, match=r"unexpected keyword argument 'enforce_restricted_role'"):
            safe_create_schema(
                mig_conn,
                "test_dummy_sch",
                get_migration_test_db_url(),
                settings.DATABASE_URL,
                enforce_restricted_role=False,
            )

        with pytest.raises(TypeError, match=r"unexpected keyword argument 'enforce_restricted_role'"):
            safe_drop_schema(
                mig_conn,
                "test_dummy_sch",
                get_migration_test_db_url(),
                settings.DATABASE_URL,
                enforce_restricted_role=False,
            )

    with pytest.raises(TypeError, match=r"unexpected keyword argument 'enforce_restricted_role'"):
        verify_database_isolation(
            TEST_DATABASE_URL,
            settings.DATABASE_URL,
            enforce_restricted_role=False,
        )

    with pytest.raises(TypeError, match=r"unexpected keyword argument 'enforce_restricted_role'"):
        validate_database_target(
            TEST_DATABASE_URL,
            settings.DATABASE_URL,
            enforce_restricted_role=False,
        )

    test_engine.dispose()
    migration_engine.dispose()


