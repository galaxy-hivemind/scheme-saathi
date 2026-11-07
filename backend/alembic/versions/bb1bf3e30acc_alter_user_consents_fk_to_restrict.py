"""alter_user_consents_fk_to_restrict

Revision ID: bb1bf3e30acc
Revises: d60b841ec91c
Create Date: 2026-11-07 16:15:00.970552

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb1bf3e30acc'
down_revision: Union[str, Sequence[str], None] = 'd60b841ec91c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Alter user_consents.user_id foreign key from ON DELETE CASCADE to ON DELETE RESTRICT.
    Ensures citizen consent audit records cannot be silently cascade-deleted.
    """
    op.drop_constraint(
        constraint_name="user_consents_user_id_fkey",
        table_name="user_consents",
        type_="foreignkey",
    )
    op.create_foreign_key(
        constraint_name="user_consents_user_id_fkey",
        source_table="user_consents",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """
    Revert user_consents.user_id foreign key from ON DELETE RESTRICT back to ON DELETE CASCADE.
    """
    op.drop_constraint(
        constraint_name="user_consents_user_id_fkey",
        table_name="user_consents",
        type_="foreignkey",
    )
    op.create_foreign_key(
        constraint_name="user_consents_user_id_fkey",
        source_table="user_consents",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )
