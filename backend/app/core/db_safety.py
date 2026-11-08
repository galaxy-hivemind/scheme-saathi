"""
Scheme Saathi — Database Target Safety Validation & Centralized Execution Gate

Establishes a fail-closed database isolation trust model ensuring destructive operations
(migrations, fixture setup/teardown, table creation/dropping, schema removal) NEVER run
against the application database or any unverified/ambiguous database.

Trust Model:
1. Verifiable Database Identity: Uses PostgreSQL live catalogs (current_database, db_oid,
   cluster system_identifier, current_user) combined with an in-database sentinel.
2. In-Database Sentinel Contract: Dedicated table `_scheme_saathi_db_sentinel` provisioned
   by administrative credentials with explicit role ('regular_test' vs 'migration_test')
   and is_disposable=TRUE. Test runtime roles are granted SELECT-only access and cannot
   modify, delete, or recreate the sentinel.
3. Restricted Test Runtime Role: Fallback test fixtures must connect as `scheme_saathi_test_user`
   (verified via current_user). Connections as postgres/superusers are rejected.
4. Fail-Closed on Ambiguity: Missing, inaccessible, conflicting, or unverified identity
   fails closed before any destructive SQL can execute. If the application database cannot
   be reached to verify isolation, the system fails closed.
5. Unconditional Connected Database Comparison: If the target's connected current_database()
   matches the application database name, it is unconditionally rejected across all
   hostnames, ports, driver schemes, and proxy endpoints.
6. Separate Authorization: Authorization environment variables (ALLOW_TEST_DB_RESET,
   ALLOW_MIGRATION_TESTS) are strictly separate from identity and never bypass verification.
7. Centralized Execution: All destructive DDL operations pass through auditable gatekeepers.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import os
import re
import socket
import sys
from typing import Sequence, Any, Callable

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url, URL, Engine
from sqlalchemy.schema import MetaData


REGULAR_TEST_PURPOSE = "regular_test"
MIGRATION_TEST_PURPOSE = "migration_test"

REGULAR_TEST_OPT_IN_VARS = (
    "ALLOW_TEST_DB_RESET",
    "ALLOW_DESTRUCTIVE_TESTS",
    "ALLOW_TEST_DB_WIPE",
)

MIGRATION_TEST_OPT_IN_VARS = (
    "ALLOW_MIGRATION_TESTS",
    "ALLOW_DESTRUCTIVE_MIGRATION_TESTS",
)

SENTINEL_TABLE_NAME = "_scheme_saathi_db_sentinel"
SENTINEL_MARKER_KEY = "scheme_saathi_test_isolation"
TEST_RUNTIME_ROLE = "scheme_saathi_test_user"
ADMIN_ROLES = {"postgres", "root", "admin", "superuser"}

DISPOSABLE_TEST_MARKERS = ("test", "disposable", "migtest", "migration_test")
PROTECTED_SYSTEM_SCHEMAS = ("public", "information_schema", "pg_catalog", "pg_toast")

IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


def validate_pg_identifier(name: str, label: str = "identifier") -> str:
    """Validate that a string is a safe, valid PostgreSQL identifier to prevent SQL injection."""
    if not name or not isinstance(name, str) or not IDENTIFIER_REGEX.match(name.strip()):
        raise ValueError(f"Invalid or unsafe PostgreSQL {label} '{name}'. Must be alphanumeric/underscores only.")
    return name.strip()


def mask_url_password(url_str: str) -> str:
    """Render a database URL safely with password hidden."""
    try:
        return normalize_db_url(url_str).render_as_string(hide_password=True)
    except Exception:
        return "[unparseable-url]"


@dataclass
class DatabaseIdentity:
    """Represents the physical identity and diagnostic status of a PostgreSQL database."""
    url: str
    database_name: str | None
    resolved_ips: set[str]
    port: int
    is_connected: bool = False
    current_database: str | None = None
    current_user: str | None = None
    user_query_error: str | None = None
    is_superuser: bool = False
    is_superuser_verified: bool = False
    superuser_query_error: str | None = None
    system_identifier: str | None = None
    db_oid: int | None = None
    permission_denied_catalogs: bool = False
    connection_error: str | None = None


@dataclass
class SentinelRecord:
    """In-database identity marker provisioned on disposable test databases."""
    marker_key: str
    purpose: str
    is_disposable: bool
    database_name: str
    provisioned_at: datetime
    cluster_system_id: str | None = None


def resolve_host_ips(host: str | None, port: int = 5432) -> set[str]:
    """
    Resolve a host to its set of IP addresses, handling localhost and loopback aliases.
    Normalizes casing and whitespace.
    """
    if not host or not host.strip():
        return {"127.0.0.1", "::1", "0.0.0.0"}
    normalized = host.strip().lower()
    if normalized in ("localhost", "0.0.0.0", "127.0.0.1", "::1", "127.0.1.1"):
        return {"127.0.0.1", "::1", "0.0.0.0"}
    try:
        addr_info = socket.getaddrinfo(normalized, port)
        return {info[4][0] for info in addr_info}
    except Exception:
        return {normalized}


def normalize_db_url(url_str: str) -> URL:
    """
    Parses and normalizes a database URL across various driver schemes.
    Handles postgresql://, postgresql+psycopg://, postgresql+psycopg2://, postgresql+asyncpg://, postgres://.
    """
    if not url_str or not url_str.strip():
        raise ValueError("Database URL cannot be empty.")
    return make_url(url_str.strip())


def inspect_database_identity(db_url: str, timeout_seconds: float = 3.0) -> DatabaseIdentity:
    """
    Inspects live PostgreSQL database catalog identity.
    Queries current_database(), current_user, is_superuser, db_oid, and system_identifier.
    Distinguishes permission limitations from actual connectivity failures.
    Does not assume physical identity verification succeeded if catalogs cannot be read.
    """
    url = normalize_db_url(db_url)
    db_name = (url.database or "").strip().lower()
    port = url.port or 5432
    ips = resolve_host_ips(url.host, port)

    identity = DatabaseIdentity(
        url=db_url,
        database_name=db_name,
        resolved_ips=ips,
        port=port,
    )

    try:
        engine = create_engine(
            db_url,
            connect_args={"connect_timeout": int(timeout_seconds)},
            pool_pre_ping=True,
        )
        with engine.connect() as conn:
            identity.is_connected = True

            # 1. current_database()
            try:
                identity.current_database = conn.execute(text("SELECT current_database();")).scalar()
            except Exception as e:
                identity.connection_error = f"Failed to query current_database(): {e}"
                return identity

            # 2. current_user and is_superuser
            try:
                user_val = conn.execute(text("SELECT current_user;")).scalar()
                if user_val:
                    identity.current_user = str(user_val).strip()
                else:
                    identity.user_query_error = "SELECT current_user returned empty/None"
            except Exception as e:
                identity.user_query_error = f"Failed to query current_user: {e}"

            try:
                super_val = conn.execute(text("SELECT current_setting('is_superuser');")).scalar()
                if super_val is not None:
                    identity.is_superuser = (str(super_val).strip().lower() == "on")
                    identity.is_superuser_verified = True
                else:
                    identity.superuser_query_error = "current_setting('is_superuser') returned None"
            except Exception as e:
                identity.superuser_query_error = f"Failed to query current_setting('is_superuser'): {e}"

            # 3. pg_database oid
            try:
                identity.db_oid = conn.execute(
                    text("SELECT oid FROM pg_database WHERE datname = current_database();")
                ).scalar()
            except Exception as e:
                err_msg = str(e).lower()
                if "permission denied" in err_msg or "42501" in err_msg:
                    identity.permission_denied_catalogs = True
                else:
                    identity.connection_error = f"Failed to query pg_database oid: {e}"

            # 4. pg_control_system()
            try:
                identity.system_identifier = conn.execute(
                    text("SELECT system_identifier FROM pg_control_system();")
                ).scalar()
            except Exception as e:
                err_msg = str(e).lower()
                if "permission denied" in err_msg or "42501" in err_msg:
                    identity.permission_denied_catalogs = True
                else:
                    identity.permission_denied_catalogs = True

        engine.dispose()
    except Exception as conn_err:
        identity.is_connected = False
        identity.connection_error = str(conn_err)

    return identity


def is_opted_in(opt_in_env_vars: Sequence[str]) -> bool:
    """Check if destructive testing has been explicitly authorized via specified environment variables."""
    for var in opt_in_env_vars:
        val = os.getenv(var, "").strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
    return False


def read_sentinel_record(conn) -> SentinelRecord | None:
    """Reads the isolation sentinel record from the connected database, if present."""
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if SENTINEL_TABLE_NAME not in table_names:
        return None

    query = text(f"""
        SELECT marker_key, purpose, is_disposable, database_name, provisioned_at, cluster_system_id
        FROM {SENTINEL_TABLE_NAME}
        WHERE marker_key = :marker_key;
    """)
    row = conn.execute(query, {"marker_key": SENTINEL_MARKER_KEY}).mappings().first()
    if not row:
        return None

    return SentinelRecord(
        marker_key=row["marker_key"],
        purpose=row["purpose"],
        is_disposable=row["is_disposable"],
        database_name=row["database_name"],
        provisioned_at=row["provisioned_at"],
        cluster_system_id=row.get("cluster_system_id"),
    )


def setup_test_roles(
    admin_url: str,
    test_role: str = TEST_RUNTIME_ROLE,
    test_password: str | None = None,
) -> None:
    """
    Administrative setup creating the dedicated test role with restricted permissions:
    - Never modifies PUBLIC permissions on scheme_saathi or any database.
    - Explicitly establishes intended role attributes: LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS.
    - Inspects and removes any administrative or unsafe role memberships (pg_auth_members).
    - Revokes CONNECT and privileges on application database (scheme_saathi) specifically for test_role.
    - Sets session_preload_libraries on scheme_saathi for test_role to guarantee connection refusal.
    - Verifies that session_preload_libraries is actually applied in pg_db_role_setting.
    - Grants connect and DDL rights on disposable test databases.
    - Parameterized and validated SQL prevents SQL injection.
    - Explicitly fails if credentials are missing or grants cannot be applied.
    """
    validated_role = validate_pg_identifier(test_role, "test role name")
    password = test_password if test_password is not None else os.getenv("TEST_DB_PASSWORD")
    if not password or not password.strip() or password.strip() in ("placeholder", "password"):
        raise ValueError(
            "Test role password must be explicitly configured via argument (--test-password) "
            "or TEST_DB_PASSWORD environment variable (cannot be empty or placeholder)."
        )

    app_db = "scheme_saathi"
    engine = create_engine(admin_url, pool_pre_ping=True)
    with engine.connect() as conn:
        # 0. Reject targeting existing superusers or administrative roles
        super_check = conn.execute(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = :role;"),
            {"role": validated_role},
        ).scalar()
        if super_check is True or validated_role.lower() in ADMIN_ROLES:
            raise ValueError(
                f"Role '{validated_role}' has unexpected SUPERUSER or administrative privilege! "
                f"Cannot use an administrative role as test runtime role."
            )

        # 1. Idempotently create or update the role with explicit restricted attributes
        role_exists = conn.execute(
            text("SELECT exists(SELECT 1 FROM pg_roles WHERE rolname = :role)"),
            {"role": validated_role},
        ).scalar()

        safe_password = password.strip().replace("'", "''")
        if not role_exists:
            conn.execute(text(
                f'CREATE ROLE "{validated_role}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                f'NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD \'{safe_password}\';'
            ))
        else:
            conn.execute(text(
                f'ALTER ROLE "{validated_role}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                f'NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD \'{safe_password}\';'
            ))

        # 2. Inspect role memberships and inherited privileges; revoke unsafe memberships
        memberships = conn.execute(
            text("""
                SELECT r.rolname, r.rolsuper, r.rolcreaterole, r.rolcreatedb
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.roleid
                JOIN pg_roles u ON u.oid = m.member
                WHERE u.rolname = :role;
            """),
            {"role": validated_role},
        ).mappings().fetchall()
        for m in memberships:
            member_name = m["rolname"]
            if m["rolsuper"] or m["rolcreaterole"] or m["rolcreatedb"] or member_name.lower() in ADMIN_ROLES:
                conn.execute(text(f'REVOKE "{member_name}" FROM "{validated_role}";'))

        # 3. Validate role attributes: must have LOGIN, must NOT have any elevated attributes
        role_attrs = conn.execute(
            text(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolcanlogin, "
                "rolreplication, rolbypassrls, rolinherit "
                "FROM pg_roles WHERE rolname = :role;"
            ),
            {"role": validated_role},
        ).mappings().first()
        if not role_attrs:
            raise RuntimeError(f"Role '{validated_role}' was not found after creation.")
        if role_attrs["rolsuper"]:
            raise ValueError(f"Role '{validated_role}' has unexpected SUPERUSER privilege! Cannot use superuser as test runtime role.")
        if role_attrs["rolcreaterole"]:
            raise ValueError(f"Role '{validated_role}' has unexpected CREATEROLE privilege! Cannot confer role creation.")
        if role_attrs["rolcreatedb"]:
            raise ValueError(f"Role '{validated_role}' has unexpected CREATEDB privilege! Cannot confer database creation.")
        if not role_attrs["rolcanlogin"]:
            raise ValueError(f"Role '{validated_role}' lacks LOGIN attribute!")
        if role_attrs["rolreplication"]:
            raise ValueError(f"Role '{validated_role}' has unexpected REPLICATION privilege!")
        if role_attrs["rolbypassrls"]:
            raise ValueError(f"Role '{validated_role}' has unexpected BYPASSRLS privilege!")

        # 4. Explicitly revoke permissions from test_role on application database (scheme_saathi)
        # NOTE: NEVER REVOKE CONNECT FROM PUBLIC! Only revoke from this specific test role.
        conn.execute(text(f'REVOKE ALL ON DATABASE "{app_db}" FROM "{validated_role}";'))
        conn.execute(text(f'REVOKE CONNECT ON DATABASE "{app_db}" FROM "{validated_role}";'))
        conn.execute(text(f"ALTER ROLE \"{validated_role}\" IN DATABASE \"{app_db}\" SET session_preload_libraries = 'nonexistent_lib';"))

        # 5. Verify that the session_preload_libraries setting was actually applied
        setting_applied = conn.execute(
            text("""
                SELECT exists(
                    SELECT 1
                    FROM pg_db_role_setting s
                    JOIN pg_database d ON d.oid = s.setdatabase
                    JOIN pg_roles r ON r.oid = s.setrole
                    WHERE d.datname = :db AND r.rolname = :role
                      AND 'session_preload_libraries=nonexistent_lib' = ANY(s.setconfig)
                );
            """),
            {"db": app_db, "role": validated_role},
        ).scalar()
        if not setting_applied:
            raise RuntimeError(f"Failed to apply session_preload_libraries lockout on database '{app_db}' for role '{validated_role}'.")

        # 6. Grant necessary privileges on disposable test databases
        for test_db, needs_schema_create in [("scheme_saathi_test", False), ("scheme_saathi_migration_test", True)]:
            db_exists = conn.execute(
                text("SELECT exists(SELECT 1 FROM pg_database WHERE datname = :db)"),
                {"db": test_db},
            ).scalar()
            if db_exists:
                conn.execute(text(f'GRANT CONNECT, TEMPORARY ON DATABASE "{test_db}" TO "{validated_role}";'))
                if needs_schema_create:
                    conn.execute(text(f'GRANT CREATE ON DATABASE "{test_db}" TO "{validated_role}";'))

        conn.commit()

    # 7. Final Privilege & Attribute Verification
    with engine.connect() as conn:
        verify_attrs = conn.execute(
            text("SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = :role;"),
            {"role": validated_role},
        ).mappings().first()
        if verify_attrs["rolsuper"] or verify_attrs["rolcreaterole"] or verify_attrs["rolcreatedb"]:
            raise RuntimeError(f"Security verification failed: role '{validated_role}' retains elevated privileges.")

    engine.dispose()


def provision_test_database_sentinel(
    target_url: str,
    app_url: str,
    purpose: str,
    enforce_opt_in: bool = True,
    grant_role: str | None = TEST_RUNTIME_ROLE,
) -> None:
    """
    Explicit administrative operation to provision the in-database disposable sentinel record.
    Strictly refuses to provision any database that matches or resolves to the application database.
    Configures SELECT-only access for the test runtime role so the test runner cannot modify it.
    """
    if purpose not in (REGULAR_TEST_PURPOSE, MIGRATION_TEST_PURPOSE):
        raise ValueError(f"Invalid sentinel purpose '{purpose}'. Must be '{REGULAR_TEST_PURPOSE}' or '{MIGRATION_TEST_PURPOSE}'.")

    # 1. Enforce opt-in
    required_vars = REGULAR_TEST_OPT_IN_VARS if purpose == REGULAR_TEST_PURPOSE else MIGRATION_TEST_OPT_IN_VARS
    if enforce_opt_in and not is_opted_in(required_vars):
        raise PermissionError(
            f"Cannot provision test database sentinel for {purpose}: explicit opt-in required. "
            f"Set one of {list(required_vars)} to '1' before provisioning."
        )

    # Validate grant_role if provided
    validated_grant_role = validate_pg_identifier(grant_role, "grant role") if grant_role else None

    # 2. Strict Application Database Non-Collision Check
    target_parsed = normalize_db_url(target_url)
    app_parsed = normalize_db_url(app_url)

    target_db = (target_parsed.database or "").strip().lower()
    app_db = (app_parsed.database or "").strip().lower()
    target_port = target_parsed.port or 5432
    app_port = app_parsed.port or 5432

    target_ips = resolve_host_ips(target_parsed.host, target_port)
    app_ips = resolve_host_ips(app_parsed.host, app_port)

    hosts_overlap = bool(target_ips & app_ips) or (
        target_parsed.host and app_parsed.host and
        target_parsed.host.strip().lower() == app_parsed.host.strip().lower()
    )

    if target_db == app_db and target_port == app_port and hosts_overlap:
        raise ValueError("Cannot provision application database as disposable test database! Operation rejected.")

    # Check disposable database name markers
    if not any(marker in target_db for marker in DISPOSABLE_TEST_MARKERS):
        raise ValueError(
            f"Cannot provision database '{target_db}' as disposable test database: "
            f"name does not contain required test markers ({DISPOSABLE_TEST_MARKERS})."
        )

    # 3. Live connection & identity check before writing sentinel
    target_ident = inspect_database_identity(target_url)
    if not target_ident.is_connected:
        raise RuntimeError(f"Cannot provision sentinel: connection to target failed ({target_ident.connection_error}).")

    target_connected_name = (target_ident.current_database or "").strip().lower()
    if target_connected_name == app_db:
        raise ValueError("Target connected database matches application database! Refusing to provision.")

    app_ident = inspect_database_identity(app_url)
    if app_ident.is_connected:
        app_connected_name = (app_ident.current_database or "").strip().lower()
        if target_connected_name == app_connected_name:
            raise ValueError("Target connected database matches application database! Refusing to provision.")
        if target_ident.system_identifier and app_ident.system_identifier:
            if target_ident.system_identifier == app_ident.system_identifier:
                if target_ident.db_oid and app_ident.db_oid and target_ident.db_oid == app_ident.db_oid:
                    raise ValueError("Target shares physical database OID with application database! Refusing to provision.")

    # 4. Write sentinel table and marker record
    engine = create_engine(target_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {SENTINEL_TABLE_NAME} (
                marker_key VARCHAR(64) PRIMARY KEY,
                purpose VARCHAR(32) NOT NULL,
                is_disposable BOOLEAN NOT NULL DEFAULT TRUE,
                database_name VARCHAR(255) NOT NULL,
                provisioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                cluster_system_id VARCHAR(64)
            );
        """))
        conn.execute(
            text(f"""
                INSERT INTO {SENTINEL_TABLE_NAME} (marker_key, purpose, is_disposable, database_name, cluster_system_id)
                VALUES (:marker_key, :purpose, TRUE, :database_name, :cluster_system_id)
                ON CONFLICT (marker_key) DO UPDATE
                SET purpose = EXCLUDED.purpose,
                    is_disposable = EXCLUDED.is_disposable,
                    database_name = EXCLUDED.database_name,
                    provisioned_at = NOW(),
                    cluster_system_id = EXCLUDED.cluster_system_id;
            """),
            {
                "marker_key": SENTINEL_MARKER_KEY,
                "purpose": purpose,
                "database_name": target_ident.current_database,
                "cluster_system_id": target_ident.system_identifier,
            },
        )

        # 5. Lock down sentinel permissions for test runtime role (SELECT-only)
        if validated_grant_role:
            role_exists = conn.execute(
                text("SELECT exists(SELECT 1 FROM pg_roles WHERE rolname = :role)"),
                {"role": validated_grant_role},
            ).scalar()
            if role_exists:
                conn.execute(text(f'REVOKE ALL ON TABLE "{SENTINEL_TABLE_NAME}" FROM "{validated_grant_role}";'))
                conn.execute(text(f'GRANT SELECT ON TABLE "{SENTINEL_TABLE_NAME}" TO "{validated_grant_role}";'))

        conn.commit()

    # Verify table privilege lockdown if role exists
    if validated_grant_role:
        with engine.connect() as conn:
            role_exists = conn.execute(
                text("SELECT exists(SELECT 1 FROM pg_roles WHERE rolname = :role)"),
                {"role": validated_grant_role},
            ).scalar()
            if role_exists:
                can_select = conn.execute(
                    text("SELECT has_table_privilege(:role, :tbl, 'SELECT')"),
                    {"role": validated_grant_role, "tbl": SENTINEL_TABLE_NAME},
                ).scalar()
                can_update = conn.execute(
                    text("SELECT has_table_privilege(:role, :tbl, 'UPDATE')"),
                    {"role": validated_grant_role, "tbl": SENTINEL_TABLE_NAME},
                ).scalar()
                if not can_select:
                    raise RuntimeError(f"Role '{validated_grant_role}' lacks SELECT on sentinel table.")
                if can_update:
                    raise RuntimeError(f"Role '{validated_grant_role}' has unsafe UPDATE on sentinel table!")

    engine.dispose()


