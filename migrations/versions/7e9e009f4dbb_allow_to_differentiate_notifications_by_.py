"""Allow to differentiate notifications by type

Revision ID: 7e9e009f4dbb
Revises: 505e4e6976de
Create Date: 2022-02-07 14:21:52.319351

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e9e009f4dbb'
down_revision = '505e4e6976de'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notification', sa.Column('type', sa.String(), nullable=True))
    op.execute("UPDATE notification SET type = 'workflow_status_notification'")
    op.alter_column('notification', 'type', nullable=False)


def downgrade():
    op.drop_column('notification', 'type')
