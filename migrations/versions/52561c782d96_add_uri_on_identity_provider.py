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

"""Add uri on identity provider

Revision ID: 52561c782d96
Revises: cdf9f34b764c
Create Date: 2022-03-11 10:16:39.583434

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '52561c782d96'
down_revision = 'cdf9f34b764c'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # get api urls
    urls = bind.execute("SELECT p.id as pid, r.id as rid, r.uri as uri "
                        "FROM oauth2_identity_provider p JOIN resource r ON p.api_resource_id = r.id")
    # add URI
    op.add_column('oauth2_identity_provider', sa.Column('uri', sa.String(), nullable=True))
    # set api_url as default URI
    for url in urls:
        bind.execute(f"UPDATE oauth2_identity_provider SET uri = '{url[2]}' WHERE id = {url[0]}")
    # patch Github URI
    bind.execute("UPDATE oauth2_identity_provider SET uri = 'https://github.com' WHERE name = 'github'")
    # add constraints
    op.alter_column('oauth2_identity_provider', 'uri', nullable=False)
    op.create_unique_constraint(None, 'oauth2_identity_provider', ['uri'])


def downgrade():
    # remove URI
    op.drop_constraint(None, 'oauth2_identity_provider', type_='unique')
    op.drop_column('oauth2_identity_provider', 'uri')
