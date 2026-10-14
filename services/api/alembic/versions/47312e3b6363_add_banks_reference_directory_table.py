"""add banks reference directory table

Revision ID: 47312e3b6363
Revises: 695be80075fd
Create Date: 2026-10-14 09:17:35.844532

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '47312e3b6363'
down_revision: str | None = '695be80075fd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BANK_TYPES = (
    "COMMERCIAL",
    "ISLAMIC",
    "DIGITAL",
    "E_WALLET",
    "STATE",
    "POLICY",
    "THRIFT",
    "RURAL",
    "COOPERATIVE",
    "FOREIGN",
    "WHOLESALE",
)


def upgrade() -> None:
    op.create_table(
        'banks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('country_code', sa.String(length=2), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('short_name', sa.String(length=100), nullable=True),
        sa.Column('bic', sa.String(length=11), nullable=True),
        sa.Column('national_id', sa.String(length=30), nullable=True),
        sa.Column('bank_type', sa.String(length=20), nullable=False),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"bank_type IN ({','.join(repr(t) for t in BANK_TYPES)})", name='ck_banks_bank_type'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('country_code', 'code', name='uq_banks_country_code'),
    )
    op.create_index('ix_banks_country_code', 'banks', ['country_code'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_banks_country_code', table_name='banks')
    op.drop_table('banks')
