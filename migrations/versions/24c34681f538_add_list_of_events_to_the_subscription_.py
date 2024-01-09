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