def verify_database_isolation(
    target_url: str,
    app_url: str,
    expected_purpose: str = REGULAR_TEST_PURPOSE,
    enforce_opt_in: bool = True,
    opt_in_env_vars: Sequence[str] | None = None,
    enforce_restricted_role: bool = False,
    expected_role: str | None = None,
) -> DatabaseIdentity:
    """
    Central safety validator:
    Establishes verified database isolation, role restrictions, and authorization. Fails closed before any
    destructive action can occur.

    Proof requirements:
    1. Authorization: Explicit opt-in environment variable for this specific purpose.
    2. Live Application Database Check: Application database must be reachable during comparison;
       if unreachable, fails closed immediately.
    3. Unconditional Actual Connected Database Name Comparison: The target's connected
       current_database() cannot match the application database name under any circumstance
       (regardless of hostname, port, driver scheme, proxy, or alias).
    4. Restricted Runtime Role Enforcement: When enforce_restricted_role=True, verifies
       connected current_user against expected_role and rejects administrative/superuser roles.
    5. In-Database Sentinel Contract: Dedicated table `_scheme_saathi_db_sentinel` must exist,
       have is_disposable=TRUE, match expected_purpose, and match connected database name.
       A missing sentinel causes an immediate failure; test fixtures NEVER auto-provision it.
    """
    # 1. Authorization check
    if opt_in_env_vars is None:
        opt_in_env_vars = REGULAR_TEST_OPT_IN_VARS if expected_purpose == REGULAR_TEST_PURPOSE else MIGRATION_TEST_OPT_IN_VARS

    if enforce_opt_in and not is_opted_in(opt_in_env_vars):
        opt_names = list(opt_in_env_vars)
        example_var = opt_names[0] if opt_names else "ALLOW_TEST_DB_RESET"
        raise PermissionError(
            f"Destructive operation for {expected_purpose} rejected: explicit opt-in required. "
            f"Set one of {opt_names} to '1' before running. "
            f"Example: {example_var}=1 pytest tests/ -v"
        )

    # 2. URL parsing & scheme normalization
    target_parsed = normalize_db_url(target_url)
    app_parsed = normalize_db_url(app_url)

    target_db = (target_parsed.database or "").strip().lower()
    app_db = (app_parsed.database or "").strip().lower()
    target_port = target_parsed.port or 5432
    app_port = app_parsed.port or 5432

    if not target_db:
        raise ValueError(f"Invalid target URL for {expected_purpose}: database name is missing.")

    # 3. Host and IP resolution
    target_ips = resolve_host_ips(target_parsed.host, target_port)
    app_ips = resolve_host_ips(app_parsed.host, app_port)

    hosts_overlap = bool(target_ips & app_ips) or (
        target_parsed.host and app_parsed.host and
        target_parsed.host.strip().lower() == app_parsed.host.strip().lower()
    )
    same_db_name = (target_db == app_db)
    same_port = (target_port == app_port)

    if same_db_name and same_port and hosts_overlap:
        raise ValueError(
            f"Unsafe target for {expected_purpose}: Target URL points to the active application database "
            f"'{target_parsed.database}' on host '{target_parsed.host}:{target_port}' "
            f"(resolved IPs: {target_ips & app_ips}). Operation rejected."
        )

    # 4. Live Application Database Identity Check
    app_ident = inspect_database_identity(app_url)
    if not app_ident.is_connected:
        raise RuntimeError(
            f"Application database at '{mask_url_password(app_url)}' is unreachable ({app_ident.connection_error}). "
            f"Cannot verify target isolation against active application database. Failing closed."
        )

    app_actual_db = (app_ident.current_database or app_db).strip().lower()

    # 5. Live Connected Target PostgreSQL Identity Inspection
    target_ident = inspect_database_identity(target_url)
    if not target_ident.is_connected:
        if same_db_name:
            raise ValueError(
                f"Unsafe target for {expected_purpose}: Database name '{target_db}' matches application database, "
                f"and connection verification failed ({target_ident.connection_error}). Failing closed."
            )
        raise RuntimeError(
            f"Cannot verify {expected_purpose} safety: connection to target failed ({target_ident.connection_error})."
        )

    target_actual_db = (target_ident.current_database or "").strip().lower()

    # 6. Unconditional Connected Database Name Comparison
    if target_actual_db == app_actual_db:
        raise ValueError(
            f"Unsafe target for {expected_purpose}: Connected database name '{target_ident.current_database}' "
            f"matches the active application database name '{app_ident.current_database}'! "
            f"Rejection is unconditional across all hostnames, ports, driver schemes, and proxy endpoints."
        )

    # 7. Restricted Runtime Role Enforcement (Fail-Closed)
    if enforce_restricted_role:
        if not expected_role or not isinstance(expected_role, str) or not expected_role.strip():
            raise ValueError(
                "Restricted role enforcement failed: expected_role must be explicitly specified "
                "when enforce_restricted_role=True. Missing expected_role is forbidden."
            )
        expected_role_clean = expected_role.strip()

        # Require a non-empty, successfully verified current_user
        if target_ident.user_query_error or not target_ident.current_user:
            raise RuntimeError(
                f"Destructive operation rejected: failed to query or verify target database current_user "
                f"({target_ident.user_query_error or 'user is empty'}). An unverified role cannot be trusted."
            )

        # Require a successfully verified superuser status
        if target_ident.superuser_query_error or not target_ident.is_superuser_verified:
            raise RuntimeError(
                f"Destructive operation rejected: failed to query or verify target superuser status "
                f"({target_ident.superuser_query_error or 'superuser status unverified'}). "
                f"An unverified superuser status cannot be trusted."
            )

        # Reject superusers and administrative roles
        if target_ident.is_superuser or target_ident.current_user.lower() in ADMIN_ROLES:
            raise PermissionError(
                f"Destructive operation rejected: target connection is using administrative/superuser role "
                f"'{target_ident.current_user}'. Fallback execution must use the restricted runtime role '{expected_role_clean}'."
            )

        # Require exact equality between actual current_user and expected_role
        if target_ident.current_user != expected_role_clean:
            raise PermissionError(
                f"Destructive operation rejected: target connected as '{target_ident.current_user}', "
                f"expected restricted runtime role '{expected_role_clean}'."
            )

    # 8. Physical Cluster and Catalog Comparison
    if target_ident.system_identifier and app_ident.system_identifier:
        if target_ident.system_identifier == app_ident.system_identifier:
            if target_ident.db_oid and app_ident.db_oid and target_ident.db_oid == app_ident.db_oid:
                raise ValueError(
                    f"Unsafe target for {expected_purpose}: Connected database shares exact physical "
                    f"cluster and OID identity with application database "
                    f"(cluster={target_ident.system_identifier}, oid={target_ident.db_oid})."
                )

    # 9. In-Database Sentinel Verification
    engine = create_engine(target_url, pool_pre_ping=True)
    with engine.connect() as conn:
        sentinel = read_sentinel_record(conn)
    engine.dispose()

    if sentinel is None:
        raise ValueError(
            f"Unsafe target for {expected_purpose}: Database '{target_ident.current_database}' lacks "
            f"the required in-database disposable sentinel record ({SENTINEL_TABLE_NAME}). "
            f"A missing sentinel causes an immediate failure. Tests never automatically provision sentinels. "
            f"Administrative provisioning is required before running tests."
        )

    if not sentinel.is_disposable:
        raise ValueError(
            f"Unsafe target for {expected_purpose}: Database '{target_ident.current_database}' sentinel "
            f"explicitly marks is_disposable=FALSE. Refusing destructive operations."
        )

    if sentinel.purpose != expected_purpose:
        raise ValueError(
            f"Conflicting database identity: Target database '{target_ident.current_database}' has sentinel "
            f"purpose '{sentinel.purpose}', but current execution requires '{expected_purpose}'. "
            f"Cross-role destructive execution rejected."
        )

    if (sentinel.database_name or "").strip().lower() != target_actual_db:
        raise ValueError(
            f"Conflicting database identity: Sentinel recorded database_name '{sentinel.database_name}' "
            f"does not match actual connected database '{target_ident.current_database}'. Failing closed."
        )

    return target_ident


