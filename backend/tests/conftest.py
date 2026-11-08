"""
Pytest fixtures for Scheme Saathi test suite.
Configures isolated test database sessions against the local PostgreSQL test instance.
Enforces multi-layer safety validation, in-database sentinel verification, and explicit opt-in.
"""
import os
import pytest
from sqlalchemy import create_engine
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
)
from app.main import app as fastapi_app
from app.database.base import Base
from app.database.dependencies import get_db
import app.models  # noqa: F401

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test",
)

test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Session fixture that sets up and tears down the disposable test database.
    Strictly requires explicit opt-in (ALLOW_TEST_DB_RESET=1, ALLOW_DESTRUCTIVE_TESTS=1,
    or ALLOW_TEST_DB_WIPE=1) before running destructive drop_all and create_all.
    Re-validates target safety immediately before teardown and refuses to drop
    tables if setup failed.
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

    # 2. Ensure test database sentinel is provisioned if valid disposable database
    try:
        verify_database_isolation(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
        )
    except ValueError as e:
        if "lacks the required in-database disposable sentinel record" in str(e):
            # Target is a confirmed non-application database needing sentinel initialization
            provision_test_database_sentinel(
                target_url=TEST_DATABASE_URL,
                app_url=settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
                enforce_opt_in=True,
            )
        else:
            raise

    # 3. Perform centralized safe setup
    setup_succeeded = False
    try:
        safe_drop_all(test_engine, Base.metadata, TEST_DATABASE_URL, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)
        safe_create_all(test_engine, Base.metadata, TEST_DATABASE_URL, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)
        setup_succeeded = True
        yield
    finally:
        # 4. Only teardown if setup actually succeeded (do not drop if setup failed)
        if setup_succeeded:
            safe_drop_all(test_engine, Base.metadata, TEST_DATABASE_URL, settings.DATABASE_URL, purpose=REGULAR_TEST_PURPOSE)


@pytest.fixture
def db_session():
    """Provides a clean database session per test with rollback/cleanup."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

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
