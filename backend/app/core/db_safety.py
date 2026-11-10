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
from contextlib import contextmanager
import os
import re
import socket
import sys
from typing import Sequence, Any, Callable

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url, URL, Engine, Connection
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
_DEFAULT_ROLE_SENTINEL = object()


def get_configured_test_runtime_role() -> str:
    """Return the single authoritative approved test runtime role name."""
    env_role = os.getenv("TEST_DB_USER", "").strip()
    return env_role if env_role else TEST_RUNTIME_ROLE


def get_dbapi_sql_composer(raw_conn: Any):
    """
    Verify the actual DBAPI connection class at runtime and return the matching
    driver-specific SQL composition module (psycopg 3 or psycopg2).
    Never mix drivers or rely on URL scheme assumptions.
    """
    conn_module = getattr(type(raw_conn), "__module__", "")
    if "psycopg2" in conn_module:
        from psycopg2 import sql as sql_mod
        return sql_mod
    elif "psycopg" in conn_module:
        from psycopg import sql as sql_mod
        return sql_mod
    else:
        raise TypeError(
            f"Unsupported or unverified DBAPI connection type '{type(raw_conn)}' ({conn_module}). "
            f"Expected a verified psycopg (v3) or psycopg2 connection."
        )


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

        # 1. Idempotently create or update the role with explicit restricted attributes using safe SQL composition
        role_exists = conn.execute(
            text("SELECT exists(SELECT 1 FROM pg_roles WHERE rolname = :role)"),
            {"role": validated_role},
        ).scalar()

        raw_conn = conn.connection.dbapi_connection
        sql = get_dbapi_sql_composer(raw_conn)
        clean_password = password.strip()
        if not role_exists:
            create_stmt = sql.SQL(
                "CREATE ROLE {u} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {p};"
            ).format(u=sql.Identifier(validated_role), p=sql.Literal(clean_password))
            conn.execute(text(create_stmt.as_string(raw_conn)))
        else:
            alter_stmt = sql.SQL(
                "ALTER ROLE {u} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {p};"
            ).format(u=sql.Identifier(validated_role), p=sql.Literal(clean_password))
            conn.execute(text(alter_stmt.as_string(raw_conn)))

        # 2. Inspect all role memberships granted to the runtime role; revoke all memberships to prevent privilege escalation
        memberships = conn.execute(
            text("""
                SELECT r.rolname
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.roleid
                JOIN pg_roles u ON u.oid = m.member
                WHERE u.rolname = :role;
            """),
            {"role": validated_role},
        ).mappings().fetchall()
        for m in memberships:
            member_name = validate_pg_identifier(m["rolname"], "role membership")
            conn.execute(text(f'REVOKE "{member_name}" FROM "{validated_role}";'))

        # Verify that zero role memberships remain after revocation
        remaining_memberships = conn.execute(
            text("""
                SELECT r.rolname
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.roleid
                JOIN pg_roles u ON u.oid = m.member
                WHERE u.rolname = :role;
            """),
            {"role": validated_role},
        ).mappings().fetchall()
        if remaining_memberships:
            rem_names = [r["rolname"] for r in remaining_memberships]
            raise RuntimeError(
                f"Role membership cleanup failed: role '{validated_role}' retains unexpected memberships: {rem_names}. "
                f"Zero role memberships required for dedicated runtime role."
            )

        # 3. Validate role attributes: must have LOGIN, must NOT have any elevated attributes, NOINHERIT
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
        if role_attrs["rolinherit"]:
            raise ValueError(f"Role '{validated_role}' has unexpected INHERIT privilege! rolinherit must be FALSE.")

        # 4. Explicitly revoke permissions from test_role on application database (scheme_saathi)
        # NOTE: NEVER REVOKE CONNECT FROM PUBLIC! Only revoke from this specific test role.
        conn.execute(text(f'REVOKE ALL ON DATABASE "{app_db}" FROM "{validated_role}";'))
        conn.execute(text(f'REVOKE CONNECT ON DATABASE "{app_db}" FROM "{validated_role}";'))
        conn.execute(text(f"ALTER ROLE \"{validated_role}\" IN DATABASE \"{app_db}\" SET session_preload_libraries = 'nonexistent_lib';"))
        try:
            conn.execute(text("REVOKE EXECUTE ON FUNCTION pg_control_system() FROM PUBLIC;"))
        except Exception:
            pass

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
                try:
                    target_admin_url = make_url(admin_url).set(database=test_db)
                    with create_engine(target_admin_url).connect() as db_conn:
                        db_conn.execute(text("REVOKE EXECUTE ON FUNCTION pg_control_system() FROM PUBLIC;"))
                        db_conn.commit()
                except Exception:
                    pass

        conn.commit()

    # 7. Final Privilege, Attribute & Membership Verification
    with engine.connect() as conn:
        verify_attrs = conn.execute(
            text(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolcanlogin, "
                "rolreplication, rolbypassrls, rolinherit "
                "FROM pg_roles WHERE rolname = :role;"
            ),
            {"role": validated_role},
        ).mappings().first()
        if not verify_attrs:
            raise RuntimeError(f"Security verification failed: role '{validated_role}' not found.")
        if (
            verify_attrs["rolsuper"]
            or verify_attrs["rolcreaterole"]
            or verify_attrs["rolcreatedb"]
            or not verify_attrs["rolcanlogin"]
            or verify_attrs["rolreplication"]
            or verify_attrs["rolbypassrls"]
            or verify_attrs["rolinherit"]
        ):
            raise RuntimeError(f"Security verification failed: role '{validated_role}' does not match required restricted attributes.")

        final_members = conn.execute(
            text("""
                SELECT r.rolname
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.roleid
                JOIN pg_roles u ON u.oid = m.member
                WHERE u.rolname = :role;
            """),
            {"role": validated_role},
        ).mappings().fetchall()
        if final_members:
            rem = [r["rolname"] for r in final_members]
            raise RuntimeError(f"Security verification failed: role '{validated_role}' retains unexpected memberships: {rem}.")

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


