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

"""Add client_name property on OAuth2Provider

Revision ID: 770508273f01
Revises: 64564b96c9db
Create Date: 2022-05-12 20:09:43.177927

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '770508273f01'
down_revision = '64564b96c9db'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    providers = bind.execute("SELECT id, name FROM oauth2_identity_provider")
    op.add_column('oauth2_identity_provider', sa.Column('client_name', sa.String(), nullable=True))
    for p in providers:
        bind.execute(f"UPDATE oauth2_identity_provider SET client_name = '{p[1]}' WHERE id = {p[0]}")
    # set constraints
    op.alter_column('oauth2_identity_provider', 'client_name', nullable=False)
    op.create_unique_constraint(None, 'oauth2_identity_provider', ['client_name'])


def downgrade():
    op.drop_constraint(None, 'oauth2_identity_provider', type_='unique')
    op.drop_column('oauth2_identity_provider', 'client_name')
