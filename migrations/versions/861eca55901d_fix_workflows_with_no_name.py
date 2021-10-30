"""Fix workflows with no name

Revision ID: 861eca55901d
Revises: 01684f92a380
Create Date: 2021-10-30 15:51:52.296778

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '861eca55901d'
down_revision = '01684f92a380'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    bind.execute("update resource set name='unknown' where id in (select id from workflow natural join resource where name='')")


def downgrade():
    pass
