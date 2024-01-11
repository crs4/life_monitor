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

"""Add user notification model

Revision ID: 97e77a9c44b2
Revises: f4cbfe20075f
Create Date: 2022-01-17 13:21:37.565495

"""
from alembic import op
import sqlalchemy as sa
from lifemonitor.models import JSON


# revision identifiers, used by Alembic.
revision = '97e77a9c44b2'
down_revision = 'f4cbfe20075f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notification',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('created', sa.DateTime(), nullable=True),
                    sa.Column('name', sa.String(), nullable=True),
                    sa.Column('type', sa.String(), nullable=False),
                    sa.Column('data', JSON(), nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('user_notification',
                    sa.Column('emailed', sa.DateTime(), nullable=True),
                    sa.Column('read', sa.DateTime(), nullable=True),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('notification_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['notification_id'], ['notification.id'], ),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
                    sa.PrimaryKeyConstraint('user_id', 'notification_id')
                    )
    op.add_column('user', sa.Column('email', sa.String(), nullable=True))
    op.add_column('user', sa.Column('email_verification_hash', sa.String(length=256), nullable=True))
    op.add_column('user', sa.Column('email_verified', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('user', 'email_verified')
    op.drop_column('user', 'email_verification_hash')
    op.drop_column('user', 'email')
    op.drop_table('user_notification')
    op.drop_table('notification')
