"""Add flag to enable/disable mail notifications

Revision ID: d5da43a38a6a
Revises: d1387a6fe551
Create Date: 2022-01-20 13:27:41.016651

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5da43a38a6a'
down_revision = 'd1387a6fe551'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('email_notifications', sa.Boolean()))
    op.execute("UPDATE \"user\" SET email_notifications = true")
    op.alter_column('user', 'email_notifications', nullable=False)


def downgrade():
    op.drop_column('user', 'email_notifications')