@contextmanager
def _ddl_transaction_scope(engine_or_conn: Engine | Connection):
    """
    Manages connection checkout and transaction ownership for DDL gateways.

    - When the gateway checks out a new connection from an Engine:
      It owns the transaction, commits on successful DDL execution,
      rolls back on failure, and closes the connection on exit.
    - When the caller supplies an existing Connection:
      - If the connection already has an active transaction (conn.in_transaction()):
        It uses a nested transaction/savepoint (conn.begin_nested()).
        On success, the savepoint is released (nested transaction committed).
        On failure, only the savepoint is rolled back.
        The caller's outer transaction is NEVER committed or rolled back.
      - If the connection does not have an active transaction:
        It starts a transaction on the connection, commits on success,
        and rolls back on failure, leaving the connection open.
    """
    if isinstance(engine_or_conn, Engine):
        with engine_or_conn.connect() as conn:
            with conn.begin():
                yield conn
    elif isinstance(engine_or_conn, Connection):
        conn = engine_or_conn
        if conn.in_transaction():
            with conn.begin_nested():
                yield conn
        else:
            with conn.begin():
                yield conn
    else:
        raise TypeError(f"Expected Engine or Connection, got {type(engine_or_conn).__name__}")


def _obtain_connection(engine_or_conn: Engine | Connection):
    """Compatibility bridge routing callers to _ddl_transaction_scope."""
    return _ddl_transaction_scope(engine_or_conn)


