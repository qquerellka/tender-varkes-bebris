"""spell corrections

Revision ID: 0002_spell_corrections
Revises: 0001_init
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_spell_corrections"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spell_corrections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("wrong_term", sa.String(length=255), nullable=False),
        sa.Column("correct_term", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_spell_corrections_wrong_term",
        "spell_corrections",
        ["wrong_term"],
    )


def downgrade() -> None:
    op.drop_index("ix_spell_corrections_wrong_term", table_name="spell_corrections")
    op.drop_table("spell_corrections")
