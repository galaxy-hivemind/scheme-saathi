"""
Integration tests for Alembic schema migrations against an isolated PostgreSQL database.
Validates safety guards, upgrade from previous revision, fresh upgrade to head,
downgrade behavior, and PostgreSQL foreign key constraint actions (RESTRICT vs CASCADE).
"""
from pathlib import Path
import os
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import settings

MIGRATION_TEST_DB_URL = os.getenv(
    "MIGRATION_TEST_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test",
)

DISPOSABLE_TEST_MARKERS = ["migration_test", "disposable_test", "test_migration"]


def validate_disposable_migration_test_db(test_url: str, app_url: str) -> None:
    """
    Safety guard: Strictly verifies that the migration test target is positively
    identified as a dedicated disposable test database and is not the application database.
    Prevents accidental destruction of application or shared databases.
    """
    if not test_url or not test_url.strip():
        raise ValueError("Migration test target URL cannot be empty.")

    test_parsed = make_url(test_url)
    app_parsed = make_url(app_url)

    # 1. Reject if points to the exact same database as application DATABASE_URL
    if (
        test_parsed.host == app_parsed.host
        and test_parsed.port == app_parsed.port
        and test_parsed.database == app_parsed.database
    ):
        raise ValueError(
            f"Unsafe migration test target: Target URL points to the active application database '{test_parsed.database}'."
        )

    # 2. Require an explicit disposable test marker in the database name
    db_name = (test_parsed.database or "").lower()
    if not any(marker in db_name for marker in DISPOSABLE_TEST_MARKERS):
        raise ValueError(
            f"Unsafe migration test target: Database name '{test_parsed.database}' "
            f"does not contain any required disposable test markers ({DISPOSABLE_TEST_MARKERS})."
        )


def get_pg_foreign_key_ondelete(conn, table_name: str, constraint_name: str) -> str:
    """
    Queries PostgreSQL's pg_constraint catalog for the authoritative confdeltype.
    confdeltype values: 'r' = RESTRICT, 'c' = CASCADE, 'a' = NO ACTION, 'n' = SET NULL.
    """
    query = text("""
        SELECT c.confdeltype
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = :table
          AND c.conname = :conname;
    """)
    result = conn.execute(query, {"table": table_name, "conname": constraint_name}).scalar()
    mapping = {"r": "RESTRICT", "c": "CASCADE", "a": "NO ACTION", "n": "SET NULL"}
    return mapping.get(result, str(result))


# ── Safety Guard Tests ────────────────────────────────────────────────────────

def test_migration_safety_guard_rejects_app_database():
    """Verify that the safety guard prevents running migrations against DATABASE_URL."""
    with pytest.raises(ValueError, match="points to the active application database"):
        validate_disposable_migration_test_db(
            test_url=settings.DATABASE_URL,
            app_url=settings.DATABASE_URL,
        )


def test_migration_safety_guard_rejects_non_disposable_database():
    """Verify that a database without a disposable marker is rejected."""
    with pytest.raises(ValueError, match="does not contain any required disposable test markers"):
        validate_disposable_migration_test_db(
            test_url="postgresql://postgres:postgres@localhost:5432/production_db",
            app_url=settings.DATABASE_URL,
        )


def test_migration_safety_guard_accepts_valid_disposable_target():
    """Verify that a properly marked disposable test database passes validation."""
    validate_disposable_migration_test_db(
        test_url=MIGRATION_TEST_DB_URL,
        app_url=settings.DATABASE_URL,
    )


# ── Migration Lifecycle & Constraint Assertion Tests ──────────────────────────

def test_alembic_fresh_database_upgrade_head_and_foreign_keys():
    """
    Validates fresh database path:
    1. Positive identification and safety validation.
    2. Upgrade from empty schema directly to head.
    3. Verifies user_consents.user_id ondelete is RESTRICT.
    4. Verifies user_profiles.user_id ondelete is CASCADE.
    5. Clean teardown in finally block.
    """
    validate_disposable_migration_test_db(MIGRATION_TEST_DB_URL, settings.DATABASE_URL)
    engine = create_engine(MIGRATION_TEST_DB_URL)

    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", MIGRATION_TEST_DB_URL)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    try:
        # Reset disposable schema
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()

        # Upgrade from base to head
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"users", "user_profiles", "user_consents", "alembic_version"}.issubset(tables)

        # Verify current revision
        with engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev == "bb1bf3e30acc"

            # Foreign key assertions:
            # user_consents.user_id -> RESTRICT
            consent_fk_action = get_pg_foreign_key_ondelete(conn, "user_consents", "user_consents_user_id_fkey")
            assert consent_fk_action == "RESTRICT"

            # user_profiles.user_id -> CASCADE
            profile_fk_action = get_pg_foreign_key_ondelete(conn, "user_profiles", "user_profiles_user_id_fkey")
            assert profile_fk_action == "CASCADE"
    finally:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()
        engine.dispose()


def test_alembic_upgrade_from_previous_revision_and_downgrade():
    """
    Validates existing database upgrade path:
    1. Upgrade to previous revision d60b841ec91c (constraint had CASCADE).
    2. Upgrade to new revision bb1bf3e30acc (constraint altered to RESTRICT).
    3. Downgrade back to d60b841ec91c (constraint restored to CASCADE).
    4. Re-upgrade back to bb1bf3e30acc (constraint restored to RESTRICT).
    """
    validate_disposable_migration_test_db(MIGRATION_TEST_DB_URL, settings.DATABASE_URL)
    engine = create_engine(MIGRATION_TEST_DB_URL)

    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", MIGRATION_TEST_DB_URL)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    try:
        # Reset disposable schema
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()

        # Step 1: Upgrade to previous revision d60b841ec91c
        command.upgrade(alembic_cfg, "d60b841ec91c")
        with engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev == "d60b841ec91c"
            fk_action = get_pg_foreign_key_ondelete(conn, "user_consents", "user_consents_user_id_fkey")
            assert fk_action == "CASCADE"

        # Step 2: Apply new migration to head (bb1bf3e30acc)
        command.upgrade(alembic_cfg, "bb1bf3e30acc")
        with engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev == "bb1bf3e30acc"
            fk_action = get_pg_foreign_key_ondelete(conn, "user_consents", "user_consents_user_id_fkey")
            assert fk_action == "RESTRICT"

        # Step 3: Downgrade back to d60b841ec91c
        command.downgrade(alembic_cfg, "d60b841ec91c")
        with engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev == "d60b841ec91c"
            fk_action = get_pg_foreign_key_ondelete(conn, "user_consents", "user_consents_user_id_fkey")
            assert fk_action == "CASCADE"

        # Step 4: Re-upgrade back to head
        command.upgrade(alembic_cfg, "head")
        with engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev == "bb1bf3e30acc"
            fk_action = get_pg_foreign_key_ondelete(conn, "user_consents", "user_consents_user_id_fkey")
            assert fk_action == "RESTRICT"
    finally:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()
        engine.dispose()