def verify_connection_isolation(
    conn: Connection,
    target_url: str,
    app_url: str,
    expected_purpose: str = REGULAR_TEST_PURPOSE,
    enforce_opt_in: bool = True,
    opt_in_env_vars: Sequence[str] | None = None,
    expected_role: Any = _DEFAULT_ROLE_SENTINEL,
) -> DatabaseIdentity:
    """
    Verifies that the actual live SQLAlchemy connection satisfies all isolation,
    safety, role restriction, sentinel, and application-separation guarantees.

    Restricted runtime role enforcement is MANDATORY and cannot be disabled.
    Fails closed immediately before any destructive DDL can execute.
    """
    # 0. Validate expected_role (mandatory non-empty string, cannot be administrative, must match configured runtime role)
    if expected_role is _DEFAULT_ROLE_SENTINEL:
        expected_role = get_configured_test_runtime_role()
    elif expected_role is None or not isinstance(expected_role, str) or not expected_role.strip():
        raise ValueError("expected_role must be explicitly specified (non-empty string). Missing or None expected_role is forbidden.")

    expected_role_clean = expected_role.strip()
    if expected_role_clean.lower() in ADMIN_ROLES:
        raise PermissionError(
            f"Security violation: administrative role '{expected_role_clean}' cannot be used as expected test runtime role."
        )
    configured_runtime_role = get_configured_test_runtime_role()
    if expected_role_clean != configured_runtime_role:
        raise PermissionError(
            f"Security violation: expected role '{expected_role_clean}' is not the approved, configured "
            f"test runtime role ('{configured_runtime_role}'). Arbitrary roles are forbidden."
        )

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
    target_user = (target_parsed.username or "").strip()

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

    # 4. Live Application Database Check
    app_ident = inspect_database_identity(app_url)
    if not app_ident.is_connected:
        raise RuntimeError(
            f"Application database at '{mask_url_password(app_url)}' is unreachable ({app_ident.connection_error}). "
            f"Cannot verify target isolation against active application database. Failing closed."
        )
    app_actual_db = (app_ident.current_database or app_db).strip().lower()

    # 5. Live Inspection of the ACTUAL Execution Connection (conn)
    # 5.1 current_database()
    try:
        actual_db_raw = conn.execute(text("SELECT current_database();")).scalar()
        if not actual_db_raw:
            raise RuntimeError("SELECT current_database() returned empty on actual execution connection.")
        actual_db = str(actual_db_raw).strip()
    except Exception as e:
        raise RuntimeError(f"Failed to query current_database() on actual execution connection: {e}")

    # 5.2 current_user
    user_query_error = None
    actual_user = None
    try:
        user_val = conn.execute(text("SELECT current_user;")).scalar()
        if user_val:
            actual_user = str(user_val).strip()
        else:
            user_query_error = "SELECT current_user returned empty/None on actual connection"
    except Exception as e:
        user_query_error = f"Failed to query current_user on actual connection: {e}"

    # 5.3 current_setting('is_superuser')
    superuser_query_error = None
    actual_is_superuser = False
    actual_is_superuser_verified = False
    try:
        super_val = conn.execute(text("SELECT current_setting('is_superuser');")).scalar()
        if super_val is not None:
            actual_is_superuser = (str(super_val).strip().lower() == "on")
            actual_is_superuser_verified = True
        else:
            superuser_query_error = "current_setting('is_superuser') returned None on actual connection"
    except Exception as e:
        superuser_query_error = f"Failed to query current_setting('is_superuser') on actual connection: {e}"

    # 6. Role Query Error Checks
    if user_query_error or not actual_user:
        raise RuntimeError(
            f"Destructive operation rejected: failed to query or verify target database current_user "
            f"({user_query_error or 'user is empty'}). An unverified role cannot be trusted."
        )

    if superuser_query_error or not actual_is_superuser_verified:
        raise RuntimeError(
            f"Destructive operation rejected: failed to query or verify target superuser status "
            f"({superuser_query_error or 'superuser status unverified'}). "
            f"An unverified superuser status cannot be trusted."
        )

    # 7. Mandatory Administrative & Superuser Rejection (Fail-Closed, Checked First)
    if actual_is_superuser or actual_user.lower() in ADMIN_ROLES:
        raise PermissionError(
            f"Destructive operation rejected: target connection is using administrative/superuser role "
            f"'{actual_user}'. Fallback execution must use the restricted runtime role '{expected_role_clean}'."
        )

    if target_user and target_user.lower() in ADMIN_ROLES:
        raise PermissionError(
            f"Destructive operation rejected: target URL specifies administrative role '{target_user}'. "
            f"Administrative target URLs cannot be used for destructive test operations."
        )

    # 8. User / Role mismatch against target_url
    if target_user and actual_user.lower() != target_user.lower():
        raise PermissionError(
            f"Connection mismatch: actual connection authenticated as role '{actual_user}', "
            f"but target URL specifies role '{target_user}'. DDL execution rejected."
        )

    # 9. Expected Restricted Runtime Role Check
    if actual_user != expected_role_clean:
        raise PermissionError(
            f"Destructive operation rejected: target connected as '{actual_user}', "
            f"expected restricted runtime role '{expected_role_clean}'."
        )

    # 10. Revalidate runtime-role catalog attributes and zero memberships on the actual connection
    try:
        role_record = conn.execute(
            text("""
                SELECT rolsuper, rolcreatedb, rolcreaterole, rolcanlogin,
                       rolinherit, rolreplication, rolbypassrls
                FROM pg_roles
                WHERE rolname = :rolename;
            """),
            {"rolename": actual_user},
        ).mappings().first()
    except Exception as e:
        raise RuntimeError(
            f"Destructive operation rejected: failed to query pg_roles catalog for role '{actual_user}' "
            f"on actual execution connection: {e}"
        ) from e

    if not role_record:
        raise RuntimeError(
            f"Destructive operation rejected: role '{actual_user}' not found in pg_roles catalog on actual connection."
        )

    # Check each required security attribute:
    if role_record.get("rolsuper") is not False:
        raise PermissionError(f"Security violation: runtime role '{actual_user}' has unexpected rolsuper=True attribute.")
    if role_record.get("rolcreatedb") is not False:
        raise PermissionError(f"Security violation: runtime role '{actual_user}' has unexpected rolcreatedb=True attribute.")
    if role_record.get("rolcreaterole") is not False:
        raise PermissionError(f"Security violation: runtime role '{actual_user}' has unexpected rolcreaterole=True attribute.")
    if role_record.get("rolcanlogin") is not True:
        raise PermissionError(f"Security violation: runtime role '{actual_user}' has unexpected rolcanlogin=False attribute.")
    if role_record.get("rolinherit") is not False:
        raise PermissionError(f"Security violation: runtime role '{actual_user}' has unexpected rolinherit=True attribute.")
    if role_record.get("rolreplication") is not False:
        raise PermissionError(f"Security violation: runtime role '{actual_user}' has unexpected rolreplication=True attribute.")
    if role_record.get("rolbypassrls") is not False:
        raise PermissionError(f"Security violation: runtime role '{actual_user}' has unexpected rolbypassrls=True attribute.")

    # 11. Zero memberships in pg_auth_members
    try:
        membership_count = conn.execute(
            text("""
                SELECT count(*)
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.member
                WHERE r.rolname = :rolename;
            """),
            {"rolename": actual_user},
        ).scalar()
    except Exception as e:
        raise RuntimeError(
            f"Destructive operation rejected: failed to query pg_auth_members for role '{actual_user}' "
            f"on actual execution connection: {e}"
        ) from e

    if membership_count is None:
        raise RuntimeError(f"Destructive operation rejected: membership count query returned None for role '{actual_user}'.")

    if membership_count > 0:
        raise PermissionError(
            f"Security violation: runtime role '{actual_user}' has {membership_count} active membership(s) in pg_auth_members. "
            f"Zero memberships are required."
        )

    # 10. Database Verification & Collision Checks on the actual connection
    actual_db_lower = actual_db.lower()
    if actual_db_lower != target_db:
        raise ValueError(
            f"Connection mismatch: actual connection is to database '{actual_db}', "
            f"but target URL specifies '{target_db}'. DDL execution rejected."
        )

    if actual_db_lower == app_actual_db:
        raise ValueError(
            f"Unsafe target for {expected_purpose}: Actual connection's database '{actual_db}' "
            f"matches the active application database '{app_actual_db}'! "
            f"Rejection is unconditional across all hostnames, ports, driver schemes, and proxy endpoints."
        )

    # 9. Optional catalog queries protected by SAVEPOINT (do not abort transaction on permission denied)
    actual_oid = None
    permission_denied_catalogs = False
    try:
        with conn.begin_nested():
            actual_oid = conn.execute(
                text("SELECT oid FROM pg_database WHERE datname = current_database();")
            ).scalar()
    except Exception as e:
        err_msg = str(e).lower()
        if "permission denied" in err_msg or "42501" in err_msg:
            permission_denied_catalogs = True

    actual_sysid = None
    try:
        with conn.begin_nested():
            actual_sysid = conn.execute(
                text("SELECT system_identifier FROM pg_control_system();")
            ).scalar()
    except Exception:
        permission_denied_catalogs = True

    if actual_sysid and app_ident.system_identifier:
        if actual_sysid == app_ident.system_identifier:
            if actual_oid and app_ident.db_oid and actual_oid == app_ident.db_oid:
                raise ValueError(
                    f"Unsafe target for {expected_purpose}: Actual connection shares exact physical "
                    f"cluster and OID identity with application database "
                    f"(cluster={actual_sysid}, oid={actual_oid})."
                )

    # 10. In-Database Sentinel Verification on the actual connection
    sentinel = read_sentinel_record(conn)
    if sentinel is None:
        raise ValueError(
            f"Unsafe target for {expected_purpose}: Database '{actual_db}' lacks "
            f"the required in-database disposable sentinel record ({SENTINEL_TABLE_NAME}). "
            f"A missing sentinel causes an immediate failure. Tests never automatically provision sentinels. "
            f"Administrative provisioning is required before running tests."
        )

    if not sentinel.is_disposable:
        raise ValueError(
            f"Unsafe target for {expected_purpose}: Database '{actual_db}' sentinel "
            f"explicitly marks is_disposable=FALSE. Refusing destructive operations."
        )

    if sentinel.purpose != expected_purpose:
        raise ValueError(
            f"Conflicting database identity: Target database '{actual_db}' has sentinel "
            f"purpose '{sentinel.purpose}', but current execution requires '{expected_purpose}'. "
            f"Cross-role destructive execution rejected."
        )

    if (sentinel.database_name or "").strip().lower() != actual_db_lower:
        raise ValueError(
            f"Conflicting database identity: Sentinel recorded database_name '{sentinel.database_name}' "
            f"does not match actual connected database '{actual_db}'. Failing closed."
        )

    return DatabaseIdentity(
        url=target_url,
        database_name=actual_db_lower,
        resolved_ips=target_ips,
        port=target_port,
        is_connected=True,
        current_database=actual_db,
        current_user=actual_user,
        user_query_error=user_query_error,
        is_superuser=actual_is_superuser,
        is_superuser_verified=actual_is_superuser_verified,
        superuser_query_error=superuser_query_error,
        system_identifier=actual_sysid,
        db_oid=actual_oid,
        permission_denied_catalogs=permission_denied_catalogs,
    )


