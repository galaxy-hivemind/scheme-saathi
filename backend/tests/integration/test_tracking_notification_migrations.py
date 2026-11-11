"""
Integration tests for Phase 4 / Increment 1 Application Tracking and Notification Alembic schema migration:
- Upgrade from Documents & Applications head (b2c3d4e5f6a7) to Tracking & Notifications head (c3d4e5f6a7b8).
- Verify table existence, constraints, foreign keys (CASCADE to applications, SET NULL to applications), and indexes.
- Downgrade to b2c3d4e5f6a7 and verify application_status_history, notifications tables are dropped.
- Re-upgrade to c3d4e5f6a7b8.
"""
from pathlib import Path
from urllib.parse import quote_plus
import os
import uuid
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings
from app.core.db_safety import provision_test_database_sentinel, MIGRATION_TEST_PURPOSE, normalize_db_url
from tests.integration.test_migrations import (
    get_migration_test_db_url,
    validate_migration_test_target,
    verify_migration_connected_role,
    isolated_test_schema,
    configure_alembic_for_schema,
    get_pg_foreign_key_ondelete,
)
from tests.integration.test_scheme_migrations import _setup_container_migration_db_if_needed


def test_tracking_and_notification_migration_lifecycle(monkeypatch):
    """
    Test complete lifecycle of c3d4e5f6a7b8 (application_status_history, notifications):
    1. Upgrade to b2c3d4e5f6a7 (Phase 3 Increment 3 documents & applications head).
    2. Upgrade to c3d4e5f6a7b8 (Phase 4 Increment 1 tracking & notifications).
    3. Verify table schema, constraints, foreign keys, and indexes.
    4. Downgrade to b2c3d4e5f6a7 and verify tables are cleanly dropped.
    5. Re-upgrade to c3d4e5f6a7b8.
    """
    _setup_container_migration_db_if_needed(monkeypatch)

    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with isolated_test_schema(engine, prefix="migtest_track_notify") as test_schema:
        alembic_cfg = configure_alembic_for_schema(test_url, test_schema)

        # 1. Start at b2c3d4e5f6a7
        command.upgrade(alembic_cfg, "b2c3d4e5f6a7")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "b2c3d4e5f6a7"

        # 2. Upgrade to c3d4e5f6a7b8
        command.upgrade(alembic_cfg, "c3d4e5f6a7b8")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "c3d4e5f6a7b8"

            # Check foreign key delete rules
            history_app_fk = get_pg_foreign_key_ondelete(
                conn, "application_status_history", "application_status_history_application_id_fkey", schema_name=test_schema
            )
            assert history_app_fk == "CASCADE"

            notify_user_fk = get_pg_foreign_key_ondelete(
                conn, "notifications", "notifications_user_id_fkey", schema_name=test_schema
            )
            assert notify_user_fk == "CASCADE"

            notify_app_fk = get_pg_foreign_key_ondelete(
                conn, "notifications", "notifications_application_id_fkey", schema_name=test_schema
            )
            assert notify_app_fk == "SET NULL"

            # Check indexes on application_status_history
            history_indexes = conn.execute(
                text(
                    f"SELECT indexname FROM pg_indexes WHERE schemaname = '{test_schema}' AND tablename = 'application_status_history'"
                )
            ).scalars().all()
            assert "ix_app_status_history_app_id" in history_indexes
            assert "ix_app_status_history_app_created" in history_indexes

            # Check indexes on notifications
            notify_indexes = conn.execute(
                text(
                    f"SELECT indexname FROM pg_indexes WHERE schemaname = '{test_schema}' AND tablename = 'notifications'"
                )
            ).scalars().all()
            assert "ix_notifications_user_id" in notify_indexes
            assert "ix_notifications_app_id" in notify_indexes
            assert "ix_notifications_user_unread" in notify_indexes
            assert "ix_notifications_user_created" in notify_indexes

            # Verify table columns in inspector
            insp = inspect(conn)
            history_cols = {c["name"]: c for c in insp.get_columns("application_status_history", schema=test_schema)}
            assert "id" in history_cols
            assert "application_id" in history_cols
            assert "status" in history_cols
            assert "source_type" in history_cols
            assert "source_reference" in history_cols
            assert "notes" in history_cols
            assert "created_at" in history_cols

            notify_cols = {c["name"]: c for c in insp.get_columns("notifications", schema=test_schema)}
            assert "id" in notify_cols
            assert "user_id" in notify_cols
            assert "application_id" in notify_cols
            assert "title" in notify_cols
            assert "message" in notify_cols
            assert "notification_type" in notify_cols
            assert "priority" in notify_cols
            assert "channels" in notify_cols
            assert "is_read" in notify_cols
            assert "read_at" in notify_cols
            assert "created_at" in notify_cols

        # 3. Downgrade back to b2c3d4e5f6a7
        command.downgrade(alembic_cfg, "b2c3d4e5f6a7")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "b2c3d4e5f6a7"

            insp = inspect(conn)
            tables = insp.get_table_names(schema=test_schema)
            assert "application_status_history" not in tables
            assert "notifications" not in tables
            assert "application_drafts" in tables

        # 4. Re-upgrade to c3d4e5f6a7b8
        command.upgrade(alembic_cfg, "c3d4e5f6a7b8")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "c3d4e5f6a7b8"

            insp = inspect(conn)
            tables = insp.get_table_names(schema=test_schema)
            assert "application_status_history" in tables
            assert "notifications" in tables
