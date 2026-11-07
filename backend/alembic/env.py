import sys
from pathlib import Path
from logging.config import fileConfig

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import engine_from_config, pool, text
from alembic import context

from app.core.config import settings
from app.database.base import Base
import app.models  # noqa: F401 — ensure all models are imported

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dynamically from app settings if not explicitly provided or if default placeholder
current_url = config.get_main_option("sqlalchemy.url")
if not current_url or "driver://user:pass" in current_url:
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    schema_name = config.get_main_option("schema_name") or config.get_main_option("version_table_schema")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    schema_name = config.get_main_option("schema_name") or config.get_main_option("version_table_schema")
    connect_args = {}
    if schema_name:
        connect_args["options"] = f"-csearch_path={schema_name}"

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        if schema_name:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=schema_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
