"""
Integration tests for Phase 3 / Increment 2 Chat and Pending Actions Alembic schema migration:
- Upgrade from Phase 3 head (f2c4b5e6d7a8) to Conversational Intake head (a1b2c3d4e5f6).
- Verify table existence, constraints, foreign keys (CASCADE to users, etc.), and indexes.
- Downgrade to f2c4b5e6d7a8 and verify chat_conversations, chat_messages, pending_actions tables are dropped.
- Re-upgrade to a1b2c3d4e5f6.
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


def test_chat_and_pending_actions_migration_lifecycle(monkeypatch):
    """
    Test complete lifecycle of a1b2c3d4e5f6 (chat_conversations, chat_messages, pending_actions):
    1. Upgrade to f2c4b5e6d7a8 (Phase 3 beneficiary_profiles head).
    2. Upgrade to a1b2c3d4e5f6 (Phase 3 Increment 2 chat tables).
    3. Verify table schema, constraints, foreign keys, and indexes.
    4. Downgrade to f2c4b5e6d7a8 and verify tables are cleanly dropped.
    5. Re-upgrade to a1b2c3d4e5f6.
    """
    _setup_container_migration_db_if_needed(monkeypatch)

    test_url = get_migration_test_db_url()
    validate_migration_test_target(test_url, settings.DATABASE_URL)
    engine = create_engine(test_url)
    verify_migration_connected_role(engine)

    with isolated_test_schema(engine, prefix="migtest_chat") as test_schema:
        alembic_cfg = configure_alembic_for_schema(test_url, test_schema)

        # 1. Start at f2c4b5e6d7a8
        command.upgrade(alembic_cfg, "f2c4b5e6d7a8")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "f2c4b5e6d7a8"

        # 2. Upgrade to a1b2c3d4e5f6
        command.upgrade(alembic_cfg, "a1b2c3d4e5f6")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "a1b2c3d4e5f6"

            # Check foreign key delete rules
            conv_user_fk = get_pg_foreign_key_ondelete(
                conn, "chat_conversations", "chat_conversations_user_id_fkey", schema_name=test_schema
            )
            assert conv_user_fk == "CASCADE"

            conv_ben_fk = get_pg_foreign_key_ondelete(
                conn, "chat_conversations", "chat_conversations_beneficiary_id_fkey", schema_name=test_schema
            )
            assert conv_ben_fk == "SET NULL"

            msg_conv_fk = get_pg_foreign_key_ondelete(
                conn, "chat_messages", "chat_messages_conversation_id_fkey", schema_name=test_schema
            )
            assert msg_conv_fk == "CASCADE"

            pending_user_fk = get_pg_foreign_key_ondelete(
                conn, "pending_actions", "pending_actions_user_id_fkey", schema_name=test_schema
            )
            assert pending_user_fk == "CASCADE"

            pending_conv_fk = get_pg_foreign_key_ondelete(
                conn, "pending_actions", "pending_actions_conversation_id_fkey", schema_name=test_schema
            )
            assert pending_conv_fk == "CASCADE"

            pending_ben_fk = get_pg_foreign_key_ondelete(
                conn, "pending_actions", "pending_actions_beneficiary_id_fkey", schema_name=test_schema
            )
            assert pending_ben_fk == "CASCADE"

        inspector = inspect(engine)
        tables = set(inspector.get_table_names(schema=test_schema))
        assert {"chat_conversations", "chat_messages", "pending_actions"}.issubset(tables)

        # Inspect chat_conversations columns and indexes
        conv_cols = {c["name"]: c for c in inspector.get_columns("chat_conversations", schema=test_schema)}
        assert {"id", "user_id", "beneficiary_id", "title", "language", "status", "context_state", "created_at", "updated_at"}.issubset(conv_cols.keys())

        conv_indexes = {ix["name"] for ix in inspector.get_indexes("chat_conversations", schema=test_schema)}
        assert "ix_chat_conversations_user_id" in conv_indexes
        assert "ix_chat_conversations_beneficiary_id" in conv_indexes
        assert "ix_chat_conversations_user_updated" in conv_indexes

        # Inspect chat_messages columns and indexes
        msg_cols = {c["name"]: c for c in inspector.get_columns("chat_messages", schema=test_schema)}
        assert {"id", "conversation_id", "role", "content", "response_type", "structured_data", "tool_calls", "created_at"}.issubset(msg_cols.keys())

        msg_indexes = {ix["name"] for ix in inspector.get_indexes("chat_messages", schema=test_schema)}
        assert "ix_chat_messages_conversation_id" in msg_indexes
        assert "ix_chat_messages_conv_created" in msg_indexes

        # Inspect pending_actions columns and indexes
        pa_cols = {c["name"]: c for c in inspector.get_columns("pending_actions", schema=test_schema)}
        assert {"id", "conversation_id", "user_id", "beneficiary_id", "action_type", "payload", "summary", "status", "expires_at", "created_at", "confirmed_at", "executed_at"}.issubset(pa_cols.keys())

        pa_indexes = {ix["name"] for ix in inspector.get_indexes("pending_actions", schema=test_schema)}
        assert "ix_pending_actions_conversation_id" in pa_indexes
        assert "ix_pending_actions_user_id" in pa_indexes
        assert "ix_pending_actions_beneficiary_id" in pa_indexes
        assert "ix_pending_actions_expires_at" in pa_indexes
        assert "ix_pending_actions_user_status" in pa_indexes
        assert "ix_pending_actions_conv_status" in pa_indexes

        # 3. Downgrade back to f2c4b5e6d7a8
        command.downgrade(alembic_cfg, "f2c4b5e6d7a8")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "f2c4b5e6d7a8"

        inspector_downgraded = inspect(engine)
        downgraded_tables = set(inspector_downgraded.get_table_names(schema=test_schema))
        assert "chat_conversations" not in downgraded_tables
        assert "chat_messages" not in downgraded_tables
        assert "pending_actions" not in downgraded_tables
        assert {"users", "user_profiles", "beneficiary_profiles", "schemes", "scheme_rule_versions"}.issubset(downgraded_tables)

        # 4. Re-upgrade back to a1b2c3d4e5f6
        command.upgrade(alembic_cfg, "a1b2c3d4e5f6")
        with engine.connect() as conn:
            rev = conn.execute(text(f'SELECT version_num FROM "{test_schema}".alembic_version')).scalar()
            assert rev == "a1b2c3d4e5f6"

        inspector_reupgraded = inspect(engine)
        reupgraded_tables = set(inspector_reupgraded.get_table_names(schema=test_schema))
        assert {"chat_conversations", "chat_messages", "pending_actions"}.issubset(reupgraded_tables)

    engine.dispose()
