# Copyright (c) 2020-2024 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Track sync of builds

Revision ID: 6bb84f8b8c77
Revises: 94fa885a5808
Create Date: 2023-03-06 10:18:43.563006

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6bb84f8b8c77'
down_revision = '94fa885a5808'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('oauth2_identity', 'tokens',
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True)
    op.drop_constraint('ro_crate_hosting_service_id_fkey', 'ro_crate', type_='foreignkey')
    op.create_foreign_key(None, 'ro_crate', 'resource', ['hosting_service_id'], ['id'])
    op.add_column('test_instance', sa.Column('last_builds_update', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('test_instance', 'last_builds_update')
    op.drop_constraint(None, 'ro_crate', type_='foreignkey')
    op.create_foreign_key('ro_crate_hosting_service_id_fkey', 'ro_crate', 'hosting_service', ['hosting_service_id'], ['id'])
    op.alter_column('oauth2_identity', 'tokens',
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False)