def verify_database_isolation(
    target_url: str,
    app_url: str,
    expected_purpose: str = REGULAR_TEST_PURPOSE,
    enforce_opt_in: bool = True,
    opt_in_env_vars: Sequence[str] | None = None,
    expected_role: Any = _DEFAULT_ROLE_SENTINEL,
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
    4. Mandatory Restricted Runtime Role Enforcement: Verifies connected current_user against
       expected_role, validates catalog security attributes (NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
       NOINHERIT, NOREPLICATION, NOBYPASSRLS, and zero pg_auth_members memberships), and rejects
       administrative/superuser roles unconditionally.
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

    # 4. Target connectivity and mock-compatibility pre-check
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

    if target_ident.user_query_error or not target_ident.current_user:
        raise RuntimeError(
            f"Destructive operation rejected: failed to query or verify target database current_user "
            f"({target_ident.user_query_error or 'user is empty'}). An unverified role cannot be trusted."
        )
    if target_ident.superuser_query_error or not target_ident.is_superuser_verified:
        raise RuntimeError(
            f"Destructive operation rejected: failed to query or verify target superuser status "
            f"({target_ident.superuser_query_error or 'superuser status unverified'}). "
            f"An unverified superuser status cannot be trusted."
        )

    # 5. Connect and execute verification on live connection
    engine = create_engine(target_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            ident = verify_connection_isolation(
                conn=conn,
                target_url=target_url,
                app_url=app_url,
                expected_purpose=expected_purpose,
                enforce_opt_in=enforce_opt_in,
                opt_in_env_vars=opt_in_env_vars,
                expected_role=expected_role,
            )
    finally:
        engine.dispose()

    return ident


# ── Centralized Destructive Execution Gateways ─────────────────────────────────

def safe_drop_all(
    engine: Engine | Connection,
    metadata: MetaData,
    target_url: str,
    app_url: str,
    purpose: str = REGULAR_TEST_PURPOSE,
    expected_role: Any = _DEFAULT_ROLE_SENTINEL,
) -> None:
    """
    Centralized gatekeeper for metadata.drop_all().
    Enforces mandatory restricted-role verification on the actual live connection
    and executes DDL through that exact verified connection within an owned transaction scope.
    """
    with _ddl_transaction_scope(engine) as conn:
        verify_connection_isolation(
            conn=conn,
            target_url=target_url,
            app_url=app_url,
            expected_purpose=purpose,
            enforce_opt_in=True,
            expected_role=expected_role,
        )
        metadata.drop_all(bind=conn)


def safe_create_all(
    engine: Engine | Connection,
    metadata: MetaData,
    target_url: str,
    app_url: str,
    purpose: str = REGULAR_TEST_PURPOSE,
    expected_role: Any = _DEFAULT_ROLE_SENTINEL,
) -> None:
    """
    Centralized gatekeeper for metadata.create_all().
    Enforces mandatory restricted-role verification on the actual live connection
    and executes DDL through that exact verified connection within an owned transaction scope.
    """
    with _ddl_transaction_scope(engine) as conn:
        verify_connection_isolation(
            conn=conn,
            target_url=target_url,
            app_url=app_url,
            expected_purpose=purpose,
            enforce_opt_in=True,
            expected_role=expected_role,
        )
        metadata.create_all(bind=conn)


def safe_create_schema(
    engine: Engine | Connection,
    schema_name: str,
    target_url: str,
    app_url: str,
    purpose: str = MIGRATION_TEST_PURPOSE,
    expected_role: Any = _DEFAULT_ROLE_SENTINEL,
) -> None:
    """
    Centralized gatekeeper for schema creation.
    Requires verified migration test database identity and mandatory restricted-role authorization,
    executing schema creation through that exact verified connection within an owned transaction scope.
    """
    validated_schema = validate_pg_identifier(schema_name, "schema name")
    with _ddl_transaction_scope(engine) as conn:
        verify_connection_isolation(
            conn=conn,
            target_url=target_url,
            app_url=app_url,
            expected_purpose=purpose,
            enforce_opt_in=True,
            expected_role=expected_role,
        )
        conn.execute(text(f'CREATE SCHEMA "{validated_schema}";'))


def safe_drop_schema(
    engine: Engine | Connection,
    schema_name: str,
    target_url: str,
    app_url: str,
    purpose: str = MIGRATION_TEST_PURPOSE,
    expected_role: Any = _DEFAULT_ROLE_SENTINEL,
) -> None:
    """
    Centralized gatekeeper for schema drops.
    Enforces that protected system schemas (public, pg_catalog, etc.) can NEVER be dropped,
    requires the target schema to possess an approved test prefix, and executes schema
    drop through that exact verified connection within an owned transaction scope.
    """
    normalized_schema = schema_name.strip().lower()
    if normalized_schema in PROTECTED_SYSTEM_SCHEMAS:
        raise ValueError(f"Refusing to drop protected schema '{schema_name}'! Operation forbidden.")

    # Require schema to possess ephemeral test prefix
    if not any(schema_name.startswith(p) for p in ("migtest_", "control_", "test_")):
        raise ValueError(f"Refusing to drop schema '{schema_name}': not an explicitly owned test schema.")

    validated_schema = validate_pg_identifier(schema_name, "schema name")
    with _ddl_transaction_scope(engine) as conn:
        verify_connection_isolation(
            conn=conn,
            target_url=target_url,
            app_url=app_url,
            expected_purpose=purpose,
            enforce_opt_in=True,
            expected_role=expected_role,
        )
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{validated_schema}" CASCADE;'))


# ── Backward Compatibility Bridge ─────────────────────────────────────────────

def validate_database_target(
    target_url: str,
    app_url: str,
    target_label: str = "test database",
    enforce_opt_in: bool = True,
    opt_in_env_vars: Sequence[str] = REGULAR_TEST_OPT_IN_VARS,
    expected_role: Any = _DEFAULT_ROLE_SENTINEL,
) -> None:
    """Compatibility bridge routing callers to verify_database_isolation."""
    purpose = REGULAR_TEST_PURPOSE if "migration" not in target_label.lower() else MIGRATION_TEST_PURPOSE
    verify_database_isolation(
        target_url=target_url,
        app_url=app_url,
        expected_purpose=purpose,
        enforce_opt_in=enforce_opt_in,
        opt_in_env_vars=opt_in_env_vars,
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
