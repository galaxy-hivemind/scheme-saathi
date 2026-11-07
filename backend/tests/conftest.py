"""
Pytest fixtures for Scheme Saathi test suite.
Configures isolated test database sessions against the local PostgreSQL test instance.
Enforces multi-layer safety validation to protect application databases from destructive DDL.
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.db_safety import validate_database_target
from app.main import app as fastapi_app
from app.database.base import Base
from app.database.dependencies import get_db
import app.models  # noqa: F401

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/scheme_saathi_test",
)

# Preserve existing local test workflow by defaulting opt-in for verified test database
if not any(os.getenv(v) for v in ["ALLOW_TEST_DB_RESET", "ALLOW_DESTRUCTIVE_TESTS", "ALLOW_TEST_DB_WIPE"]):
    os.environ["ALLOW_TEST_DB_RESET"] = "1"

# Initial pre-flight safety check
validate_database_target(
    target_url=TEST_DATABASE_URL,
    app_url=settings.DATABASE_URL,
    target_label="regular test database",
    enforce_opt_in=True,
    opt_in_env_vars=["ALLOW_TEST_DB_RESET", "ALLOW_DESTRUCTIVE_TESTS", "ALLOW_TEST_DB_WIPE"],
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
    """Create all tables before test session and drop after."""
    # Re-verify database target safety prior to executing destructive DDL
    validate_database_target(
        target_url=TEST_DATABASE_URL,
        app_url=settings.DATABASE_URL,
        target_label="regular test database",
        enforce_opt_in=True,
        opt_in_env_vars=["ALLOW_TEST_DB_RESET", "ALLOW_DESTRUCTIVE_TESTS", "ALLOW_TEST_DB_WIPE"],
    )
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


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
