"""Add name index on notification model

Revision ID: d1387a6fe551
Revises: 97e77a9c44b2
Create Date: 2022-01-18 15:41:53.769530

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1387a6fe551'
down_revision = '97e77a9c44b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_notification_name'), 'notification', ['name'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_notification_name'), table_name='notification')
