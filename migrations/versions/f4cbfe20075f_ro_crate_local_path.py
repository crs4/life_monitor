"""RO-Crate local path

Revision ID: f4cbfe20075f
Revises: 861eca55901d
Create Date: 2021-12-02 18:09:13.207425

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4cbfe20075f'
down_revision = '861eca55901d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ro_crate', sa.Column('local_path', sa.String(), nullable=True))


def downgrade():
    op.drop_column('ro_crate', 'local_path')
