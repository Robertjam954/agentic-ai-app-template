"""Replace persisted chat transcripts with explicit user preferences.

Revision ID: b7d9e2f4a6c8
Revises: a1b2c3d4e5f6
Create Date: 2026-10-09 00:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision = "b7d9e2f4a6c8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deliberately delete every historical turn: patient and chat data must not
    # survive the privacy migration.
    op.drop_table("conversationmessage")
    op.drop_table("conversation")
    op.create_table(
        "userpreference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "text", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "text"),
    )


def downgrade() -> None:
    op.drop_table("userpreference")
    op.create_table(
        "conversation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "title", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "conversationmessage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False
        ),
        sa.Column(
            "content", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