# ── Centralized Destructive Execution Gateways ─────────────────────────────────

def safe_drop_all(
    engine: Engine,
    metadata: MetaData,
    target_url: str,
    app_url: str,
    purpose: str = REGULAR_TEST_PURPOSE,
    enforce_restricted_role: bool = False,
    expected_role: str | None = None,
) -> None:
    """
    Centralized gatekeeper for metadata.drop_all().
    Re-verifies identity and authorization immediately prior to dropping tables.
    """
    verify_database_isolation(
        target_url,
        app_url,
        expected_purpose=purpose,
        enforce_restricted_role=enforce_restricted_role,
        expected_role=expected_role,
    )
    metadata.drop_all(bind=engine)


def safe_create_all(
    engine: Engine,
    metadata: MetaData,
    target_url: str,
    app_url: str,
    purpose: str = REGULAR_TEST_PURPOSE,
    enforce_restricted_role: bool = False,
    expected_role: str | None = None,
) -> None:
    """
    Centralized gatekeeper for metadata.create_all().
    Verifies identity and authorization immediately prior to creating tables.
    """
    verify_database_isolation(
        target_url,
        app_url,
        expected_purpose=purpose,
        enforce_restricted_role=enforce_restricted_role,
        expected_role=expected_role,
    )
    metadata.create_all(bind=engine)


