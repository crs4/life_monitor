"""Add list of events to the subscription model

Revision ID: 24c34681f538
Revises: d5da43a38a6a
Create Date: 2022-01-21 15:29:19.648485

"""
from alembic import op
import sqlalchemy as sa
from lifemonitor.models import IntegerSet

# revision identifiers, used by Alembic.
revision = '24c34681f538'
down_revision = 'd5da43a38a6a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription', sa.Column('events', IntegerSet(), nullable=True))
    op.execute("UPDATE subscription SET events = '0'")


def downgrade():
    op.drop_column('subscription', 'events')
