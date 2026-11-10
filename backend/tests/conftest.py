"""
Pytest fixtures for Scheme Saathi test suite.
Configures isolated test database sessions with support for both:
1. Ephemeral Testcontainers PostgreSQL container (when USE_TESTCONTAINERS=1).
2. Dedicated separately provisioned PostgreSQL test database with restricted role (default fallback).

Strictly enforces:
- Fallback must connect using the restricted runtime role (scheme_saathi_test_user).
- Rejects administrative or superuser connections for fallback execution.
- Unit tests run completely free of database fixtures and opt-in requirements.
- Integration tests require explicit opt-in (ALLOW_TEST_DB_RESET=1).
- Non-authorizing: NEVER auto-provisions sentinels inside test fixtures. Missing sentinel fails immediately.
- Re-validates target safety and connected role immediately before teardown and refuses to drop if setup failed.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.db_safety import (
    safe_drop_all,
    safe_create_all,
    verify_database_isolation,
    provision_test_database_sentinel,
    REGULAR_TEST_PURPOSE,
    REGULAR_TEST_OPT_IN_VARS,
    TEST_RUNTIME_ROLE,
    ADMIN_ROLES,
)
from app.main import app as fastapi_app
from app.database.base import Base
from app.database.dependencies import get_db
import app.models  # noqa: F401

USE_TESTCONTAINERS = os.getenv("USE_TESTCONTAINERS", "").strip().lower() in ("1", "true", "yes")

TEST_DB_USER = os.getenv("TEST_DB_USER", TEST_RUNTIME_ROLE)
TEST_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
TEST_DB_PORT = os.getenv("TEST_DB_PORT", "5432")
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "scheme_saathi_test")

_test_container = None
_container_runtime_url = None
_active_test_engine = None
_active_session_factory = None


def get_test_database_url() -> str:
    """
    Return the active test database URL (from Testcontainers if active, else fallback URL).
    Fails immediately with a clear configuration error if required fallback credentials are absent.
    Never constructs or returns a URL with an empty, default, or placeholder password.
    """
    global _test_container, _container_runtime_url
    use_testcontainers = USE_TESTCONTAINERS or (os.getenv("USE_TESTCONTAINERS", "").strip().lower() in ("1", "true", "yes"))
    if use_testcontainers:
        if _container_runtime_url is not None:
            return _container_runtime_url

        if _test_container is None:
            os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"
            try:
                from testcontainers.community.postgres import PostgresContainer
            except ImportError:
                from testcontainers.postgres import PostgresContainer

            try:
                _test_container = PostgresContainer("postgres:16-alpine", driver="psycopg")
                _test_container.start()
                admin_url = _test_container.get_connection_url()
                if not admin_url.startswith("postgresql+psycopg://"):
                    admin_url = admin_url.replace("postgresql+psycopg2://", "postgresql+psycopg://").replace("postgresql://", "postgresql+psycopg://")

                # 1. Administratively provision restricted runtime role inside disposable container
                from urllib.parse import quote_plus
                from app.core.db_safety import (
                    normalize_db_url,
                    validate_pg_identifier,
                    get_dbapi_sql_composer,
                    provision_test_database_sentinel,
                )
                import secrets

                validated_user = validate_pg_identifier(TEST_DB_USER, "test database user")
                parsed = normalize_db_url(admin_url)
                container_db = parsed.database or "test"
                validated_db = validate_pg_identifier(container_db, "database name")

                # Generate a cryptographically random password for this disposable container instance
                container_password = secrets.token_urlsafe(32)

                admin_engine = create_engine(admin_url, pool_pre_ping=True)
                with admin_engine.connect() as conn:
                    raw_conn = conn.connection.dbapi_connection
                    sql = get_dbapi_sql_composer(raw_conn)

                    create_role_stmt = sql.SQL(
                        "CREATE ROLE {user} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {pwd};"
                    ).format(
                        user=sql.Identifier(validated_user),
                        pwd=sql.Literal(container_password),
                    )
                    grant_db_stmt = sql.SQL(
                        "GRANT CONNECT, TEMPORARY, CREATE ON DATABASE {db} TO {user};"
                    ).format(
                        db=sql.Identifier(validated_db),
                        user=sql.Identifier(validated_user),
                    )
                    grant_schema_stmt = sql.SQL(
                        "GRANT ALL ON SCHEMA public TO {user};"
                    ).format(
                        user=sql.Identifier(validated_user),
                    )

                    conn.execute(text(create_role_stmt.as_string(raw_conn)))
                    conn.execute(text(grant_db_stmt.as_string(raw_conn)))
                    conn.execute(text(grant_schema_stmt.as_string(raw_conn)))
                    conn.commit()

                # 2. Administratively provision sentinel inside disposable container
                provision_test_database_sentinel(
                    target_url=admin_url,
                    app_url=settings.DATABASE_URL,
                    purpose=REGULAR_TEST_PURPOSE,
                    enforce_opt_in=False,
                    grant_role=validated_user,
                )
                admin_engine.dispose()

                safe_pwd = quote_plus(container_password)
                _container_runtime_url = f"postgresql+psycopg://{validated_user}:{safe_pwd}@{parsed.host}:{parsed.port or 5432}/{container_db}"
                del container_password
                return _container_runtime_url
            except Exception:
                if _test_container is not None:
                    try:
                        _test_container.stop()
                    except Exception:
                        pass
                    _test_container = None
                _container_runtime_url = None
                raise

    # Fallback mode: require explicit credentials
    from urllib.parse import quote_plus
    from app.core.db_safety import normalize_db_url

    explicit_url = os.getenv("TEST_DATABASE_URL")
    if explicit_url:
        parsed = normalize_db_url(explicit_url)
        pwd = parsed.password
        if not pwd or not pwd.strip() or pwd.strip() in ("placeholder", "password"):
            raise ValueError(
                "TEST_DATABASE_URL was provided without valid credentials. "
                "An explicit, non-placeholder password is required for fallback execution."
            )
        return explicit_url

    pwd = os.getenv("TEST_DB_PASSWORD")
    if not pwd or not pwd.strip() or pwd.strip() in ("placeholder", "password"):
        raise ValueError(
            "Missing required fallback test database credentials: TEST_DB_PASSWORD must be "
            "explicitly configured in the environment for fallback execution. "
            "Example: TEST_DB_PASSWORD=<password> ALLOW_TEST_DB_RESET=1 pytest tests/ -v"
        )

    safe_pwd = quote_plus(pwd.strip())
    return f"postgresql://{TEST_DB_USER}:{safe_pwd}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"


def get_test_engine():
    """Return the active SQLAlchemy engine for test execution."""
    global _active_test_engine
    if _active_test_engine is None:
        url = get_test_database_url()
        _active_test_engine = create_engine(url, pool_pre_ping=True)
    return _active_test_engine


def get_session_factory():
    """Return the sessionmaker bound to the active test engine."""
    global _active_session_factory
    if _active_session_factory is None:
        _active_session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_test_engine(),
            expire_on_commit=False,
        )
    return _active_session_factory


def __getattr__(name: str):
    """Provide lazy access to module-level properties so unit tests never trigger eager DB setup."""
    if name == "TEST_DATABASE_URL":
        return get_test_database_url()
    if name == "test_engine":
        return get_test_engine()
    if name == "TestingSessionLocal":
        return get_session_factory()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


@pytest.fixture(scope="session")
def setup_test_db():
    """
    Session fixture that sets up and tears down the disposable test database.
    Requires explicit opt-in (ALLOW_TEST_DB_RESET=1) before running destructive drop_all and create_all.
    Re-validates target safety immediately before teardown and refuses to drop tables if setup failed.
    Verifies that fallback execution connects using the restricted runtime role, rejecting superusers.
    Does NOT auto-provision sentinels: a missing sentinel causes immediate failure.
    NOTE: Not autouse=True so unit tests can run without database authorization or fixtures.
    """
    # 1. Require explicit authorization before doing anything
    is_authorized = any(
        os.getenv(v, "").strip().lower() in ("1", "true", "yes", "on")
        for v in REGULAR_TEST_OPT_IN_VARS
    )
    if not is_authorized:
        raise PermissionError(
            f"Destructive operation on regular test database rejected: explicit opt-in required. "
            f"Set one of {list(REGULAR_TEST_OPT_IN_VARS)} to '1' before running. "
            f"Example: {REGULAR_TEST_OPT_IN_VARS[0]}=1 pytest tests/ -v"
        )

    active_url = get_test_database_url()
    active_engine = get_test_engine()

    # 2. Check role restriction uniformly (reject superusers/admins)
    with active_engine.connect() as conn:
        connected_user = conn.execute(text("SELECT current_user;")).scalar()
        is_super = conn.execute(text("SELECT current_setting('is_superuser');")).scalar()
    if is_super == "on" or (connected_user and connected_user.lower() in ADMIN_ROLES):
        raise PermissionError(
            f"Test fixture execution with administrative/superuser role '{connected_user}' is forbidden. "
            f"Test execution must use the restricted runtime role '{TEST_DB_USER}'."
        )
    if connected_user != TEST_DB_USER:
        raise PermissionError(
            f"Expected test execution to connect as restricted role '{TEST_DB_USER}', "
            f"but connected as '{connected_user}'."
        )

    # 3. Verify target database isolation (fails immediately if sentinel is missing or target unsafe)
    verify_database_isolation(
        target_url=active_url,
        app_url=settings.DATABASE_URL,
        expected_purpose=REGULAR_TEST_PURPOSE,
        enforce_opt_in=True,
        expected_role=TEST_DB_USER,
    )

    # 4. Perform centralized safe setup
    setup_succeeded = False
    try:
        safe_drop_all(
            active_engine,
            Base.metadata,
            active_url,
            settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            expected_role=TEST_DB_USER,
        )
        safe_create_all(
            active_engine,
            Base.metadata,
            active_url,
            settings.DATABASE_URL,
            purpose=REGULAR_TEST_PURPOSE,
            expected_role=TEST_DB_USER,
        )
        setup_succeeded = True
        yield
    finally:
        # 5. Only teardown if setup actually succeeded (do not drop if setup failed)
        if setup_succeeded:
            safe_drop_all(
                active_engine,
                Base.metadata,
                active_url,
                settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
                expected_role=TEST_DB_USER,
            )

        # Stop Testcontainers container if one was started, and dispose active engine
        global _test_container, _container_runtime_url, _active_test_engine, _active_session_factory
        if _active_test_engine is not None:
            _active_test_engine.dispose()
            _active_test_engine = None
        _active_session_factory = None

        if _test_container is not None:
            _test_container.stop()
            _test_container = None
            _container_runtime_url = None


@pytest.fixture
def db_session(setup_test_db):
    """Provides a clean database session per test with rollback/cleanup."""
    engine = get_test_engine()
    factory = get_session_factory()
    connection = engine.connect()
    transaction = connection.begin()
    session = factory(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Provides a TestClient with get_db dependency overridden to the test transaction."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