def safe_create_schema(
    engine: Engine,
    schema_name: str,
    target_url: str,
    app_url: str,
    purpose: str = MIGRATION_TEST_PURPOSE,
    enforce_restricted_role: bool = False,
    expected_role: str | None = None,
) -> None:
    """
    Centralized gatekeeper for schema creation.
    Requires verified migration test database identity and authorization.
    """
    validated_schema = validate_pg_identifier(schema_name, "schema name")
    verify_database_isolation(
        target_url,
        app_url,
        expected_purpose=purpose,
        enforce_restricted_role=enforce_restricted_role,
        expected_role=expected_role,
    )
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{validated_schema}";'))
        conn.commit()


def safe_drop_schema(
    engine: Engine,
    schema_name: str,
    target_url: str,
    app_url: str,
    purpose: str = MIGRATION_TEST_PURPOSE,
    enforce_restricted_role: bool = False,
    expected_role: str | None = None,
) -> None:
    """
    Centralized gatekeeper for schema drops.
    Enforces that protected system schemas (public, pg_catalog, etc.) can NEVER be dropped,
    and requires the target schema to possess an approved test prefix.
    """
    normalized_schema = schema_name.strip().lower()
    if normalized_schema in PROTECTED_SYSTEM_SCHEMAS:
        raise ValueError(f"Refusing to drop protected schema '{schema_name}'! Operation forbidden.")

    # Require schema to possess ephemeral test prefix
    if not any(schema_name.startswith(p) for p in ("migtest_", "control_", "test_")):
        raise ValueError(f"Refusing to drop schema '{schema_name}': not an explicitly owned test schema.")

    validated_schema = validate_pg_identifier(schema_name, "schema name")
    verify_database_isolation(
        target_url,
        app_url,
        expected_purpose=purpose,
        enforce_restricted_role=enforce_restricted_role,
        expected_role=expected_role,
    )
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{validated_schema}" CASCADE;'))
        conn.commit()


