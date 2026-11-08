"""
Scheme Saathi — Database Target Safety Validation

Provides multi-layer validation ensuring destructive database operations (migrations,
fixture setup/teardown, table creation/dropping) NEVER run against the application database.

Safety Checks:
1. Explicit Opt-In Enforcement (ALLOW_TEST_DB_RESET vs ALLOW_MIGRATION_TESTS)
2. Driver Scheme Normalization (postgresql://, postgresql+psycopg://, postgresql+psycopg2://, etc.)
3. Hostname Alias Normalization & Network IP Resolution (localhost, 127.0.0.1, ::1, 0.0.0.0)
4. Port & Database Name Equivalence Detection
5. Live PostgreSQL Database & Cluster Identity Verification (current_database, system_identifier, db_oid)
6. Fail-Closed on Ambiguity (distinguishing permission limitations from connectivity failures)
"""
from dataclasses import dataclass
import os
import socket
from typing import Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url, URL


REGULAR_TEST_OPT_IN_VARS = (
    "ALLOW_TEST_DB_RESET",
    "ALLOW_DESTRUCTIVE_TESTS",
    "ALLOW_TEST_DB_WIPE",
)

MIGRATION_TEST_OPT_IN_VARS = (
    "ALLOW_MIGRATION_TESTS",
    "ALLOW_DESTRUCTIVE_MIGRATION_TESTS",
)

DISPOSABLE_TEST_MARKERS = ("test", "disposable", "migtest", "migration_test")


@dataclass
class DatabaseIdentity:
    """Represents the physical identity and diagnostic status of a PostgreSQL database."""
    url: str
    database_name: str | None
    resolved_ips: set[str]
    port: int
    is_connected: bool = False
    current_database: str | None = None
    system_identifier: str | None = None
    db_oid: int | None = None
    permission_denied_catalogs: bool = False
    connection_error: str | None = None


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

            # 2. pg_database oid
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

            # 3. pg_control_system()
            try:
                identity.system_identifier = conn.execute(
                    text("SELECT system_identifier FROM pg_control_system();")
                ).scalar()
            except Exception as e:
                err_msg = str(e).lower()
                if "permission denied" in err_msg or "42501" in err_msg:
                    identity.permission_denied_catalogs = True
                else:
                    # Non-fatal if user is not superuser, but records permission limitation
                    identity.permission_denied_catalogs = True

        engine.dispose()
    except Exception as conn_err:
        identity.is_connected = False
        identity.connection_error = str(conn_err)

    return identity


def is_opted_in(opt_in_env_vars: Sequence[str] = REGULAR_TEST_OPT_IN_VARS) -> bool:
    """Check if destructive testing has been explicitly authorized via specified environment variables."""
    for var in opt_in_env_vars:
        val = os.getenv(var, "").strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
    return False


def validate_database_target(
    target_url: str,
    app_url: str,
    target_label: str = "test database",
    enforce_opt_in: bool = True,
    opt_in_env_vars: Sequence[str] = REGULAR_TEST_OPT_IN_VARS,
) -> None:
    """
    Robust database target safety guard:
    1. Enforces explicit opt-in via environment variables (never automatically enabled).
    2. Detects equivalent URLs across driver schemes and host aliases.
    3. Resolves network IPs to compare real destinations.
    4. Connects to test and app databases to compare physical cluster identity (system_identifier) and DB OID.
    5. Fails closed when targets remain ambiguous due to connectivity or permission limitations.
    """
    # 1. Opt-in check (explicit requirement)
    if enforce_opt_in and not is_opted_in(opt_in_env_vars):
        opt_names = list(opt_in_env_vars)
        example_var = opt_names[0] if opt_names else "ALLOW_TEST_DB_RESET"
        raise PermissionError(
            f"Destructive operation on {target_label} rejected: explicit opt-in required. "
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
        raise ValueError(f"Invalid {target_label} URL: database name is missing.")

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
            f"Unsafe {target_label} target: Target URL points to the active application database "
            f"'{target_parsed.database}' on host '{target_parsed.host}:{target_port}' "
            f"(resolved IPs: {target_ips & app_ips}). Operation rejected."
        )

    # 4. Live connected PostgreSQL identity inspection
    target_ident = inspect_database_identity(target_url)

    if not target_ident.is_connected:
        if same_db_name:
            raise ValueError(
                f"Unsafe {target_label} target: Database name '{target_db}' matches application database, "
                f"and connection verification failed ({target_ident.connection_error}). Failing closed."
            )
        raise RuntimeError(
            f"Cannot verify {target_label} safety: connection to target failed ({target_ident.connection_error})."
        )

    # Check connected database name against application database
    if target_ident.current_database and target_ident.current_database.strip().lower() == app_db:
        if same_port and hosts_overlap:
            raise ValueError(
                f"Unsafe {target_label} target: Connected database '{target_ident.current_database}' "
                f"matches the active application database on '{target_parsed.host}:{target_port}'."
            )

    # Compare against live application database if reachable
    app_ident = inspect_database_identity(app_url)
    if app_ident.is_connected:
        # Both connected: compare physical identity
        if target_ident.system_identifier and app_ident.system_identifier:
            if target_ident.system_identifier == app_ident.system_identifier:
                # Same PostgreSQL cluster
                if target_ident.db_oid and app_ident.db_oid and target_ident.db_oid == app_ident.db_oid:
                    raise ValueError(
                        f"Unsafe {target_label} target: Connected database shares exact physical "
                        f"cluster and OID identity with application database "
                        f"(cluster={target_ident.system_identifier}, oid={target_ident.db_oid})."
                    )
                if (target_ident.current_database or "").lower() == (app_ident.current_database or "").lower():
                    raise ValueError(
                        f"Unsafe {target_label} target: Connected database matches application database "
                        f"on cluster '{target_ident.system_identifier}'."
                    )
        elif target_ident.permission_denied_catalogs or app_ident.permission_denied_catalogs:
            # Catalog read restricted. Fail closed if database names match
            if (target_ident.current_database or "").lower() == (app_ident.current_database or "").lower():
                raise ValueError(
                    f"Unsafe {target_label} target: Database name matches application database, "
                    f"and physical cluster identity could not be verified due to restricted catalog permissions. "
                    f"Failing closed."
                )
    else:
        # App database is unreachable. If database names match on overlapping network, fail closed
        if same_db_name and hosts_overlap:
            raise ValueError(
                f"Unsafe {target_label} target: Database name '{target_db}' matches application database, "
                f"and application database is currently unreachable ({app_ident.connection_error}). "
                f"Cannot prove physical separation. Failing closed."
            )