# ── Backward Compatibility Bridge ─────────────────────────────────────────────

def validate_database_target(
    target_url: str,
    app_url: str,
    target_label: str = "test database",
    enforce_opt_in: bool = True,
    opt_in_env_vars: Sequence[str] = REGULAR_TEST_OPT_IN_VARS,
    enforce_restricted_role: bool = False,
    expected_role: str | None = None,
) -> None:
    """Compatibility bridge routing callers to verify_database_isolation."""
    purpose = REGULAR_TEST_PURPOSE if "migration" not in target_label.lower() else MIGRATION_TEST_PURPOSE
    verify_database_isolation(
        target_url=target_url,
        app_url=app_url,
        expected_purpose=purpose,
        enforce_opt_in=enforce_opt_in,
        opt_in_env_vars=opt_in_env_vars,
        enforce_restricted_role=enforce_restricted_role,
        expected_role=expected_role,
    )


# ── CLI Entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scheme Saathi Database Safety & Sentinel Provisioning Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    prov_parser = subparsers.add_parser("provision", help="Provision in-database disposable sentinel")
    prov_parser.add_argument("--purpose", choices=[REGULAR_TEST_PURPOSE, MIGRATION_TEST_PURPOSE], required=True)
    prov_parser.add_argument("--target-url", default=None, help="Target test database URL")
    prov_parser.add_argument("--app-url", default=None, help="Application database URL")
    prov_parser.add_argument("--grant-role", default=TEST_RUNTIME_ROLE, help="Test runtime role to grant read-only access")

    role_parser = subparsers.add_parser("setup-roles", help="Setup test runtime role with restricted permissions")
    role_parser.add_argument("--admin-url", default=None, help="PostgreSQL admin URL")
    role_parser.add_argument("--test-role", default=TEST_RUNTIME_ROLE, help="Name of test role to configure")
    role_parser.add_argument("--test-password", default=None, help="Password for test role")

    args = parser.parse_args()

    if args.command == "provision":
        target = args.target_url
        if not target:
            if args.purpose == REGULAR_TEST_PURPOSE:
                target = os.getenv("TEST_DATABASE_URL")
                if not target:
                    pwd = os.getenv("TEST_DB_PASSWORD")
                    if pwd and pwd.strip():
                        target = f"postgresql://{args.grant_role or TEST_RUNTIME_ROLE}:{pwd.strip()}@localhost:5432/scheme_saathi_test"
            else:
                target = os.getenv("MIGRATION_TEST_DB_URL")
                if not target:
                    pwd = os.getenv("TEST_DB_PASSWORD")
                    if pwd and pwd.strip():
                        target = f"postgresql://{args.grant_role or TEST_RUNTIME_ROLE}:{pwd.strip()}@localhost:5432/scheme_saathi_migration_test"

        if not target:
            print(
                "Error: Target database URL must be provided via --target-url, or configured via "
                "TEST_DATABASE_URL / MIGRATION_TEST_DB_URL / TEST_DB_PASSWORD environment variables.",
                file=sys.stderr,
            )
            sys.exit(1)

        app = args.app_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/scheme_saathi")

        print(f"Provisioning disposable sentinel for {args.purpose} on: {mask_url_password(target)}")
        provision_test_database_sentinel(target, app, purpose=args.purpose, enforce_opt_in=True, grant_role=args.grant_role)
        print("Sentinel provisioned successfully.")
    elif args.command == "setup-roles":
        admin = args.admin_url or os.getenv("ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
        pwd = args.test_password or os.getenv("TEST_DB_PASSWORD")
        if not pwd:
            print("Error: Password must be provided via --test-password or TEST_DB_PASSWORD env var.", file=sys.stderr)
            sys.exit(1)
        print(f"Setting up restricted test role '{args.test_role}' on: {mask_url_password(admin)}")
        setup_test_roles(admin, test_role=args.test_role, test_password=pwd)
        print("Test role configured successfully.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
